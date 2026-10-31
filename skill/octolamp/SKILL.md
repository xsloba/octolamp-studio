---
name: octolamp
description: Control an Octolamp — the 3D-printed GitHub Octocat lamp (github.com/martinwoodward/octolamp) running WLED on the home network (octolamp.local). Use this whenever the user mentions the octolamp, "the lamp", "my light", the Octocat light or WLED, or asks for anything a light could do: change colour or brightness, turn it on/off, run an effect, set a mood or scene ("cozy", "party mode", "spooky"), flash it as a notification, show the state of something (CI, deadlines, a timer, the weather) through the lamp, schedule it, animate it, light up part of the cat (head, ears, tail, ring), split it into halves or slices, or build an automation or script that drives it — even if they only say "make it purple" or "dim it".
---

# Octolamp

The lamp is a WLED controller driving an addressable LED strip inside an
Octocat-shaped diffuser: a ring around the cat, plus the cat itself. Everything
goes over WLED's HTTP JSON API from this computer, through one bundled script:

```bash
python3 -I ~/.claude/skills/octolamp/scripts/lamp.py <command> ...
```

Every command except `status`/`get`/the list commands prints a one-line summary
of what the lamp is showing afterwards, so you can confirm a change took effect
without a second call. The host is `$OCTOLAMP_HOST` if set, otherwise
`octolamp.local` resolved over IPv4 (a plain lookup stalls ~5 s on macOS while
IPv6 mDNS times out).

## This lamp's profile

The files in `references/` and `assets/` describe one specific lamp; the ones
shipped in the repo are the **reference build**:

- ESP32 running WLED 16.x, data on **GPIO33**, **98 LEDs** (WS2812B, GRB).
- WLED in **2D mode** on a 24×24 grid shaped like the Octocat (`assets/ledmap.json`).
- `references/layout.json`: every LED's position and region, mapped from photos.
- `references/calibration.json`: per-LED brightness gains measured from a photo.

Every Octolamp is stuck by hand, so LED counts (99–105 in the original
instructions) and strip routes differ. If `status` shows a different LED count
than `layout.json` has, the profile isn't for this lamp. Plain colours, effects,
presets and brightness still work, but `region`, `wave`, `animate`, the
ring+cat and slice layouts, and the calibration need the lamp re-mapped first.
Walk the user through `docs/mapping.md` in the repo; it takes about 8 photos.

## Commands

| Command | What it does |
|---|---|
| `status` | Full picture: on/off, brightness, power draw, each segment's effect, palette, colours |
| `on` / `off` / `toggle` | Power |
| `bri 40%` or `bri 100` | Brightness (0–255 or a percentage) |
| `color purple` / `color '#ff8800'` / `color 255,0,80` | Solid colour. Up to three colours (primary, secondary, tertiary) for effects that use them |
| `effect <name\|id> [--speed N] [--intensity N] [--palette NAME] [--colors C1 C2]` | Run an effect. Names are fuzzy-matched (`rainbw` → Rainbow) |
| `palette <name>` | Change the palette an effect draws from |
| `effects` / `palettes` | List what this firmware has (~216 effects, ~72 palettes on 16.x) |
| `presets` / `preset <id\|name>` / `save-preset <id> <name>` | Saved looks |
| `regions` / `region head,tail red [--only]` | Colour named parts of the Octocat; `--only` turns everything else off |
| `pixels "0-9:red,10-19:#00ff00,55:white" [--clear]` | Paint individual LEDs by strip index (0-based, ranges inclusive) |
| `flash <colour> [--times 3]` | Blink a colour, then restore the exact previous look (even multi-segment effects) |
| `wave <colour> [--dir up\|down\|left\|right\|out\|in] [--seconds 2.5] [--times N] [--keep]` | Sweep a band of colour across the lamp's real shape, then restore the previous look |
| `animate [name] [--seconds 30] [--keep]` | Run a computer-driven animation from `scripts/animations.py` (no name lists them), then restore the previous look |
| `weather [--dry-run] [--if-active] [--temp C]` | The calm look coloured by the current weather: icy blues when cold, amber/orange when hot or sunny. Saves preset 2 "Weather" |
| `github ci owner/repo [--branch B] [--workflow ci.yml] [--watch] [--if-active] [--status ...]` | Latest Actions run → preset "CI running" (amber meteor circling the ring), "CI passed" (green breathe), "CI failed" (red heartbeat cat). `--watch` follows a running build to the end |
| `github commits [--user LOGIN] [--goal 10] [--if-active] [--count N --level L]` | Today's contributions: the ring fills clockwise toward the goal, the cat glows the contribution-level green (GitHub's own 0–4 levels) |
| `evening on [--start 19:00] [--end 07:00] [--level 30%]` / `evening off` / `evening status` | Optional evening dimming: WLED timers lower the master brightness at night and restore it in the morning, on the lamp itself, whatever look is showing |
| `mode` / `mode 1d` / `mode 2d` | Show or switch between plain-strip and 2D-Octocat mode (reboots the lamp, ~15 s) |
| `nightlight <minutes>` | Fade to off over N minutes |
| `raw '<json>'` | POST anything to `/json/state` — the escape hatch for whatever the commands don't cover |
| `get /json/info` | Read any JSON endpoint |

Global flags go before the command: `--seg N` targets one segment instead of
all; `--raw` skips the brightness calibration (use it for test patterns).
Named colours: red, green, blue, white, warm, yellow, amber, orange, purple,
violet, pink, magenta, cyan, teal, lime, off, plus github-green, github-purple,
github-red, github-orange, github-blue.

## Turning requests into light

The user wants to say what they want in plain words, so translate intent rather
than asking which effect ID they mean. Pick something, apply it, and say what you
chose in one line so they can ask for a tweak. Run `effects` or `palettes` when
you need a name you're not sure exists — IDs change between WLED versions, so
match by name.

Effects that suit this lamp: **Breathe** (calm pulse), **Candle** / **Candle
Multi** (flicker), **Fire 2012**, **Aurora**, **Pacifica** (ocean), **Lake**,
**Colortwinkles**, **Twinklefox**, **Fairy**, **Sparkle**, **Lightning**,
**Fireworks**, **Meteor**, **Plasma**, **Flow**, **Heartbeat**, **Sunrise**,
**Halloween Eyes**, **Dancing Shadows**, **Rainbow**, **Chase**. Good palettes:
Ocean, Lava, Forest, Sunset, Aurora, Fire, Icefire, Pastel, Sakura, Party,
Autumn, Candy.

Some starting points:
- *Cozy / reading* → `color warm` at 40–60%, or Candle with the Fire palette.
- *Focus* → solid white or `color 255,180,120` around 50%, no motion.
- *Party* → Colortwinkles or Plasma with the Party palette, speed ~180.
- *Spooky* → Halloween Eyes, or Fire 2012 with the Lava palette.
- *Calm* → Breathe in blue or teal, speed ~60; Pacifica; or the weather look.
- *Notification* → `flash`, so whatever was showing comes back afterwards; `wave`
  for something showier (e.g. `wave github-green --dir up` when a build passes).
- *Show-off* → a 2D effect (below): **Octopus** is the obvious one for an Octocat.

**2D effects** draw across the Octocat picture, not along the strip (2D mode
only): **Octopus** (tentacles swirling out from the centre), **Black Hole**,
**Polar Lights**, **Swirl**, **Sun Radiation**, **Distortion Waves**,
**Waverly**, **Soap**, **Blobs**, **Metaballs**, **Noise2D**, **Plasma Ball**,
**Frizzles**, **Drift Rose**, **Lissajous**, **DNA**, **Julia**, **Hiphotic**,
**Colored Bursts**, **Pulser**, **Spaceships**, **Crazy Bees**, **Ghost Rider**,
**Matrix**, **Tartan**, **Game Of Life**. Ordinary 1D effects still work in 2D
mode; WLED stretches them over the grid using the segment's `m12` setting
(0 Pixels, 1 Bar, 2 Arc, 3 Corner): `raw '{"seg":[{"id":0,"m12":2}]}'` makes a
1D effect like Rainbow radiate out from the centre of the ring.

**Segments** in 2D mode are rectangles on the 24×24 grid (`start`/`stop` are
columns, `startY`/`stopY` are rows). Left and right halves, for example:
`{"seg":[{"id":0,"start":0,"stop":12,"startY":0,"stopY":24},{"id":1,"start":12,"stop":24,"startY":0,"stopY":24,"on":true}]}`.
Back to one segment: `{"seg":[{"id":0,"start":0,"stop":24,"startY":0,"stopY":24},{"id":1,"stop":0}]}`
(a `stop` of 0 deletes a segment), or load preset 1. For splits that follow the
picture (the cat vs the ring, the head vs the tail, pie slices), use `region` or
one of the extra layouts below — rectangles can't cut those shapes.

## Layouts, presets and playlists

WLED can hold several LED maps and switch at runtime with `{"ledmap": n}`:

| ledmap | File | What it's for |
|---|---|---|
| 0 | `assets/ledmap.json` (uploaded as `ledmap.json`) | The Octocat-shaped 24×24 picture: 2D effects, `region`, `wave`, `animate` |
| 1 | `assets/ledmap1.json` "Ring + cat" | Ring LEDs in rows 0–2 sorted by angle, cat LEDs in rows 3–4, so the ring and the cat can run separate effects |
| 2 | `assets/ledmap2.json` "Octants" | One row per 45° pie slice, clockwise from 12 o'clock: `start 0 stop 24 startY k stopY k+1` is slice k+1 |

- Only `ledmap.json` (0) sets the grid size, and only at boot; new ledmap files
  show up in WLED after a reboot.
- `color`, `effect`, `region`, `pixels`, `wave` and `animate` switch to layout
  0 themselves (and reset brightness, palette and colour when leaving the
  weather look); `flash`, `wave` and `animate` switch back afterwards.
- **Presets must declare their layout.** WLED doesn't store the active ledmap
  in a normally saved preset, so save layout-dependent looks as an exact command:
  `raw '{"psave":N,"n":"Name","o":true,"ledmap":1,...the full look...}'`.
- **Never re-save presets while a playlist that uses them is running.** It
  crashed and rebooted the reference lamp mid-save. Load a non-playlist look
  first (`state.pl` should be -1) and leave ~1 s between saves.
- For slow colour changes, a **playlist with long `transition`s** beats the
  Fade effect: Fade's slowest full cycle is only ~6.5 s (`65536 / (speed/8 + 10)` ms).

The repo's `wled/presets.json` ships these (check `presets` on the lamp for
what's actually installed — the user may have changed them):

| # | Name | What it does |
|---|---|---|
| 1 | Octolamp white | Solid white on layout 0 — the plain fallback |
| 2 | Weather | The calm look (below), coloured by the weather; rewritten by `weather` |
| 3 | Slices clockwise | Playlist of 16–24 on layout 2: 8 pie slices (red, orange, yellow, green, cyan, blue, violet, magenta — gamma-adjusted to stay ≥28° apart in hue on the LEDs) fade in one by one clockwise, hold, fade to dark, repeat (~10 s a round) |
| 4 / 5 / 6 | CI running / CI passed / CI failed | Layout 1 looks picked by `github ci` (amber meteor circling the ring; green breathe; red heartbeat cat) |
| 9 | Two-tone cycle | Playlist of 10–15 on layout 0: left/right halves in two colours, a new pair every 10 s with 8 s crossfades and sides alternating |

Presets 7/8 are the evening-dimming brightness presets. Free slots for new looks: 25+.

## Brightness: looks vs. day and evening

**Looks never set the master brightness.** Each preset and command puts its own
level into *segment* brightness (the power-cap fits for Weather, CI, and
contributions live there), and master brightness is left for the user and for
evening dimming. Brightness is linear on this lamp (`light.gc.bri` is 1), so
master × segment is what the LEDs get. When saving a new look, keep `"bri"` out
of the preset's top level and put levels on its segments, or it will fight the
evening timer.

**Evening dimming** (`lamp.py evening on`) is optional and off by default. It
saves two brightness-only presets: 7 "Day brightness" (`{"bri":255}`) and 8
"Evening brightness" (`{"bri":<level>}`). WLED timers apply them at the start
and end times (`/json/cfg` `timers.ins`, entries with `macro` 7 or 8; other
timers are left alone). Turning it on also sets the boot brightness to 255.
It runs on the lamp, using the lamp's NTP clock and timezone, so it works with
the computer off. Timers don't fire retroactively, though, so after a reboot
mid-evening `lamp.py evening apply` puts the right level back. The weather
LaunchAgent runs it every 30 minutes. `apply` only corrects 255, the evening
level, or the 128 boot default, never a brightness the user chose by hand.
`evening off` removes the timers and restores full brightness. Saving presets
7/8 stops a running playlist first and resumes it afterwards (saving presets
mid-playlist can crash WLED). WLED's global brightness factor
(`light.scale-bri`) looks like the obvious tool for this, but it doesn't apply
until a reboot.

## The calm look and the weather

The **calm look** runs entirely on the lamp: a slow Colorwaves gradient drifts
around the ring (segment "Weather ring", layout 1 rows 0–2) while the cat
breathes one solid colour (segment "Weather cat", rows 3–4). It's the right kind
of look for anything that should stay on for hours, unlike `animate`.

- **Its segment brightness is fitted to the power headroom.** `weather` samples
  the power estimate for ~12 s (two ~5 s breaths), projects it to full master
  brightness (brightness is linear on this lamp), and picks the highest segment
  brightness that keeps the cat's peak breath plus the ring under ~92% of the
  cap at full master brightness — above that, WLED's limiter would dim the ring
  every time the cat breathes in. It only re-saves when the fit moves by more
  than ~3%, and lets the 3 s fade-in finish before measuring.
- **Weather** (`scripts/weather.py`) uses Open-Meteo — free, no key — for the
  city-level location in `config.json` (copy `config.example.json`; it's
  git-ignored). It folds the feels-like temperature, +3 °C for daytime sun and
  −2/−4 °C for rain/fog or snow, into one "warmth" number, then slides along
  `SCALE`: icy ≤2 °C, cold 10, cool 16, mild 21, warm 26, hot ≥32.
  `weather --dry-run --temp 30` previews a band without touching the lamp.
- `--if-active` only updates when the weather look is showing, so a scheduled
  job never overrides another look the user put on. The repo's
  `examples/com.octolamp.weather.plist` is a macOS LaunchAgent that runs it every
  30 minutes (logs to `~/Library/Logs/octolamp-weather.log`). Check it with
  `launchctl print gui/$(id -u)/com.octolamp.weather` (`runs`, `last exit code`).
  Installing or removing it is persistent configuration on the user's computer —
  ask first. "No route to host" in the log means macOS Local Network privacy is
  blocking background Python from reaching the lamp; the user grants that in
  System Settings → Privacy & Security → Local Network.

## GitHub on the lamp

`scripts/github.py` reads GitHub with `$GITHUB_TOKEN`/`$GH_TOKEN`, else the
signed-in `gh` CLI (it checks only the *active* account — `gh auth status`
fails if any stored account is stale), else unauthenticated (public repos only,
60 requests/hour). Never print or log tokens.

- **`github ci`** maps the latest workflow run to a look: queued/in progress →
  "CI running", success → "CI passed", failure/timed out → "CI failed";
  cancelled/skipped change nothing. The three looks are presets (4–6 in the
  repo's `presets.json`, found by name, on layout 1). Each preset's brightness
  is fitted so its moving part never trips the power cap. Good uses: "watch my
  build" → `github ci owner/repo --watch` in the background after a push; a
  scheduler running `github ci owner/repo --if-active` so a CI look keeps
  itself current without overriding other looks. `--status running|passed|failed`
  previews a look offline.
- **`github commits`** uses GitHub's contribution calendar (signed in) for
  today's count and level — the same number and 0–4 shade as the profile graph.
  The ring fills clockwise from 12 o'clock (count / `--goal`), the cat glows that
  level's green, and even level 0 shows a faint outline. It's a painted
  picture on layout 0 (segment named "Contributions", brightness fixed at
  `CONTRIB_BRI`=72 so a full level-4 ring stays under the cap and the levels look
  different). `--if-active` refreshes it only while it's showing; refresh every
  15–30 minutes. Without sign-in it falls back to counting public events, which
  lag and undercount — say so.

## The lamp's shape

Reference-build strip order, as you face the lamp (re-map yours with
`docs/mapping.md` if it differs):

| LEDs | Where |
|---|---|
| 0–34 | **Outer ring**: starts at the bottom, just right of the cat's feet, and runs counter-clockwise (up the right side, over the top, down the left) |
| 35–39 | **Crossover**: back across the bottom under the feet |
| 40–67 | **Inner ring**: a second pass along the ring's inner wall, clockwise from the bottom left, over the top, down to the bottom right |
| 68–69 | Right leg / body |
| 70–89 | **Head**: counter-clockwise from the lower right, up through the right ear (76–78), across the top, the left ear (83–85), down the left side |
| 90–94 | **Tail**, tip to base |
| 95–97 | Left leg / body |

Named regions for `region`: ring-outer, crossover, ring-inner, ring (all three),
head (includes the ears), ears, tail, legs, cat (head + tail + legs). Because the
ring has two passes, outer and inner LEDs at the same angle light the same spot.

`references/layout.json` has every LED's position, normalised so the ring's
centre is (0.5, 0.5) and its outer LED circle has radius 0.5 (x right, y down),
plus its region. For custom spatial effects, compute a colour per LED from its
x/y, angle or distance from the centre and send frames with `paint()`
(`sys.path.insert(0, <skill>/scripts); import lamp`). `paint({led: [r,g,b]})`
handles the 1D/2D index translation and the calibration.

**Custom animations** live in `scripts/animations.py`. Each is a function
`frame(t, ctx) -> {led: [r, g, b]}`, given seconds since the start and a context
with each LED's angle around the ring, its height within the cat (0 = feet,
1 = ear tips), and the region sets. Register it in `ANIMATIONS` and
`lamp.py animate <name>` runs it. When the user asks for a new animation, add it
there instead of writing a one-off script, so it stays available (and can be
shared in the repo). Check it offline first — every frame should cover every LED
with ints 0–255 — then run it briefly on the lamp.

- **`signature`**: the ring breathes (4.5 s) in GitHub purple/blue drifting
  around the circle, the ears double-blink like a cat every 3.2 s, and a green
  wave rises from the feet to the ear tips every 2.8 s over a dim teal body.
- Animations stream at about **13–17 fps** over HTTP (WLED takes ~55 ms per
  frame), so design for slow-to-medium motion: breaths, sweeps, blinks — not
  strobing. WLED's faster DDP/UDP realtime input is deliberately switched off so
  other devices on the network can't drive the lamp; don't turn it on without asking.
- An animation runs only as long as its command does. Start long runs in the
  background with a `--seconds` limit; `kill` stops one and still restores the
  previous look. For something permanent, prefer an on-lamp look (preset or
  playlist) or suggest a scheduler — never leave an endless loop running.

## Brightness calibration

`references/calibration.json` holds a per-LED gain (0.6–1.0), measured by
lighting the lamp all one white, photographing it, and comparing the brightness
the camera saw near each LED with a common target. WLED's colour gamma (2.2) and
the camera's sRGB encoding roughly cancel, so photo-brightness ratios map
straight onto colour-value gains. `paint()` applies them to everything drawn from
the computer (regions, pixels, waves, animations); `--raw` skips them. On-lamp
looks can't use per-LED gains, so the weather look uses the mean gain as segment
brightness instead.

On the reference build: cat vs ring went from 89% → 95%, ears vs head 91% → 99%.
The tail stays ~12% darker because it was already at full drive; closing that
means lowering the target and dimming everything — ask first. `docs/calibration.md`
explains how to re-measure after any physical change.

**What software can't fix: seeing individual LEDs.** The ring shows a ~3% RMS
LED-to-LED ripple with both passes lit (~4% with either alone), so keep both
passes on for ring looks. It's geometry — LED pitch vs distance to the white
shell. Slow, smooth content hides it best; sparkle/twinkle makes it obvious.
Physical fixes are the user's call: a diffusion layer inside the ring cover
(frosted film, or 2–3 layers of baking parchment), thicker or more diffusing
prints, more distance, or a dotless addressable COB strip (then redo the LED
settings and re-map).

## How the lamp actually looks (why colours surprise people)

- **Gamma correction is on.** Mixed colours drift towards their strongest
  channel: (255,170,90) "warm white" comes out as dim orange-red, and sky blue
  and purple both land near pure blue. To get a colour you have in mind, push
  the weaker channels up, or use pure colours. Equal R=G=B stays neutral white.
- **The power cap** (850 mA on the reference build, which runs off a computer
  USB port): ~100 LEDs at full white would need ~5.4 A, so WLED scales white
  down to roughly 15%. Single colours draw a third as much and look far brighter.
  `status` shows the estimate; `850/850` means the cap is limiting.
- The diffuser blends neighbouring LEDs, so people can't count or pick out
  individual pixels. If you need their eyes to tell LEDs or regions apart, give
  each a **distinct colour** and ask what colours they see. Asking "is it
  blinking?" doesn't work: a strip that stops getting data freezes on its last
  frame, which looks the same as a slow blink.
- The cat is one hollow diffuser: a few bright LEDs in the legs tint the whole
  head, so a dark region next to a lit one won't look fully dark.
- **Painted pixels freeze the segment** (WLED stops running the effect so your
  pixels stay put). `color`, `effect`, `palette` and presets unfreeze it.
  `flash` and `wave` restore effects and presets afterwards, but not
  hand-painted pixels.
- WLED's live-view endpoint (`/json/live`) may be disabled, so you can't read
  pixel colours back. The `power` figure in `status` is a decent stand-in: each
  fully lit single-colour LED adds about 18 mA over the idle baseline (~218 mA
  on the reference build).

## Building automations

For anything recurring (CI status, deadlines, a pomodoro timer, "flash when the
build finishes"), write a small script that calls `lamp.py` and run it from a
scheduler or the user's own tooling:
- Prefer `flash` for one-off alerts (it restores the previous look). For a status
  that should *stay* visible, set it and leave it.
- Any loop you start must end on its own (a duration or a count). Run long ones
  in the background, and tell the user how to stop it.
- Connections to the lamp should time out quickly (the script uses 5 s). If the
  lamp is unreachable, report it and carry on; never retry in a tight loop.

## Leave these to the user

These either need secrets the user keeps to themselves, or can lock them out of
the lamp, so ask first or hand the step to them:
- **Hardware config** (LED pin, LED count, LED type). Changing it means uploading
  `cfg.json` through `/upload` and rebooting; `POST /json/cfg` silently ignores
  LED-output changes on WLED 16. Start from the lamp's current `/cfg.json`, not an
  old copy, so you don't drop the 2D setting. A wrong pin leaves the strip frozen.
  Never publish a `cfg.json`: it contains the Wi-Fi network name.
- **The power cap.** Don't raise it while the lamp is on computer USB — the port
  browns out and the lamp reboots. With a 5 V 2 A+ wall charger ~1800 mA is fine,
  but only once the user confirms the charger.
- **Wi-Fi, the settings PIN, and the OTA lock passphrase.** Only the user enters these.
- **The boot preset and existing presets.** Save new looks to free slots unless
  the user asks to change the existing ones.
- **Don't open the USB serial port** (`/dev/cu.usbmodem*` / `/dev/ttyUSB*`).
  Opening it resets an ESP32, and on the reference build the LED pin was
  originally misconfigured onto the UART pin, making serial useless anyway.
- **2D vs 1D mode.** `mode 1d` gives the plain strip back (useful while mapping);
  it reboots the lamp and changes how every 1D effect looks, so only switch when
  asked. Don't edit the ledmaps by hand — rebuild them from `references/layout.json`
  with the repo's `tools/build_ledmaps.py`.

## When something's off

- `can't resolve octolamp.local` or a timeout: the lamp is unplugged or off
  Wi-Fi. If it lost Wi-Fi it opens a `WLED-AP` hotspot; once the user joins it,
  WLED is at `http://4.3.2.1`. Set `OCTOLAMP_HOST=<ip>` to bypass name lookup.
- The lamp ignores commands but `status` looks right: the strip isn't receiving
  data — a wiring or pin problem, not the API. Tell the user rather than guessing;
  find the pin with a distinct colour per candidate GPIO (see `docs/mapping.md`).
- WLED API reference: https://kno.wled.ge/interfaces/json-api/
