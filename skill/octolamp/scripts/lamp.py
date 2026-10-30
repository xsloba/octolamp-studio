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

WEATHER_PRESET, WEATHER_BRI = 2, 62   # bri 62 keeps a breathing white-ish cat + ring under the 850 mA cap

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
    return state({"on": True, "transition": 0, "seg": [{"id": seg, "i": ops}]})

FULL = [{"id": 0, "start": 0, "stop": 24, "startY": 0, "stopY": 24, "n": "", "on": True, "pal": 0,
         "col": [[255, 255, 255], [0, 0, 0], [0, 0, 0]]}] + [{"id": i, "stop": 0} for i in range(1, 32)]

def use_layout(n):
    """Switch WLED's active ledmap (0 = Octocat-shaped 2D map, 1 = ring+cat strips) and reset segments to fit."""
    st = api("/json/state")
    if st.get("ledmap", 0) != n:
        state({"ledmap": n}); time.sleep(0.3); _cells.clear(); _segs.clear()
        if n == 0 and api("/json/info")["leds"].get("matrix"): state({"seg": FULL})
        if n == 0 and st.get("ledmap") == 1: state({"bri": 255})   # weather's low brightness was a power compromise, not a choice
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
        state({"on": True, "seg": [{"id": i, "fx": 0, "frz": False, "col": cols} for i in seg_ids(args)]})
    elif c == "effect":
        use_layout(0)
        fx, name = lookup("effect", args.name)
        seg = {"fx": fx, "frz": False}   # painted pixels freeze a segment; effects need it running
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
        bri = WEATHER_BRI
        ring_bri = round(255 * sum(gain(i) for i in layout()["regions"]["ring"]) / len(layout()["regions"]["ring"]))
        cat_bri = round(255 * sum(gain(i) for i in layout()["regions"]["cat"]) / len(layout()["regions"]["cat"]))
        look = {"on": True, "bri": bri, "transition": 30, "seg": [
            dict({"start": 0, "stop": 24, "startY": 0, "stopY": 3} if two_d else {"start": 0, "stop": 68}, id=0, m12=0, fx=cw, sx=40, ix=128,
             pal=grad, col=ring_cols, frz=False, on=True, bri=ring_bri, n="Weather ring"),
            dict({"start": 0, "stop": 15, "startY": 3, "stopY": 5} if two_d else {"start": 68, "stop": 98}, id=1, m12=0, fx=br, sx=30, pal=0,
                 col=[cat_col, [0, 0, 0], [0, 0, 0]], frz=False, on=True, bri=cat_bri, n="Weather cat"),
        ] + [{"id": i, "stop": 0} for i in range(2, 32)]}
        state(look)
        time.sleep(look["transition"] / 10 + 0.5)   # let the fade from the previous look finish before measuring
        # Fit brightness to the power headroom: as bright as possible while the cat's peak breath plus the
        # ring stays under the cap (otherwise WLED's limiter would dim the ring every time the cat breathes in).
        # Brightness is gamma-corrected on this lamp, so LED current ~ bri^2.2.
        def peak_mA():   # ~12 s at 4 Hz covers at least two ~5 s breaths
            return max(api("/json/info")["leds"]["pwr"] for _ in range(48) if not time.sleep(0.25))
        cap, idle = api("/json/info")["leds"]["maxpwr"], 218
        peak = peak_mA()
        if peak < cap:
            fit = bri * ((0.92 * (cap - idle)) / max(1, peak - idle)) ** (1 / 2.2)
            bri = int(max(40, min(128, fit)) // 4 * 4)
            prev = api("/presets.json").get(str(WEATHER_PRESET), {}).get("bri")
            if prev and abs(prev - bri) <= 6: bri = prev          # don't re-save the preset over measurement noise
            state({"bri": bri}); time.sleep(1); peak = peak_mA()
        while peak >= cap and bri > 24:
            bri -= 6; state({"bri": bri}); time.sleep(1); peak = peak_mA()
        saved = api("/presets.json").get(str(WEATHER_PRESET), {})
        if ([(s.get("col"), s.get("bri")) for s in saved.get("seg", [])[:2]] != [(ring_cols, ring_bri), ([cat_col, [0, 0, 0], [0, 0, 0]], cat_bri)]
                or saved.get("bri") != bri):
            # "o": store exactly this command, so loading the preset also switches to the ring+cat layout
            state(dict(look, bri=bri, transition=7, ledmap=1 if two_d else 0, psave=WEATHER_PRESET, n="Weather", o=True))
            note = f"saved as preset {WEATHER_PRESET}"
        else: note = "preset unchanged"
        print(f"applied at brightness {bri} (peak {peak} mA, cap never engaged), {note}"); return
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
