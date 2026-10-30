# Brightness calibration

Even with every LED set to the same colour, some parts of the lamp look
brighter than others. On the reference build the ring was about 11% brighter
than the cat, and the ears and tail about 10% dimmer than the head.
Calibration measures this from a photo and stores a gain per LED.

## What it can and can't fix

- **Can:** broad zones (ring vs cat, head vs tail, a bright cluster where the
  strip crosses over). Measured on the reference build: cat vs ring went from
  89% to 95%, ears vs head from 91% to 99%.
- **Can't:** seeing individual LEDs through the shell. The reference ring shows
  a ~3% RMS ripple from LED to LED with both passes lit (~4% with one pass).
  That's LED spacing versus distance to the shell. The fixes are physical: a
  diffusion layer (frosted film, or 2–3 layers of baking parchment), thicker or
  more diffusing prints, more distance, or a dotless addressable COB strip.
- **Can't brighten:** gains only go down. A zone already at full drive (the
  reference tail) can only be matched by dimming everything else.

## Steps

1. Light every LED the same white with calibration off:
   `lamp.py --raw pixels '0-97:#c8c8c8' --clear` at brightness ~110.
2. Take a photo straight on, exposure turned **down** so the white isn't
   blown out (under 1% saturated pixels).
3. Measure:
   ```bash
   pip install numpy pillow
   python3 tools/uniformity.py photo.jpg skill/octolamp/references/layout.json gains.json
   ```
   It fits the ring as a circle, samples brightness around the ring and across
   its width, measures the cat near each mapped LED, and prints the broad spread
   and the LED-to-LED ripple. If the fit grabs the wrong circle (e.g. a very
   bright cat), pass a seed: `... gains.json CX CY R` in photo pixels.
4. Turn the measurement into gains: `gain = min(1, target / measured)`, with
   the target set between the dimmer zones. Save it as
   `skill/octolamp/references/calibration.json` (`{"gains": {"0": 0.82, ...}}`).
   Ask Claude to do this step if you like.
5. Check: repeat steps 1–3 with calibration **on** and compare ratios (ring vs
   cat, head vs tail), not absolute values. The phone re-exposes every photo.

Why photo brightness maps straight onto colour values: WLED applies a 2.2 gamma
to colours, and the camera's sRGB encoding roughly undoes it. So a zone that
reads 10% brighter in the photo needs a ~10% lower colour value.

`tools/ringprobe.py` is a simpler variant for comparing two halves of the ring,
e.g. outer pass on the left and inner pass on the right.
