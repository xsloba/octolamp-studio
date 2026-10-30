"""Weather -> colours for the calm ring + breathing cat look.

Fetches current conditions from Open-Meteo (free, no key) for the place in
../config.json, folds them into one "warmth" number, and slides along a colour
scale from icy blues (cold) to amber and orange (hot/sunny).
"""
import json, os, urllib.request

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# warmth (deg C, after the sun/rain adjustment) -> (three ring gradient colours, cat colour)
SCALE = [
    (2,  [(40, 90, 255), (120, 200, 255), (210, 235, 255)], (150, 200, 255)),   # icy
    (10, [(0, 110, 255), (0, 200, 210), (90, 140, 255)],    (70, 190, 230)),    # cold
    (16, [(0, 190, 150), (90, 150, 255), (170, 120, 255)],  (140, 170, 255)),   # cool
    (21, [(255, 160, 120), (200, 130, 255), (120, 210, 200)], (255, 210, 170)), # mild
    (26, [(255, 150, 40), (255, 90, 70), (255, 200, 90)],   (255, 160, 60)),    # warm
    (32, [(255, 50, 0), (255, 110, 0), (255, 180, 20)],     (255, 90, 10)),     # hot
]


def config():
    path = os.path.join(SKILL_DIR, "config.json")
    if not os.path.exists(path):
        raise SystemExit(f"no {path}: copy config.example.json to config.json and set your city's lat/lon")
    with open(path) as f: return json.load(f)


def fetch(cfg):
    url = ("https://api.open-meteo.com/v1/forecast?latitude=%.2f&longitude=%.2f"
           "&current=temperature_2m,apparent_temperature,weather_code,cloud_cover,is_day&timezone=auto"
           % (cfg["lat"], cfg["lon"]))
    with urllib.request.urlopen(url, timeout=10) as r: return json.loads(r.read())["current"]


def describe(code):
    if code == 0: return "clear"
    if code in (1, 2): return "partly cloudy"
    if code == 3: return "overcast"
    if code in (45, 48): return "fog"
    if 51 <= code <= 67 or 80 <= code <= 82: return "rain"
    if 71 <= code <= 77 or code in (85, 86): return "snow"
    if code >= 95: return "thunderstorm"
    return f"code {code}"


def warmth(cur):
    """Feels-like temperature, nudged warmer by daytime sun and cooler by rain, snow or fog."""
    w = cur["apparent_temperature"]; sky = describe(cur["weather_code"])
    if cur["is_day"] and sky in ("clear", "partly cloudy"): w += 3
    if sky in ("rain", "fog", "thunderstorm"): w -= 2
    if sky == "snow": w -= 4
    return w


def colours(w):
    """Interpolate the scale at warmth w -> (ring colours, cat colour)."""
    if w <= SCALE[0][0]: return [list(c) for c in SCALE[0][1]], list(SCALE[0][2])
    if w >= SCALE[-1][0]: return [list(c) for c in SCALE[-1][1]], list(SCALE[-1][2])
    for (t0, r0, c0), (t1, r1, c1) in zip(SCALE, SCALE[1:]):
        if t0 <= w <= t1:
            f = (w - t0) / (t1 - t0)
            lerp = lambda a, b: [round(a[k] + (b[k] - a[k]) * f) for k in range(3)]
            return [lerp(a, b) for a, b in zip(r0, r1)], lerp(c0, c1)


def band(w):
    return next((name for t, name in zip([6, 13, 18.5, 23.5, 29], ["icy", "cold", "cool", "mild", "warm"]) if w < t), "hot")
