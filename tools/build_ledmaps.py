#!/usr/bin/env python3
"""Build the three WLED ledmaps from a lamp's layout.json.

    python3 build_ledmaps.py path/to/layout.json out_dir/

writes
  ledmap.json   "Octocat 2D": every LED placed on a 24x24 grid at its real position (2D effects)
  ledmap1.json  "Ring + cat": ring LEDs in rows 0-2 sorted by angle, cat LEDs in rows 3-4
  ledmap2.json  "Octants":    one row per 45-degree pie slice, clockwise from 12 o'clock

layout.json comes from docs/mapping.md (see build_layout.py for the reference build).
"""
import json, math, os, sys

W = H = 24


def octocat_2d(px):
    """Each LED goes to the free grid cell nearest its position; the most clear-cut LEDs are placed first."""
    grid = [-1] * (W * H)
    frac = lambda v: abs(v * (W - 1) - round(v * (W - 1)))
    for p in sorted(px, key=lambda p: frac(p["x"]) + frac(p["y"])):
        fx, fy = p["x"] * (W - 1), p["y"] * (H - 1)
        x, y = min(((x, y) for x in range(W) for y in range(H) if grid[y * W + x] == -1),
                   key=lambda c: (c[0] - fx) ** 2 + (c[1] - fy) ** 2)
        grid[y * W + x] = p["i"]
    return {"n": "Octocat 2D", "width": W, "height": H, "map": grid}


def ring_and_cat(px, regions):
    """Ring sorted by angle from 6 o'clock (so effects flow round), cat from feet to ears."""
    pos = {p["i"]: p for p in px}
    ang = lambda i: (math.degrees(math.atan2(pos[i]["y"] - 0.5, pos[i]["x"] - 0.5)) - 90) % 360
    ring = sorted(regions["ring"], key=ang)
    cat = sorted(regions["cat"], key=lambda i: -pos[i]["y"])
    assert len(ring) <= 3 * W and len(cat) <= 2 * 15, "ring needs <=72 LEDs and cat <=30 for this layout"
    grid = [-1] * (W * H)
    for k, led in enumerate(ring): grid[k] = led
    for k, led in enumerate(cat): grid[3 * W + (k // 15) * W + k % 15] = led
    return {"n": "Ring + cat", "map": grid}


def octants(px):
    clock = lambda p: math.degrees(math.atan2(p["x"] - 0.5, -(p["y"] - 0.5))) % 360
    rows = [[] for _ in range(8)]
    for p in px: rows[int(clock(p) // 45)].append(p)
    grid = [-1] * (W * H)
    for k, row in enumerate(rows):
        row.sort(key=clock); assert len(row) <= W, f"slice {k + 1} has {len(row)} LEDs (max {W})"
        for j, p in enumerate(row): grid[k * W + j] = p["i"]
    return {"n": "Octants", "map": grid}


def main():
    layout_path, out = sys.argv[1], sys.argv[2]
    lay = json.load(open(layout_path)); px = lay["pixels"]; n = len(px)
    os.makedirs(out, exist_ok=True)
    for name, m in [("ledmap.json", octocat_2d(px)), ("ledmap1.json", ring_and_cat(px, lay["regions"])), ("ledmap2.json", octants(px))]:
        assert sorted(i for i in m["map"] if i >= 0) == list(range(n)), f"{name}: not every LED placed exactly once"
        json.dump(m, open(os.path.join(out, name), "w"), separators=(",", ":"))
        print(f"{name:13} {m['n']:11} {n} LEDs placed")


if __name__ == "__main__":
    main()
