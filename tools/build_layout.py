"""Turn the photo-mapping results into per-LED positions + regions for the 98-LED Octolamp.

Coordinates are traced in the 1200x1600 frame of photo 1, then normalised so the ring
centre is (0.5, 0.5) and the ring's outer LED circle has radius 0.5 (x right, y down).
"""
import json, math, sys

CX, CY, R_OUT, R_IN = 605, 960, 545, 500

def ring(theta_deg, r):
    t = math.radians(theta_deg)
    return CX + r * math.cos(t), CY + r * math.sin(t)

def interp(knots, i):
    for (i0, v0), (i1, v1) in zip(knots, knots[1:]):
        if i0 <= i <= i1: return v0 + (v1 - v0) * (i - i0) / (i1 - i0)
    raise ValueError(i)

pos, region = {}, {}
# Outer ring: LED 0 just right of the feet, counter-clockwise (angle decreasing, y down), ~9.5 deg/LED
for i in range(0, 35):
    pos[i] = ring(84 - 9.5 * i, R_OUT); region[i] = "ring-outer"
# Crossover under the feet: from the bottom-left of the ring back towards the centre
for i in range(35, 40):
    pos[i] = ring(interp([(35, 118), (39, 100)], i), interp([(35, 0.97), (39, 0.92)], i) * R_OUT); region[i] = "crossover"
# Inner pass: clockwise from bottom-left, over the top, down the right (anchors from photos 4-6)
inner = [(40, 130), (45, 200), (50, 255), (64, 365), (65, 378), (67, 410)]
for i in range(40, 68):
    pos[i] = ring(interp(inner, i), R_IN); region[i] = "ring-inner"
# Cat, traced along the silhouette in photo 1
cat = {
    68: (752, 1430), 69: (745, 1265),                                   # right leg / body
    70: (780, 1140), 71: (850, 1110), 72: (905, 1062), 73: (942, 995), 74: (952, 922),   # lower right head
    75: (948, 850), 76: (932, 785), 77: (908, 705), 78: (858, 745), 79: (790, 728),    # right side, right ear
    80: (705, 718), 81: (615, 712), 82: (525, 718), 83: (440, 735), 84: (362, 695),    # top of head, left ear
    85: (352, 785), 86: (322, 862), 87: (312, 942), 88: (330, 1022), 89: (378, 1092),  # left side of head
    90: (272, 1182), 91: (322, 1222), 92: (382, 1250), 93: (442, 1270), 94: (502, 1282),  # tail, tip to base
    95: (556, 1305), 96: (575, 1395), 97: (592, 1478),                  # left leg / body
}
for i, xy in cat.items():
    pos[i] = xy
    region[i] = ("legs" if i in (68, 69, 95, 96, 97) else "tail" if 90 <= i <= 94
                 else "ears" if i in (76, 77, 78, 83, 84, 85) else "head")

assert sorted(pos) == list(range(98))
norm = lambda x, y: (round((x - CX) / (2 * R_OUT) + 0.5, 4), round((y - CY) / (2 * R_OUT) + 0.5, 4))
layout = {
    "leds": 98,
    "coords": "x right, y down; ring centre (0.5,0.5); outer LED circle radius 0.5",
    "regions": {name: [i for i in range(98) if region[i] == name or (name == "head" and region[i] == "ears")]
                for name in ["ring-outer", "crossover", "ring-inner", "head", "ears", "tail", "legs"]},
    "pixels": [{"i": i, "x": norm(*pos[i])[0], "y": norm(*pos[i])[1], "region": region[i]} for i in range(98)],
}
layout["regions"]["ring"] = layout["regions"]["ring-outer"] + layout["regions"]["crossover"] + layout["regions"]["ring-inner"]
layout["regions"]["cat"] = sorted(layout["regions"]["head"] + layout["regions"]["tail"] + layout["regions"]["legs"])
json.dump(layout, open(sys.argv[1], "w"), indent=1)
json.dump({str(i): pos[i] for i in pos}, open(sys.argv[1].replace(".json", ".px.json"), "w"))
print({k: (len(v), v[0], v[-1]) for k, v in layout["regions"].items()})
