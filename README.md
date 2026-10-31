# Octolamp Studio

Presets, 2D layouts, a Claude Code skill and a mapping kit for the
[Octolamp](https://github.com/martinwoodward/octolamp) — the 3D-printed,
WLED-powered GitHub Octocat lamp by Martin Woodward.

The stock Octolamp is a strip of LEDs running WLED's 1D effects. This project
turns it into something that knows its own shape:

- **2D Octocat mode**: every LED mapped to where it physically sits, so WLED's
  2D effects (Octopus, Black Hole, Polar Lights, Swirl…) render across the actual
  picture instead of sliding along a strip.
- **Shape-aware layouts**: ring vs cat, and 8 clock-face pie slices, so the ring
  and the cat can run different effects and looks can sweep clockwise.
- **Ready-made looks**: a calm breathing look coloured by the live weather, a
  two-tone left/right crossfade cycle, and rainbow slices that fill clockwise.
  They're WLED presets and playlists, so they run on the lamp with no computer
  attached.
- **GitHub on your desk**: the lamp shows a repo's Actions status (amber
  meteor while it builds, green when it passes, a red heartbeat when it fails),
  or today's contributions: the ring fills toward a daily goal and the cat glows
  your contribution-graph green, brighter the more you ship.
- **Evening dimming (optional)**: `lamp.py evening on` dims the lamp from 7 pm
  to 7 am (times and level adjustable), using timers on the lamp itself, and
  it works with every look.
- **A Claude Code skill**: ask in plain words — "make it cozy", "light the
  octocat's tail purple", "do a green wave from the bottom when CI passes" — and
  Claude drives the lamp, including spatial animations and the weather look.
- **A mapping and calibration kit**: find your strip's data pin, map every LED
  from a handful of phone photos, verify the map, and even out brightness.

## What's in here

| Path | What it is |
|---|---|
| [`wled/`](wled/) | `presets.json` and the three ledmaps, plus setup notes for WLED (2D mode, power, security) |
| [`skill/octolamp/`](skill/octolamp/) | The Claude Code skill: `SKILL.md`, `scripts/lamp.py` (CLI), animations, weather |
| [`tools/`](tools/) | Mapping and calibration: test patterns, ledmap builder, photo analysis |
| [`docs/`](docs/) | [Mapping your lamp](docs/mapping.md) · [Brightness calibration](docs/calibration.md) · [Lessons learned](docs/lessons-learned.md) |
| [`examples/`](examples/) | A macOS LaunchAgent that refreshes the weather look every 30 minutes |

## Quick start

You need an assembled Octolamp running WLED on your Wi-Fi (follow the original
[build instructions](https://github.com/martinwoodward/octolamp)), reachable as
`octolamp.local` (set WLED's mDNS name, or use `OCTOLAMP_HOST=<ip>`).

1. **Does your lamp match the reference build?** It has 98 LEDs, and the strip
   route is in the [skill's shape table](skill/octolamp/SKILL.md#the-lamps-shape).
   Every lamp is stuck by hand, so yours probably differs. If it does, map it
   first ([docs/mapping.md](docs/mapping.md)); it takes about 8 photos and gives
   you your own `layout.json` and ledmaps.
2. **Install the Claude skill** (optional, but it's the easiest way to drive
   everything):
   ```bash
   git clone https://github.com/xsloba/octolamp-studio.git
   mkdir -p ~/.claude/skills
   ln -s "$PWD/octolamp-studio/skill/octolamp" ~/.claude/skills/octolamp
   python3 -I ~/.claude/skills/octolamp/scripts/lamp.py status
   ```
   The CLI is plain Python 3 standard library, with nothing to pip-install.
3. **Switch on 2D mode and the layouts**:
   ```bash
   python3 -I ~/.claude/skills/octolamp/scripts/lamp.py mode 2d
   ```
   This uploads `ledmap.json` and sets WLED's 2D mode (the lamp reboots). Upload
   `ledmap1.json` and `ledmap2.json` too (see [wled/README.md](wled/README.md)),
   then reboot once more.
4. **Load the presets** from `wled/presets.json` (WLED → Config → Security &
   Updates → Restore presets).
5. **Weather look**: copy `skill/octolamp/config.example.json` to
   `config.json`, set your city's latitude and longitude, and run
   `lamp.py weather`.

Then try `lamp.py effect octopus`, `lamp.py wave github-green --dir up`,
`lamp.py animate signature`, `lamp.py github ci owner/repo --watch` or
`lamp.py github commits`.

## Contributing

New animations, presets, palettes and mappings of other builds are very
welcome. Animations are one function each in
[`skill/octolamp/scripts/animations.py`](skill/octolamp/scripts/animations.py).
Mappings of other lamps (a `layout.json` plus how many LEDs and which pin) help
everyone check the tools against more than one build. Please don't commit
photos of your room or your WLED `cfg.json`, which contains your Wi-Fi name.

## Credits and licences

- The **Octolamp** hardware design is by [Martin Woodward](https://github.com/martinwoodward/octolamp)
  and is licensed for **non-commercial use only**. This repo contains no model
  files.
- The **invertocat** logo belongs to GitHub; see the
  [GitHub logo guidelines](https://github.com/logos).
- [WLED](https://kno.wled.ge/) does the heavy lifting on the lamp.
- Weather data by [Open-Meteo](https://open-meteo.com/) (free, no key).
- The code and documentation in this repository are MIT-licensed. See [LICENSE](LICENSE).
