"""Measure LED-dot visibility on the ring from a photo.

Fits the ring (bright annulus) by least squares, then samples luminance around it at
several radii across the band. For each half reports mean brightness and 'dot contrast'
= std of the luminance after removing a slow trend, divided by the mean (in %).
"""
import json, math, sys
import numpy as np
from PIL import Image, ImageOps

img = ImageOps.exif_transpose(Image.open(sys.argv[1])).convert("RGB")
a = np.asarray(img, dtype=np.float32); lum = 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]
H, W = lum.shape
# candidate ring pixels: bright, ignore the bottom 12% (desk reflections) and the top 10%
thr = np.percentile(lum, 93)
ys, xs = np.nonzero(lum > thr)
keep = (ys > 0.10 * H) & (ys < 0.88 * H)
ys, xs = ys[keep].astype(float), xs[keep].astype(float)
# algebraic circle fit (Kasa) on the bright pixels, then refine with only the annulus near that radius
def fit(xs, ys):
    A = np.c_[2 * xs, 2 * ys, np.ones_like(xs)]; b = xs ** 2 + ys ** 2
    cx, cy, c = np.linalg.lstsq(A, b, rcond=None)[0]; return cx, cy, math.sqrt(c + cx ** 2 + cy ** 2)
cx, cy, r = fit(xs, ys)
for _ in range(3):
    d = np.hypot(xs - cx, ys - cy); m = np.abs(d - r) < 0.12 * r
    cx, cy, r = fit(xs[m], ys[m])
# band edges: walk radially and find where luminance drops below half the band peak (median over angles)
angles = np.radians(np.arange(0, 360, 0.5))
radii = np.linspace(0.78 * r, 1.12 * r, 70)
def sample(rad, ang):
    x = (cx + rad * np.cos(ang)).astype(int).clip(0, W - 1); y = (cy + rad * np.sin(ang)).astype(int).clip(0, H - 1)
    return lum[y, x]
radial = np.array([np.median(sample(rr, angles)) for rr in radii])
band = radii[radial > 0.5 * radial.max()]
r_in, r_out = band.min(), band.max()
print(f"ring fit: centre ({cx:.0f},{cy:.0f}) r={r:.0f}px, bright band {r_in:.0f}-{r_out:.0f}px")
def halves(ang_deg):
    return {"left": (ang_deg > 100) & (ang_deg < 260), "right": (ang_deg < 80) | (ang_deg > 280)}
ang_deg = np.degrees(angles)
res = {}
depths = np.linspace(r_in + 0.1 * (r_out - r_in), r_out - 0.1 * (r_out - r_in), 7)
for name, mask in halves(ang_deg).items():
    per_depth = []
    for rr in depths:
        prof = sample(rr, angles)
        # slow trend: moving average over ~25 deg (several LED pitches), circular
        k = 50; pad = np.r_[prof[-k:], prof, prof[:k]]; trend = np.convolve(pad, np.ones(2 * k + 1) / (2 * k + 1), "same")[k:-k]
        resid = (prof - trend)[mask]; mean = prof[mask].mean()
        per_depth.append((rr, mean, 100 * resid.std() / mean, 100 * (np.percentile(resid, 97) - np.percentile(resid, 3)) / mean))
    res[name] = per_depth
    print(f"{name:5}: mean lum {np.mean([p[1] for p in per_depth]):6.1f} | dot contrast (std) by depth inner->outer: "
          + " ".join(f"{p[2]:4.1f}%" for p in per_depth) + f" | worst peak-to-trough {max(p[3] for p in per_depth):.0f}%")
sat = (a.max(axis=2) >= 250)
print(f"saturated pixels in ring band: {100 * sat[np.abs(np.hypot(*np.meshgrid(np.arange(W) - cx, np.arange(H) - cy)) - (r_in + r_out) / 2) < (r_out - r_in) / 2].mean():.1f}%")
json.dump({"cx": cx, "cy": cy, "r": r, "r_in": r_in, "r_out": r_out}, open(sys.argv[2], "w"))
