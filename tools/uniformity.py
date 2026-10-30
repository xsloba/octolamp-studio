"""Measure brightness uniformity of the all-white lamp photo and derive per-LED gains."""
import json, math, sys
import numpy as np
from PIL import Image, ImageOps

photo, layout_path, out_path = sys.argv[1:4]
seed = [float(v) for v in sys.argv[4:7]] if len(sys.argv) >= 7 else None
img = ImageOps.exif_transpose(Image.open(photo)).convert("RGB")
a = np.asarray(img, dtype=np.float32); lum = 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]
H, W = lum.shape
sat = a.max(axis=2) >= 250
# ---- ring fit (same method as ringprobe) ----
thr = np.percentile(lum, 90); ys, xs = np.nonzero(lum > thr)
keep = (ys > 0.10 * H) & (ys < 0.90 * H); ys, xs = ys[keep].astype(float), xs[keep].astype(float)
def fit(xs, ys):
    A = np.c_[2 * xs, 2 * ys, np.ones_like(xs)]; b = xs ** 2 + ys ** 2
    cx, cy, c = np.linalg.lstsq(A, b, rcond=None)[0]; return cx, cy, math.sqrt(c + cx ** 2 + cy ** 2)
cx, cy, r = seed if seed else fit(xs, ys)
for _ in range(4):
    d = np.hypot(xs - cx, ys - cy); m = np.abs(d - r) < 0.10 * r; cx, cy, r = fit(xs[m], ys[m])
angles = np.radians(np.arange(0, 360, 0.5)); ang_deg = np.degrees(angles)
def sample(rad, ang):
    x = (cx + rad * np.cos(ang)).astype(int).clip(0, W - 1); y = (cy + rad * np.sin(ang)).astype(int).clip(0, H - 1)
    return lum[y, x]
radii = np.linspace(0.80 * r, 1.12 * r, 80)
radial = np.array([np.median(sample(rr, angles)) for rr in radii])
band = radii[radial > 0.5 * radial.max()]; r_in, r_out = band.min(), band.max()
print(f"ring: centre ({cx:.0f},{cy:.0f}) r={r:.0f}, band {r_in:.0f}-{r_out:.0f}px | saturated px in image {100*sat.mean():.2f}%")
# the cat's legs join the ring at the bottom (~70-110 deg); exclude that from ring stats
ring_ok = ~((ang_deg > 62) & (ang_deg < 118))
edge_x = cx + r_out * np.cos(angles); edge_y = cy + r_out * np.sin(angles)
ring_ok &= (edge_x > 8) & (edge_x < W - 8) & (edge_y > 8) & (edge_y < H - 8)     # skip where the ring leaves the frame
depths = np.linspace(r_in + 0.2 * (r_out - r_in), r_out - 0.2 * (r_out - r_in), 5)
profs = np.array([sample(rr, angles) for rr in depths]); prof = profs.mean(axis=0)
k = 50; pad = np.r_[prof[-k:], prof, prof[:k]]; trend = np.convolve(pad, np.ones(2 * k + 1) / (2 * k + 1), "same")[k:-k]
ripple = [100 * ((p - np.convolve(np.r_[p[-k:], p, p[:k]], np.ones(2*k+1)/(2*k+1), "same")[k:-k])[ring_ok]).std() / p[ring_ok].mean() for p in profs]
print("ring dot contrast, both passes (std, mid-band depths):", " ".join(f"{x:.1f}%" for x in ripple))
t_ok = trend[ring_ok]
print(f"ring broad brightness: min {t_ok.min():.0f} at {ang_deg[ring_ok][t_ok.argmin()]:.0f} deg, max {t_ok.max():.0f} at {ang_deg[ring_ok][t_ok.argmax()]:.0f} deg, "
      f"spread {100*(t_ok.max()-t_ok.min())/t_ok.mean():.0f}% of mean {t_ok.mean():.0f}")
for lo, hi, name in [(-30, 30, "right"), (240, 300, "top"), (150, 210, "left"), (118, 150, "lower-left"), (30, 62, "lower-right")]:
    m = ((ang_deg - lo) % 360) < (hi - lo); print(f"   {name:11} {prof[m & ring_ok].mean():6.1f}")
# ---- cat: map layout coords into the photo; layout outer LED circle (radius 0.5) ~ ring centreline ----
lay = json.load(open(layout_path)); R = (r_in + r_out) / 2
to_px = lambda p: (cx + (p["x"] - 0.5) * 2 * R, cy + (p["y"] - 0.5) * 2 * R)
yy, xx = np.mgrid[0:H, 0:W]; inside = np.hypot(xx - cx, yy - cy) < r_in * 0.97
cat_mask = inside & (lum > 0.35 * np.percentile(lum[inside], 99))
print(f"cat area {cat_mask.sum()} px, mean lum {lum[cat_mask].mean():.0f}, ring band mean {prof[ring_ok].mean():.0f}")
regions = {"head (no ears)": [i for i in lay["regions"]["head"] if i not in lay["regions"]["ears"]],
           "ears": lay["regions"]["ears"], "tail": lay["regions"]["tail"], "legs": lay["regions"]["legs"]}
cat_lum = {}
for name, leds in regions.items():
    vals = []
    for i in leds:
        x, y = to_px(lay["pixels"][i]); win = 26
        m = cat_mask[int(y) - win:int(y) + win, int(x) - win:int(x) + win]
        patch = lum[int(y) - win:int(y) + win, int(x) - win:int(x) + win]
        if m.sum() > 50: vals.append(patch[m].mean())
    cat_lum[name] = float(np.mean(vals)) if vals else float("nan")
    print(f"   cat {name:15} {cat_lum[name]:6.1f}  ({len(vals)}/{len(leds)} LEDs sampled)")
# head centre vs head edge
hx, hy = to_px({"x": np.mean([lay["pixels"][i]["x"] for i in regions["head (no ears)"]]), "y": np.mean([lay["pixels"][i]["y"] for i in regions["head (no ears)"]])})
c = lum[int(hy) - 40:int(hy) + 40, int(hx) - 40:int(hx) + 40]; print(f"   cat head centre {c.mean():6.1f}")
# ---- gains: dim the bright zones down to the dim ones (gains <= 1) ----
gains = {}
ring_leds = lay["regions"]["ring"]
ref = np.percentile(t_ok, 15)
for i in ring_leds:
    p = lay["pixels"][i]; th = math.degrees(math.atan2(p["y"] - 0.5, p["x"] - 0.5)) % 360
    j = int(round(th * 2)) % 720
    gains[i] = float(min(1.0, max(0.55, ref / trend[j])))
cref = min(v for v in cat_lum.values() if v == v)
for name, leds in regions.items():
    g = min(1.0, max(0.55, cref / cat_lum[name])) if cat_lum[name] == cat_lum[name] else 1.0
    for i in leds: gains[i] = float(g)
json.dump({"gains": {str(k): round(v, 3) for k, v in sorted(gains.items())},
           "ring": {"cx": cx, "cy": cy, "r_in": r_in, "r_out": r_out}, "cat_lum": cat_lum}, open(out_path, "w"), indent=1)
gs = np.array(list(gains.values())); print(f"gains: min {gs.min():.2f} mean {gs.mean():.2f} | ring {np.mean([gains[i] for i in ring_leds]):.2f} | "
      + " ".join(f"{n}={np.mean([gains[i] for i in l]):.2f}" for n, l in regions.items()))
