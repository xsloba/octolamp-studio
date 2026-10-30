# Tools

| Script | Needs | What it does |
|---|---|---|
| `paint.py` | stdlib | Mapping test patterns: `rainbow`, `markers K`, `markers+ K`, `stripes A B K`, `blocks4 K S1,S2,S3,S4`, `range A B HEX`. Finds the lamp via `$OCTOLAMP_HOST` or `octolamp.local` and reads the LED count from it. Use in 1D mode |
| `build_layout.py` | stdlib | The reference build's tracer: turns route anchors (ring angles per pass, cat points traced on a photo) into `layout.json`. Copy and edit it for your lamp |
| `overlay.py` | pillow | Draws a layout's LED positions over a photo so you can check the trace |
| `build_ledmaps.py` | stdlib | Builds `ledmap.json` (Octocat 2D), `ledmap1.json` (ring + cat) and `ledmap2.json` (octants) from a `layout.json` |
| `uniformity.py` | numpy, pillow | Measures brightness evenness from an all-white photo (ring spread, LED-to-LED ripple, cat zones) and proposes per-LED gains |
| `ringprobe.py` | numpy, pillow | Compares LED-dot ripple between the left and right halves of the ring |

```bash
pip install -r tools/requirements.txt   # only for the photo tools
```

See [docs/mapping.md](../docs/mapping.md) and [docs/calibration.md](../docs/calibration.md)
for the full workflow.
