# WLED setup

Tested on WLED 16.0.1 (ESP32). The presets and ledmaps here are for the
**reference build** (98 LEDs). If your LED count differs, map your lamp
([docs/mapping.md](../docs/mapping.md)) and rebuild the ledmaps with
`tools/build_ledmaps.py` before uploading them.

## Files

| File | Upload as | What it does |
|---|---|---|
| `ledmaps/ledmap.json` | `/ledmap.json` | "Octocat 2D": each LED at its real position on a 24×24 grid. It contains `width`/`height`, which is what makes WLED's 2D mode take the Octocat's shape |
| `ledmaps/ledmap1.json` | `/ledmap1.json` | "Ring + cat": lets the ring and the cat run separate effects |
| `ledmaps/ledmap2.json` | `/ledmap2.json` | "Octants": 8 clock-face pie slices |
| `presets.json` | Restore presets | The looks below. Every preset names the ledmap it needs |

Upload ledmaps with `curl -F "data=@ledmap1.json;filename=/ledmap1.json" http://octolamp.local/upload`,
or WLED's file editor. **Reboot after uploading**: WLED only discovers ledmap
files at boot.

Turn on 2D mode under **Config → 2D Configuration → Strip or panel: 2D
Matrix**, or run `lamp.py mode 2d`, which does both steps.

## Presets

| # | Name | Needs |
|---|---|---|
| 1 | Octolamp white | ledmap 0 |
| 2 | Weather: ring drifts, cat breathes, colours from the weather (`lamp.py weather` updates it) | ledmap 1 |
| 3 | Slices clockwise: playlist of 16–24 | ledmap 2 |
| 4 | CI running: amber meteor circling the ring, dim amber cat | ledmap 1 |
| 5 | CI passed: ring breathes GitHub green, solid green cat | ledmap 1 |
| 6 | CI failed: deep red ring, red heartbeat cat | ledmap 1 |
| 9 | Two-tone cycle: playlist of 10–15 | ledmap 0 |
| 10–15 | Two-tone steps (left/right halves) | ledmap 0 |
| 16–24 | Clockwise slice steps (1–8 slices lit, then dark) | ledmap 2 |

`lamp.py github ci owner/repo` picks between 4–6 from a repo's latest Actions run (they're found by name, so other slots work too).

To make the weather look the power-on look, set **Config → LED Preferences →
Apply preset 2 at boot**.

## Settings that make it reliable and safe

- **Wi-Fi:** use a 2.4 GHz network on WPA2 or WPA2/WPA3 mixed (ESP32 WLED often
  won't join WPA3-only). Set the mDNS name to `octolamp`, turn on *Disable WiFi
  sleep*, set the AP to open only when there's *No connection after boot*, and
  change the AP password from `wled1234`.
- **Power:** keep the brightness limiter on. 850 mA suits a computer USB port;
  ~1800 mA suits a 5 V 2 A+ wall charger. Around 100 LEDs at full white would
  need about 5.4 A, so expect white to be capped.
- **Sync interfaces:** turn off UDP sync send/receive, E1.31/DDP/Art-Net
  realtime, Alexa, MQTT and Hue unless you use them. That's fewer open doors,
  and nothing else on the network can take over the lamp.
- **Time:** turn on NTP and set your timezone.
- **Lock it last:** set a settings PIN and an OTA lock passphrase (not the
  default `wledota`). Normal control keeps working when locked.
- **Never port-forward the lamp.** WLED's API has no authentication.
- **Don't share your `cfg.json`.** It contains your Wi-Fi network name.

## WLED quirks worth knowing

- `POST /json/cfg` silently ignores LED-output changes (pin, count) on 16.x.
  Download `/cfg.json`, edit it, and upload it back as `/cfg.json` (WLED's
  *Restore configuration*; it reboots).
- Presets saved the normal way don't remember the active ledmap. Save
  layout-dependent looks with `"o": true` and an explicit `"ledmap"`.
- Re-saving presets while a playlist that uses them is running can crash the
  ESP32. Stop the playlist first.
- If the strip doesn't react at all, the configured data pin is probably wrong.
  On the reference build it was set to GPIO1 (the UART TX pin) out of the box,
  but the strip was wired to GPIO33. [docs/mapping.md](../docs/mapping.md#0-find-the-data-pin)
  shows how to find it.
