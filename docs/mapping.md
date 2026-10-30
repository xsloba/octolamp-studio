# Mapping your lamp

Every Octolamp's strip is stuck by hand, so the LED count and route differ from
lamp to lamp. Mapping finds where each LED physically sits. That's what makes
2D effects, regions, waves and the slice/ring layouts line up with *your* lamp.

You need a phone camera and about 30 minutes. If you use Claude Code with the
`octolamp` skill, ask *"map my octolamp"* and it will drive these steps and
read your photos. The steps below work by hand too.

**Golden rule:** the diffuser blurs neighbouring LEDs, so you can't count dots
or pick out single LEDs by eye. Every test gives each LED or block a **distinct
colour**, and you read colours off the photo. Never test with "is it blinking?":
a strip that loses its data freezes on its last frame, which looks like a slow
blink.

**Photo tips:** dim room, straight on, whole lamp in frame, no flash, the same
spot every time, and turn the exposure down so whites aren't blown out.

Map in 1D mode first (`lamp.py mode 1d`), so strip index = LED index.

## 0. Find the data pin

Skip this if the lamp already responds to colour changes.

If nothing happens when you change colours, WLED is driving the wrong GPIO. On
the reference build it shipped set to GPIO1 (the UART TX pin, which also makes
the USB serial port spew garbage), but the strip was on GPIO33.

1. Configure WLED with several outputs at once, 120 LEDs each, on a batch of
   safe candidate pins (2, 4, 5, 13, 18, 19, 21, 22, then 23, 25, 26, 27, 32,
   33, 14, 15). Skip 6–11 (flash), 16–17 if the board has PSRAM, 34–39 (input
   only), and 0/1/3.
2. **Paint each output a different colour.** One photo, or one look, tells you
   which output is connected. Narrow down the batch.
3. Upload the config with the single correct pin.

Changing LED outputs requires a `cfg.json` upload. `POST /json/cfg` ignores it.

## 1. Count the LEDs

Set a generous count (e.g. 120). Light the first N−10 LEDs in one colour, then
give each LED after that its own colour: blue, white, purple, yellow, cyan, then
red for the rest. The colours you see at the very end tell you the exact count.
LEDs beyond the real end don't exist, and LEDs past the *configured* count hold
whatever they last showed, so power-cycle the lamp before this test. Set the
count to the real number.

## 2. Trace the route

Run `tools/paint.py` with these patterns, taking a photo of each:

| Test | Command | What it shows |
|---|---|---|
| Rainbow | `paint.py rainbow` | Overall path and direction (LED 0 red → last violet) |
| First half stripes | `paint.py stripes 0 49 5` | Which LEDs are where: a white start block, then red/blue blocks of 5 |
| Second half stripes | `paint.py stripes 50 97 5` | Same for the rest |
| Four distinct blocks | `paint.py blocks4 5 30,35,40,45` | Pins down turnarounds: white, red, green, blue blocks with no overlaps |

Count blocks from the white start along the path. Expect surprises. The
reference build's ring has **two passes**: the outer wall counter-clockwise,
then the inner wall clockwise. A crossover sits under the cat's feet. The
second pass doubles back over the first, so stripes overlap on the ring; use
`blocks4` with distinct colours to untangle them.

## 3. Write `layout.json`

`tools/build_layout.py` is the reference build's tracer. It places ring LEDs
by angle (start angle and degrees per LED per pass) and cat LEDs at
coordinates traced on the photo. Copy it, change the anchors to match your
route, and run it:

```bash
python3 tools/build_layout.py my-layout.json
python3 tools/overlay.py photo.jpg my-layout.px.json overlay.jpg   # needs pillow
```

Look at `overlay.jpg`: every circle should sit on its LED.

The output format: `pixels[i] = {i, x, y, region}` with the ring centre at
(0.5, 0.5) and the outer LED circle at radius 0.5 (x right, y down), plus
`regions` (ring-outer, crossover, ring-inner, ring, head, ears, tail, legs,
cat).

## 4. Verify on the lamp

Colour every LED by its `y` coordinate (red at the top, blue at the bottom). If
the map is right, you see **level horizontal bands running straight across both
the ring and the cat**. Anything out of place shows up as a wrong colour in a
band.

## 5. Build and upload the ledmaps

```bash
python3 tools/build_ledmaps.py my-layout.json wled/ledmaps/
```

Copy `my-layout.json` to `skill/octolamp/references/layout.json`, upload the
three ledmaps (see [wled/README.md](../wled/README.md)), reboot, and run
`lamp.py mode 2d`. Then calibrate brightness ([calibration.md](calibration.md)).

Please consider sharing your `layout.json`, LED count and pin in an issue or PR.
It helps check the tools against more builds.
