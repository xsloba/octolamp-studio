"""Mapping test patterns: paint every LED of the lamp from a computed list of colours.

Usage: python3 paint.py rainbow | markers K | markers+ K | stripes A B K | blocks4 K S1,S2,S3,S4 | range A B HEX
Host: $OCTOLAMP_HOST, else octolamp.local (resolved over IPv4). Works in 1D mode, which is how
you map a lamp the first time (`lamp.py mode 1d`).
"""
import colorsys, json, os, socket, sys, urllib.request
_name = os.environ.get("OCTOLAMP_HOST", "octolamp.local")
H = "http://" + socket.getaddrinfo(_name, 80, socket.AF_INET)[0][4][0]
N = json.load(urllib.request.urlopen(H + "/json/info", timeout=5))["leds"]["count"]
def send(hexes):
    body = {"on": True, "bri": 255, "transition": 0,
            "seg": [{"id": 0, "start": 0, "stop": N, "fx": 0, "on": True, "bri": 255, "i": hexes}] + [{"id": i, "stop": 0} for i in range(1, 32)]}
    r = urllib.request.Request(H + "/json/state", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    return urllib.request.urlopen(r, timeout=5).read().decode()
def hx(rgb): return "%02x%02x%02x" % tuple(int(round(c * 255)) for c in rgb)
mode = sys.argv[1]
if mode == "rainbow":   # LED 1 red -> LED 98 violet (hue 0..0.78)
    cols = [hx(colorsys.hsv_to_rgb(0.78 * i / (N - 1), 1, 1)) for i in range(N)]
elif mode == "markers":  # every Kth LED lit in its rainbow hue, rest off
    k = int(sys.argv[2]); off = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    cols = [hx(colorsys.hsv_to_rgb(0.78 * i / (N - 1), 1, 1)) if (i - off) % k == 0 else "000000" for i in range(N)]
elif mode == "markers+":  # like markers, plus LED 0 white and the last LED always lit
    k = int(sys.argv[2])
    cols = [hx(colorsys.hsv_to_rgb(0.78 * i / (N - 1), 1, 1)) if i % k == 0 or i == N - 1 else "000000" for i in range(N)]
    cols[0] = "ffffff"
elif mode == "stripes":  # LEDs a..b lit: first block white, then alternating red/blue blocks of K; rest off
    a, b, k = int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
    cols = ["000000"] * N
    for i in range(a, b + 1):
        blk = (i - a) // k
        cols[i] = "ffffff" if blk == 0 else ("ff0000" if blk % 2 else "0000ff")
elif mode == "blocks4":  # given start indexes, blocks of K in white, red, green, blue; rest off
    k = int(sys.argv[2]); starts = [int(x) for x in sys.argv[3].split(",")]
    pal = ["ffffff", "ff0000", "00ff00", "0000ff"]
    cols = ["000000"] * N
    for s, col in zip(starts, pal):
        for i in range(s, min(s + k, N)): cols[i] = col
elif mode == "range":    # light LEDs a..b (0-based inclusive) in one colour
    a, b, col = int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
    cols = [col if a <= i <= b else "000000" for i in range(N)]
elif mode == "blocks":   # blocks of K LEDs, cycling through a palette of distinct hexes
    k = int(sys.argv[2]); pal = sys.argv[3].split(",")
    cols = [pal[(i // k) % len(pal)] for i in range(N)]
else: sys.exit("modes: rainbow | markers K [offset] | range A B HEX | blocks K hex,hex,...")
print(send(cols))
lit = [i for i, c in enumerate(cols) if c != "000000"]
print("lit:", len(lit), "LEDs", lit if len(lit) < 40 else f"{lit[0]}..{lit[-1]}")
