#!/usr/bin/env python3
"""Control the Octolamp (WLED) over its HTTP JSON API. Stdlib only.

Host: $OCTOLAMP_HOST, else octolamp.local resolved over IPv4 (a plain lookup
stalls ~5 s on macOS while IPv6 mDNS times out).
"""
import argparse, difflib, json, os, re, socket, sys, time, urllib.request

NAME = os.environ.get("OCTOLAMP_HOST", "octolamp.local")

COLORS = {
    "red": (255, 0, 0), "green": (0, 255, 0), "blue": (0, 0, 255), "white": (255, 255, 255),
    "warm": (255, 120, 20), "yellow": (255, 200, 0), "amber": (255, 110, 0), "orange": (255, 60, 0),
    "purple": (140, 0, 255), "violet": (90, 0, 255), "pink": (255, 40, 120), "magenta": (255, 0, 255),
    "cyan": (0, 255, 255), "teal": (0, 180, 120), "lime": (120, 255, 0), "off": (0, 0, 0), "black": (0, 0, 0),
    "github-green": (46, 160, 67), "github-purple": (130, 80, 223), "github-red": (218, 54, 51),
    "github-orange": (219, 109, 40), "github-blue": (47, 129, 247),
}

_host = None
def host():
    global _host
    if _host is None:
        try: _host = socket.getaddrinfo(NAME, 80, socket.AF_INET)[0][4][0]
        except OSError: sys.exit(f"can't resolve {NAME} - is the lamp on Wi-Fi? (set OCTOLAMP_HOST=<ip> to override)")
    return _host

def api(path, body=None, timeout=5):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"http://{host()}{path}", data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r: return json.loads(r.read() or b"{}")
    except OSError as e: sys.exit(f"lamp at {host()} not answering {path}: {e}")

def state(body): return api("/json/state", body)

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def layout():
    with open(os.path.join(SKILL_DIR, "references", "layout.json")) as f: return json.load(f)

# Looks set their brightness on their segments; master brightness is left for the user / the evening timer.
CONTRIB_BRI = 72                       # contributions segment brightness: full ring at level 4 peaks ~750 mA
WEATHER_PRESET = 2
DAY_PRESET, EVENING_PRESET = 7, 8      # brightness-only presets the evening timers apply
IDLE_MA = 218                          # power estimate with every LED off

_cells = {}
def cell_of():
    """Physical LED -> index WLED uses for per-pixel writes. None in 1D (identity); a grid cell in 2D mode."""
    if "map" not in _cells:
        lm = api("/ledmap.json") if api("/json/info")["leds"].get("matrix") else None
        _cells["map"] = {phys: cell for cell, phys in enumerate(lm["map"]) if phys >= 0} if lm else None
    return _cells["map"]

CALIBRATE = True
_gain = {}
def gain(led):
    """Per-LED brightness correction measured from an all-white photo (references/calibration.json)."""
    if not _gain:
        try:
            with open(os.path.join(SKILL_DIR, "references", "calibration.json")) as f:
                _gain.update({int(k): v for k, v in json.load(f)["gains"].items()})
        except OSError: _gain[-1] = 1.0
    return _gain.get(led, 1.0) if CALIBRATE else 1.0

_segs = {}
def paint(colors, clear=False, seg=0):
    """colors: {physical LED: [r,g,b]} -> one per-pixel write, correct in 1D and 2D mode.

    WLED wipes per-pixel data when the effect changes in the same request, so the first
    paint over a running effect switches to Solid on its own and only then writes pixels.
    """
    cells = cell_of()
    if seg not in _segs:
        s = next(x for x in api("/json/state")["seg"] if x["id"] == seg)
        if s["fx"] != 0:
            state({"seg": [{"id": seg, "fx": 0}]}); time.sleep(0.05)
        _segs[seg] = s
    s = _segs[seg]
    ops = []
    if clear:
        n = (s["stop"] - s["start"]) * ((s.get("stopY", 1) - s.get("startY", 0)) if cells else 1)
        ops += [0, n, "000000"]
    for led, rgb in sorted(colors.items()):
        g = gain(led)
        ops += [cells[led] if cells else led - s["start"], "%02x%02x%02x" % tuple(min(255, round(v * g)) for v in rgb)]
    return state({"on": True, "transition": 0, "seg": [{"id": seg, "i": ops, "bri": 255}]})

FULL = [{"id": 0, "start": 0, "stop": 24, "startY": 0, "stopY": 24, "n": "", "on": True, "pal": 0, "bri": 255,
         "col": [[255, 255, 255], [0, 0, 0], [0, 0, 0]]}] + [{"id": i, "stop": 0} for i in range(1, 32)]

def use_layout(n):
    """Switch WLED's active ledmap (0 = Octocat-shaped 2D map, 1 = ring+cat strips) and reset segments to fit."""
    st = api("/json/state")
    if st.get("ledmap", 0) != n:
        state({"ledmap": n}); time.sleep(0.3); _cells.clear(); _segs.clear()
        if n == 0 and api("/json/info")["leds"].get("matrix"): state({"seg": FULL})
    return st

def restore(snap):
    if snap.get("ledmap", 0) != api("/json/state").get("ledmap", 0):
        state({"ledmap": snap.get("ledmap", 0)}); time.sleep(0.3)
    state(restorable(snap))

def upload(name, data):
    boundary = "----octolamp%d" % int(time.time() * 1000)
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"data\"; filename=\"/{name}\"\r\n"
            f"Content-Type: application/json\r\n\r\n").encode() + data + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(f"http://{host()}/upload", data=body,
                                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=10) as r: return r.read().decode()

def reboot_and_wait():
    try: api("/json/state", {"rb": True}, timeout=3)
    except SystemExit: pass
    time.sleep(6)
    for _ in range(40):
        try:
            with urllib.request.urlopen(f"http://{host()}/json/info", timeout=2) as r: return json.loads(r.read())
        except OSError: time.sleep(1)
    sys.exit("lamp did not come back after reboot")

def parse_color(s):
    s = s.strip().lower()
    if s in COLORS: return list(COLORS[s])
    if re.fullmatch(r"#?[0-9a-f]{6}", s): s = s.lstrip("#"); return [int(s[i:i + 2], 16) for i in (0, 2, 4)]
    if re.fullmatch(r"\d{1,3},\d{1,3},\d{1,3}", s): return [min(255, int(v)) for v in s.split(",")]
    sys.exit(f"unknown colour {s!r}: use a name ({', '.join(sorted(COLORS))}), #rrggbb, or r,g,b")

def parse_bri(s):
    s = s.strip()
    return max(0, min(255, round(float(s[:-1]) * 2.55) if s.endswith("%") else int(s)))

def lookup(kind, query):
    names = api(f"/json/{'eff' if kind == 'effect' else 'pal'}")
    if query.isdigit() and int(query) < len(names): return int(query), names[int(query)]
    norm = lambda n: re.sub(r"[^a-z0-9&]", "", n.lower())
    table = {norm(n): i for i, n in enumerate(names) if n not in ("RSVD", "-")}
    q = norm(query)
    if q in table: return table[q], names[table[q]]
    close = difflib.get_close_matches(q, table, n=1, cutoff=0.6)
    if close: return table[close[0]], names[table[close[0]]]
    sys.exit(f"no {kind} like {query!r}; run `lamp.py {kind}s` to list them")

def seg_ids(args):
    if args.seg is not None: return [args.seg]
    return [s["id"] for s in api("/json/state")["seg"]] or [0]

def describe():
    d = api("/json"); st, info = d["state"], d["info"]
    eff, pal = d.get("effects", []), d.get("palettes", [])
    out = {"on": st["on"], "brightness": st["bri"], "preset": st.get("ps"),
           "leds": info["leds"]["count"], "power_mA": f'{info["leds"]["pwr"]}/{info["leds"]["maxpwr"]}',
           "uptime_s": info["uptime"], "ip": info["ip"], "version": info["ver"], "segments": []}
    for s in st["seg"]:
        out["segments"].append({"id": s["id"], "leds": f'{s["start"]}-{s["stop"] - 1}', "on": s["on"],
            "effect": eff[s["fx"]] if s["fx"] < len(eff) else s["fx"], "speed": s["sx"], "intensity": s["ix"],
            "palette": pal[s["pal"]] if s["pal"] < len(pal) else s["pal"],
            "colors": ["#%02x%02x%02x" % tuple(c[:3]) for c in s["col"]]})
    return out

def restorable(snap):
    keep = {k: v for k, v in snap.items() if k in ("on", "bri", "transition", "seg", "mainseg")}
    # drop segments that didn't exist before, keep the rest exactly as they were
    ids = {s["id"] for s in snap["seg"]}
    keep["seg"] = snap["seg"] + [{"id": i, "stop": 0} for i in range(32) if i not in ids]
    return keep

def main():
    p = argparse.ArgumentParser(description="Control the Octolamp (WLED).")
    p.add_argument("--seg", type=int, help="segment id to target (default: all segments)")
    p.add_argument("--raw", action="store_true", help="skip the per-LED brightness calibration (for test patterns)")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status", help="what the lamp is showing")
    sub.add_parser("on"); sub.add_parser("off"); sub.add_parser("toggle")
    a = sub.add_parser("bri", help="brightness 0-255 or N%%"); a.add_argument("value")
    a = sub.add_parser("color", help="solid colour(s): primary [secondary] [tertiary]"); a.add_argument("colors", nargs="+")
    a = sub.add_parser("effect", help="run an effect by name or id")
    a.add_argument("name"); a.add_argument("--speed", type=int); a.add_argument("--intensity", type=int)
    a.add_argument("--palette"); a.add_argument("--colors", nargs="+")
    a = sub.add_parser("palette", help="set the palette by name or id"); a.add_argument("name")
    sub.add_parser("effects", help="list effects"); sub.add_parser("palettes", help="list palettes")
    sub.add_parser("presets", help="list saved presets")
    a = sub.add_parser("preset", help="load a preset by id or name"); a.add_argument("which")
    a = sub.add_parser("save-preset", help="save the current look"); a.add_argument("id", type=int); a.add_argument("name")
    a = sub.add_parser("pixels", help='paint LEDs, e.g. "0-9:red,10-19:#00ff00,55:white" (indexes 0-based, ranges inclusive)')
    a.add_argument("spec"); a.add_argument("--clear", action="store_true", help="turn every other LED off first")
    a = sub.add_parser("flash", help="blink a colour, then put the previous look back")
    a.add_argument("color"); a.add_argument("--times", type=int, default=3); a.add_argument("--on-ms", type=int, default=350)
    a.add_argument("--off-ms", type=int, default=250)
    a = sub.add_parser("nightlight", help="fade off over N minutes"); a.add_argument("minutes", type=int)
    sub.add_parser("regions", help="list named regions of the lamp")
    a = sub.add_parser("region", help="colour named regions, e.g. region head,tail red")
    a.add_argument("names"); a.add_argument("color"); a.add_argument("--only", action="store_true", help="turn every other LED off")
    a = sub.add_parser("wave", help="sweep a band of colour across the lamp's shape, then restore the previous look")
    a.add_argument("color"); a.add_argument("--dir", default="up", choices=["up", "down", "left", "right", "out", "in"])
    a.add_argument("--seconds", type=float, default=2.5); a.add_argument("--width", type=float, default=0.25)
    a.add_argument("--times", type=int, default=1); a.add_argument("--keep", action="store_true", help="don't restore afterwards")
    a = sub.add_parser("animate", help="run a Mac-driven animation from animations.py, then restore the previous look")
    a.add_argument("name", nargs="?", help="omit to list animations"); a.add_argument("--seconds", type=float, default=30)
    a.add_argument("--fps", type=float, default=20); a.add_argument("--keep", action="store_true", help="leave the last frame showing")
    a = sub.add_parser("weather", help="colour the calm ring + breathing cat look by the current weather (cold=blue, hot/sunny=amber)")
    a.add_argument("--dry-run", action="store_true", help="show the weather and colours, don't touch the lamp")
    a.add_argument("--if-active", action="store_true", help="only update if the weather look is already showing (for scheduled runs)")
    a.add_argument("--temp", type=float, help="pretend it feels like this many deg C (preview the scale)")
    a = sub.add_parser("github", help="show GitHub on the lamp: Actions status (ci) or today's contributions (commits)")
    gsub = a.add_subparsers(dest="gcmd", required=True)
    g = gsub.add_parser("ci", help="latest Actions run of a repo -> CI running / passed / failed preset")
    g.add_argument("repo", help="owner/name"); g.add_argument("--branch"); g.add_argument("--workflow", help="workflow file name, e.g. ci.yml")
    g.add_argument("--watch", action="store_true", help="keep checking until the run finishes")
    g.add_argument("--every", type=int, default=30, help="seconds between checks with --watch")
    g.add_argument("--max-minutes", type=float, default=45, help="give up watching after this long")
    g.add_argument("--if-active", action="store_true", help="only update if a CI look is already showing (for schedulers)")
    g.add_argument("--status", choices=["running", "passed", "failed"], help="preview a look without asking GitHub")
    g = gsub.add_parser("commits", help="today's contributions: ring fills clockwise toward a goal, cat glows the contribution-level green")
    g.add_argument("--user", help="GitHub login (default: whoever gh / GITHUB_TOKEN is signed in as)")
    g.add_argument("--goal", type=int, default=10, help="contributions for a full ring")
    g.add_argument("--if-active", action="store_true", help="only update if the contributions look is already showing")
    g.add_argument("--dry-run", action="store_true"); g.add_argument("--count", type=int, help="preview with this count")
    g.add_argument("--level", type=int, choices=range(5), help="preview with this level (0-4)")
    a = sub.add_parser("evening", help="optional evening dimming: WLED timers lower the master brightness at night (runs on the lamp)")
    a.add_argument("action", choices=["on", "off", "status", "apply"], help="apply = fix the brightness for the current time (used by the background job)")
    a.add_argument("--start", default="19:00", help="when evening starts, HH:MM (lamp's local time)")
    a.add_argument("--end", default="07:00", help="when day starts again, HH:MM")
    a.add_argument("--level", default="30%", help="evening brightness, 0-255 or N%% (day is always full)")
    a = sub.add_parser("mode", help="show or switch 1D strip / 2D Octocat mode (2D uses the photo-mapped layout)")
    a.add_argument("which", nargs="?", choices=["1d", "2d"])
    a = sub.add_parser("raw", help="POST any JSON to /json/state"); a.add_argument("json")
    a = sub.add_parser("get", help="GET any /json path, e.g. /json/info"); a.add_argument("path")
    args = p.parse_args()
    c = args.cmd
    global CALIBRATE
    CALIBRATE = not args.raw

    if c == "status": print(json.dumps(describe(), indent=1)); return
    if c in ("on", "off"): state({"on": c == "on"})
    elif c == "toggle": state({"on": "t"})
    elif c == "bri": state({"on": True, "bri": parse_bri(args.value)})
    elif c == "color":
        use_layout(0)
        cols = [parse_color(x) for x in args.colors[:3]]
        state({"on": True, "seg": [{"id": i, "fx": 0, "frz": False, "col": cols, "bri": 255} for i in seg_ids(args)]})
    elif c == "effect":
        use_layout(0)
        fx, name = lookup("effect", args.name)
        seg = {"fx": fx, "frz": False, "bri": 255}   # painted pixels freeze a segment; effects need it running
        if args.speed is not None: seg["sx"] = args.speed
        if args.intensity is not None: seg["ix"] = args.intensity
        if args.palette: seg["pal"] = lookup("palette", args.palette)[0]
        if args.colors: seg["col"] = [parse_color(x) for x in args.colors[:3]]
        state({"on": True, "seg": [dict(seg, id=i) for i in seg_ids(args)]}); print("effect:", name)
    elif c == "palette":
        pal, name = lookup("palette", args.name)
        state({"seg": [{"id": i, "pal": pal, "frz": False} for i in seg_ids(args)]}); print("palette:", name)
    elif c in ("effects", "palettes"):
        for i, n in enumerate(api(f"/json/{'eff' if c == 'effects' else 'pal'}")):
            if n not in ("RSVD", "-"): print(i, n)
        return
    elif c == "presets":
        for k, v in sorted(api("/presets.json").items(), key=lambda kv: int(kv[0])):
            if k != "0": print(k, v.get("n", "(unnamed)"))
        return
    elif c == "preset":
        presets = {k: v.get("n", "") for k, v in api("/presets.json").items() if k != "0"}
        pid = args.which if args.which in presets else next((k for k, n in presets.items() if n.lower() == args.which.lower()), None)
        if pid is None: sys.exit(f"no preset {args.which!r}; have: {presets}")
        state({"ps": int(pid)}); print("preset:", pid, presets[pid])
    elif c == "save-preset": state({"psave": args.id, "n": args.name, "ib": True, "sb": True})
    elif c == "pixels":
        use_layout(0)
        colors = {}
        for part in args.spec.split(","):
            where, col = part.rsplit(":", 1); a_, b_ = (where.split("-") + [where])[:2]
            for i in range(int(a_), int(b_) + 1): colors[i] = parse_color(col)
        paint(colors, clear=args.clear, seg=args.seg if args.seg is not None else 0)
    elif c == "flash":
        snap = api("/json/state"); col = parse_color(args.color)
        flash_seg = [{"id": s["id"], "fx": 0, "col": [col, [0, 0, 0], [0, 0, 0]], "on": True, "bri": 255} for s in snap["seg"]]
        dark_seg = [{"id": s["id"], "col": [[0, 0, 0], [0, 0, 0], [0, 0, 0]]} for s in snap["seg"]]
        try:
            for _ in range(args.times):
                state({"on": True, "bri": 255, "transition": 0, "seg": flash_seg}); time.sleep(args.on_ms / 1000)
                state({"transition": 0, "seg": dark_seg}); time.sleep(args.off_ms / 1000)
        finally:
            restore(snap)
    elif c == "regions":
        for name, leds in layout()["regions"].items(): print(f"{name:11} {len(leds):3} LEDs  {leds[0]}-{leds[-1]}")
        return
    elif c == "region":
        use_layout(0)
        regs = layout()["regions"]; col = parse_color(args.color); leds = []
        for name in args.names.split(","):
            if name not in regs: sys.exit(f"no region {name!r}; have: {', '.join(regs)}")
            leds += regs[name]
        paint({i: col for i in leds}, clear=args.only)
    elif c == "wave":
        import math
        snap = api("/json/state"); use_layout(0); col = parse_color(args.color); px = layout()["pixels"]
        def coord(p):
            d = math.hypot(p["x"] - 0.5, p["y"] - 0.5) * 2
            return {"up": 1 - p["y"], "down": p["y"], "right": p["x"], "left": 1 - p["x"], "out": d, "in": 1 - d}[args.dir]
        cs = [coord(p) for p in px]; w = args.width
        try:
            for _ in range(args.times):
                t0 = time.time()
                while (el := time.time() - t0) < args.seconds:
                    pos = -w + (1 + 2 * w) * el / args.seconds
                    paint({p["i"]: [round(v * max(0.0, 1 - abs(c - pos) / w)) for v in col] for p, c in zip(px, cs)})
                    time.sleep(0.03)
        finally:
            if not args.keep: restore(snap)
    elif c == "animate":
        import signal
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import animations
        if not args.name:
            for n, f in animations.ANIMATIONS.items(): print(f"{n:12} {(f.__doc__ or '').strip()}")
            return
        if args.name not in animations.ANIMATIONS:
            sys.exit(f"no animation {args.name!r}; have: {', '.join(animations.ANIMATIONS)}")
        frame, ctx = animations.ANIMATIONS[args.name], animations.context(layout())
        snap = api("/json/state"); use_layout(0)
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))   # `kill` restores the look too
        frames, t0 = 0, time.time()
        try:
            while (el := time.time() - t0) < args.seconds:
                paint(frame(el, ctx)); frames += 1
                time.sleep(max(0.0, t0 + frames / args.fps - time.time()))
        except KeyboardInterrupt: pass
        finally:
            if not args.keep: restore(snap)
            el = time.time() - t0
            print(f"{args.name}: {frames} frames in {el:.1f}s ({frames / max(el, 0.001):.1f} fps)" + ("" if args.keep else ", previous look restored"))
        return
    elif c == "weather":
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import weather
        cfg = weather.config()
        if args.temp is not None:
            w, line = args.temp, f"preview: feels like {args.temp:.0f} C"
        else:
            cur = weather.fetch(cfg); w = weather.warmth(cur)
            f = lambda c_: round(c_ * 9 / 5 + 32)
            line = (f'{cfg["place"]}: {f(cur["temperature_2m"])}F (feels {f(cur["apparent_temperature"])}F), '
                    f'{weather.describe(cur["weather_code"])}{", day" if cur["is_day"] else ", night"}')
        ring_cols, cat_col = weather.colours(w)
        print(f"{line} -> warmth {w:.1f} C, {weather.band(w)} | ring {ring_cols} | cat {cat_col}")
        if args.dry_run: return
        st = api("/json/state")
        active = st.get("ledmap") == 1 and st["seg"] and st["seg"][0].get("n") == "Weather ring"
        if args.if_active and not active:
            print("weather look isn't showing; left the lamp alone"); return
        two_d = bool(api("/json/info")["leds"].get("matrix"))
        if two_d and st.get("ledmap") != 1:
            state({"ledmap": 1}); time.sleep(0.5)
        cw, _ = lookup("effect", "colorwaves"); br, _ = lookup("effect", "breathe"); grad, _ = lookup("palette", "color gradient")
        base_ring = 255 * sum(gain(i) for i in layout()["regions"]["ring"]) / len(layout()["regions"]["ring"])
        base_cat = 255 * sum(gain(i) for i in layout()["regions"]["cat"]) / len(layout()["regions"]["cat"])
        saved = api("/presets.json").get(str(WEATHER_PRESET), {})
        saved_segs = [s for s in saved.get("seg", []) if s.get("stop", 1)][:2]
        k = (saved_segs[0]["bri"] / base_ring) if saved_segs and saved_segs[0].get("bri") else 0.25
        def make_look(k):
            return {"on": True, "transition": 30, "seg": [
                dict({"start": 0, "stop": 24, "startY": 0, "stopY": 3} if two_d else {"start": 0, "stop": 68}, id=0, m12=0, fx=cw, sx=40, ix=128,
                     pal=grad, col=ring_cols, frz=False, on=True, bri=max(1, round(base_ring * k)), n="Weather ring"),
                dict({"start": 0, "stop": 15, "startY": 3, "stopY": 5} if two_d else {"start": 68, "stop": 98}, id=1, m12=0, fx=br, sx=30, pal=0,
                     col=[cat_col, [0, 0, 0], [0, 0, 0]], frz=False, on=True, bri=max(1, round(base_cat * k)), n="Weather cat"),
            ] + [{"id": i, "stop": 0} for i in range(2, 32)]}
        state(make_look(k))
        time.sleep(3.5)   # let the fade from the previous look finish before measuring
        # Fit the look's own (segment) brightness so that at FULL master brightness the cat's peak breath plus the
        # ring stays under the power cap; otherwise WLED's limiter would dim the ring every time the cat breathes in.
        # Brightness is linear on this lamp, so measure at whatever master brightness is set (day or evening) and project.
        def projected_peak():   # ~12 s at 4 Hz covers at least two ~5 s breaths
            pk = max(api("/json/info")["leds"]["pwr"] for _ in range(48) if not time.sleep(0.25))
            m = max(1, api("/json/state")["bri"])
            return IDLE_MA + (pk - IDLE_MA) * 255 / m
        cap = api("/json/info")["leds"]["maxpwr"]
        proj = projected_peak()
        k_fit = max(0.08, min(1.0, k * 0.92 * (cap - IDLE_MA) / max(1, proj - IDLE_MA)))
        k_new = round(k_fit / 0.02) * 0.02
        if not (saved_segs and abs(k_new - k) <= 0.03): k = k_new        # don't re-save the preset over measurement noise
        look = make_look(k); state(look); time.sleep(1); proj = projected_peak()
        while proj >= 0.98 * cap and k > 0.1:
            k -= 0.03; look = make_look(k); state(look); time.sleep(1); proj = projected_peak()
        segs_now = [(s["col"], s["bri"]) for s in look["seg"][:2]]
        if [(s.get("col"), s.get("bri")) for s in saved_segs] != segs_now or "bri" in saved:
            # "o": store exactly this command (no master brightness), so loading it also switches to the ring+cat layout
            state(dict(look, transition=7, ledmap=1 if two_d else 0, psave=WEATHER_PRESET, n="Weather", o=True))
            note = f"saved as preset {WEATHER_PRESET}"
        else: note = "preset unchanged"
        print(f"applied: ring {look['seg'][0]['bri']}, cat {look['seg'][1]['bri']} segment brightness "
              f"(projected peak at full brightness {proj:.0f} mA, cap {cap}), {note}"); return
    elif c == "github":
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import github
        if args.gcmd == "ci":
            names = {"running": "CI running", "passed": "CI passed", "failed": "CI failed"}
            presets = {v.get("n"): int(k) for k, v in api("/presets.json").items() if k != "0"}
            missing = [n for n in names.values() if n not in presets]
            if missing: sys.exit(f"missing presets {missing}: restore wled/presets.json from the octolamp-studio repo")
            def show(stt, line):
                if stt in names:
                    cur = api("/json/state").get("ps")
                    if args.if_active and cur not in {presets[n] for n in names.values()}:
                        print(line, "| a CI look isn't showing; left the lamp alone"); return
                    if cur != presets[names[stt]]: state({"ps": presets[names[stt]]})
                    print(line, "->", names[stt])
                else: print(line, "-> nothing to show; lamp unchanged")
            if args.status: show(args.status, f"preview: {args.status}"); return
            t0 = time.time()
            while True:
                run = github.latest_run(args.repo, args.branch, args.workflow); stt = github.run_state(run)
                line = (f'{args.repo}: {run["name"]} #{run["run_number"]} on {run["head_branch"]} '
                        f'({run["status"]}{", " + run["conclusion"] if run.get("conclusion") else ""})') if run else f"{args.repo}: no workflow runs"
                show(stt, line)
                if not (args.watch and stt == "running") or time.time() - t0 > args.max_minutes * 60: break
                time.sleep(args.every)
            return
        # commits
        login = args.user or github.viewer_login()
        if not login and args.count is None: sys.exit("say whose contributions: --user LOGIN (or sign in with gh / set GITHUB_TOKEN)")
        if args.count is not None:
            count, level, src = args.count, (args.level if args.level is not None else min(4, (args.count + 2) // 3)), "preview"
        else:
            count, level, src = github.contributions_today(login)
        print(f"{login or 'preview'}: {count} contribution(s) today, level {level}/4 ({src}) -> ring {min(count, args.goal)}/{args.goal}")
        if args.dry_run: return
        st = api("/json/state")
        active = st.get("ledmap", 0) == 0 and st["seg"] and st["seg"][0].get("n") == "Contributions"
        if args.if_active and not active:
            print("contributions look isn't showing; left the lamp alone"); return
        import math
        # level 0-4 greens, chosen for gamma 2.2 so even level 0 reads as a faint glow rather than "off"
        GREENS = [(6, 70, 26), (20, 105, 42), (30, 160, 60), (40, 220, 80), (110, 255, 140)]
        col = list(GREENS[level]); dim = [4, 34, 12]
        lay = layout(); ring = lay["regions"]["ring"]; pos = {q["i"]: q for q in lay["pixels"]}
        clock = lambda i: math.degrees(math.atan2(pos[i]["x"] - 0.5, -(pos[i]["y"] - 0.5))) % 360
        lit = set(sorted(ring, key=clock)[:round(len(ring) * min(count, args.goal) / args.goal)])
        use_layout(0)
        paint({i: (col if i in lit else dim) for i in ring} | {i: col for i in lay["regions"]["cat"]}, clear=True)
        state({"seg": [{"id": 0, "n": "Contributions", "bri": CONTRIB_BRI}]})   # full level-4 ring stays under the cap
        return
    elif c == "evening":
        import datetime
        hm = lambda s: tuple(int(v) for v in s.split(":"))
        timers = api("/json/cfg")["timers"]["ins"]
        ours = [x for x in timers if x.get("macro") in (DAY_PRESET, EVENING_PRESET)]
        others = [x for x in timers if x not in ours]
        presets = api("/presets.json")
        now = datetime.datetime.strptime(api("/json/info")["time"], "%Y-%m-%d, %H:%M:%S")
        def evening_now(start, end):
            n, s, e = now.hour * 60 + now.minute, start[0] * 60 + start[1], end[0] * 60 + end[1]
            return (s <= n or n < e) if s > e else (s <= n < e)
        def current_schedule():
            ev = next((x for x in ours if x["macro"] == EVENING_PRESET), None); dy = next((x for x in ours if x["macro"] == DAY_PRESET), None)
            if not (ev and dy and ev.get("en") and dy.get("en")): return None
            return (ev["hour"], ev["min"]), (dy["hour"], dy["min"]), presets.get(str(EVENING_PRESET), {}).get("bri", 77)
        bri_now = api("/json/state")["bri"]
        if args.action == "status":
            sch = current_schedule()
            if not sch: print(f"evening dimming: OFF | brightness {bri_now} | lamp time {now:%H:%M}"); return
            (s, e, lvl) = sch
            print(f"evening dimming: ON {s[0]:02d}:{s[1]:02d}-{e[0]:02d}:{e[1]:02d} at brightness {lvl} ({round(lvl / 2.55)}%) | "
                  f"now {now:%H:%M} = {'evening' if evening_now(s, e) else 'day'} | brightness {bri_now}"); return
        if args.action == "apply":   # safety net: WLED timers don't fire retroactively after a reboot
            sch = current_schedule()
            if not sch: print("evening dimming is off; nothing to do"); return
            (s, e, lvl) = sch; want = lvl if evening_now(s, e) else 255
            if bri_now != want and bri_now in (255, lvl, 128):   # only correct values we (or a reboot) set, not a manual choice
                state({"bri": want}); print(f"brightness {bri_now} -> {want} ({'evening' if want == lvl else 'day'})")
            else: print(f"brightness {bri_now} ok ({'evening' if evening_now(s, e) else 'day'})")
            return
        if args.action == "off":
            api("/json/cfg", {"timers": {"ins": others}})
            sch_lvl = presets.get(str(EVENING_PRESET), {}).get("bri")
            if bri_now == sch_lvl: state({"bri": 255})
            print(f"evening dimming OFF (timers removed); brightness {api('/json/state')['bri']}"); return
        # on
        s, e, lvl = hm(args.start), hm(args.end), parse_bri(args.level)
        st = api("/json/state"); pl = st.get("pl", -1)
        need = presets.get(str(DAY_PRESET)) != {"n": "Day brightness", "bri": 255} or presets.get(str(EVENING_PRESET), {}).get("bri") != lvl
        if need:
            if pl != -1: state({"ps": DAY_PRESET}); time.sleep(1.0)   # stop the playlist first: saving presets mid-playlist can crash WLED
            state({"psave": DAY_PRESET, "n": "Day brightness", "o": True, "bri": 255}); time.sleep(1.0)
            state({"psave": EVENING_PRESET, "n": "Evening brightness", "o": True, "bri": lvl}); time.sleep(1.0)
        tm = lambda h_m, macro: {"en": 1, "hour": h_m[0], "min": h_m[1], "macro": macro, "dow": 127,
                                 "start": {"mon": 1, "day": 1}, "end": {"mon": 12, "day": 31}}
        api("/json/cfg", {"timers": {"ins": others + [tm(s, EVENING_PRESET), tm(e, DAY_PRESET)]}, "def": {"bri": 255}})
        want = lvl if evening_now(s, e) else 255
        state({"bri": want})
        if need and pl != -1: time.sleep(0.5); state({"ps": pl})   # resume the playlist that was showing
        print(f"evening dimming ON: {s[0]:02d}:{s[1]:02d}-{e[0]:02d}:{e[1]:02d} at brightness {lvl} ({round(lvl / 2.55)}%); "
              f"lamp time {now:%H:%M} -> {'evening' if want == lvl else 'day'}, brightness {want}"); return
    elif c == "mode":
        info = api("/json/info"); m = info["leds"].get("matrix")
        if not args.which:
            print("2D" if m else "1D", f"({m['w']}x{m['h']} grid, {len(layout()['pixels'])} physical LEDs)" if m else "(plain strip)"); return
        if args.which == "2d":
            with open(os.path.join(SKILL_DIR, "assets", "ledmap.json"), "rb") as f: print("ledmap:", upload("ledmap.json", f.read()))
            form = b"SOMP=1&MPC=1&P0W=24&P0H=24&P0X=0&P0Y=0"
        else:
            n = len(layout()["pixels"])
            print("ledmap:", upload("ledmap.json", json.dumps({"map": list(range(n))}).encode()))
            form = b"SOMP=0"
        urllib.request.urlopen(urllib.request.Request(f"http://{host()}/settings/2D", data=form), timeout=10).read()
        info = reboot_and_wait(); m = info["leds"].get("matrix")
        print("now:", "2D" if m else "1D", m or "", "| LEDs", info["leds"]["count"]); return
    elif c == "nightlight": state({"on": True, "nl": {"on": True, "dur": args.minutes, "mode": 1, "tbri": 0}})
    elif c == "raw": print(json.dumps(state(json.loads(args.json))))
    elif c == "get": print(json.dumps(api(args.path), indent=1)); return
    s = describe()
    print(f'on={s["on"]} bri={s["brightness"]} power={s["power_mA"]}mA ' +
          " | ".join(f'seg{g["id"]} {g["effect"]} {g["colors"][0]} pal={g["palette"]}' for g in s["segments"]))

if __name__ == "__main__":
    main()
