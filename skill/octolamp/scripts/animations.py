"""Mac-driven animations for the Octolamp, built on the photo-mapped layout.

Each animation is a function `frame(t, ctx) -> {led: [r, g, b]}` called ~20 times a
second; `t` is seconds since the start and `ctx` holds the layout pre-digested into
handy per-LED facts. Register new ones in ANIMATIONS at the bottom.
"""
import math

PURPLE = (130, 80, 223)      # github-purple
BLUE = (47, 129, 247)        # github-blue
GREEN = (60, 255, 120)       # brighter than github-green so the wave reads through the diffuser
EAR = (255, 255, 255)


def context(layout):
    """Per-LED geometry, computed once: angle around the ring centre, and height within the cat."""
    px = layout["pixels"]; regions = layout["regions"]
    cat = set(regions["cat"])
    cat_y = [p["y"] for p in px if p["i"] in cat]
    lo, hi = min(cat_y), max(cat_y)
    return {
        "pixels": px,
        "regions": {k: set(v) for k, v in regions.items()},
        "angle": {p["i"]: math.atan2(p["y"] - 0.5, p["x"] - 0.5) for p in px},
        "height": {p["i"]: (hi - p["y"]) / (hi - lo) for p in px if p["i"] in cat},   # 0 = feet, 1 = ear tips
    }


def mix(a, b, f):
    return [a[k] + (b[k] - a[k]) * f for k in range(3)]


def scale(c, f):
    return [max(0, min(255, round(v * f))) for v in c]


def signature(t, ctx):
    """Ring breathes in GitHub purple/blue, the ears blink like a cat, a green wave rises through the cat."""
    r = ctx["regions"]; out = {}

    # Ring: slow breath (4.5 s), with the purple/blue mix drifting around the circle.
    breath = 0.12 + 0.88 * (0.5 - 0.5 * math.cos(2 * math.pi * t / 4.5))
    for i in r["ring"]:
        drift = 0.5 + 0.5 * math.sin(ctx["angle"][i] + t * 0.7)
        out[i] = scale(mix(PURPLE, BLUE, drift), breath)

    # Cat body: dim teal base, plus a green band rising from the feet to the ear tips every 2.8 s.
    # The front edge is sharp and the trail behind it fades slowly, so it reads as motion upwards.
    front = (t % 2.8) / 2.8 * 1.5 - 0.2
    for i in r["cat"] - r["ears"]:
        h = ctx["height"][i]
        d = front - h
        glow = max(0.0, 1 - d / 0.45) if d >= 0 else max(0.0, 1 + d / 0.07)
        out[i] = [round(v) for v in mix((0, 28, 22), GREEN, glow)]

    # Ears: on, with a quick double blink every 3.2 s (the right ear trails the left by a beat).
    phase = t % 3.2
    for i in r["ears"]:
        lag = 0.06 if i <= 78 else 0.0          # 76-78 right ear, 83-85 left ear
        p = phase - lag
        closed = 2.55 <= p < 2.70 or 2.85 <= p < 3.00
        out[i] = [0, 0, 0] if closed else list(EAR)
    return out


ANIMATIONS = {
    "signature": signature,
}
