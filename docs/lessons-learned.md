# Lessons learned

Things that cost real time while building this. Most of them are WLED or ESP32
behaviour that isn't obvious from the docs.

## Hardware and setup

- **The configured LED pin may be wrong out of the box.** The reference ESP32
  board shipped with WLED driving GPIO1 (the UART TX pin) while the strip was
  wired to GPIO33. Symptoms: the strip ignores every command and stays on
  whatever colour it last received, and the USB serial port only emits null
  bytes at the LED frame rate.
- **Opening the USB serial port resets an ESP32** (DTR/RTS on the CH9102
  bridge). Don't use serial to poke a running lamp.
- **ESP32 WLED often won't join a WPA3-only network.** Use WPA2 or mixed mode.
- **`octolamp.local` can stall ~5 s on macOS** while IPv6 mDNS times out.
  Resolve it over IPv4 (`socket.getaddrinfo(name, 80, AF_INET)`) and the lookup
  takes 0.2 s.
- **macOS Local Network privacy** blocks background processes (LaunchAgents)
  from reaching LAN devices until allowed. The first run fails with "No route to
  host".

## WLED 16 behaviour

- `POST /json/cfg` reports success but ignores LED-output (pin/count) changes.
  Upload a full `cfg.json` through `/upload` instead.
- A custom 2D shape only works when WLED is in 2D Matrix mode **and** the shape
  is the default `ledmap.json` with `width`/`height`. Those keys are read only
  from ledmap 0, only at boot. Extra ledmaps (`ledmap1.json`…) are discovered
  only at boot and can be switched at runtime with `{"ledmap": n}`.
- Normally saved presets don't record the active ledmap. Save with `"o": true`
  and an explicit `"ledmap"`.
- Re-saving presets while a playlist that uses them is running crashed the
  lamp mid-save.
- In one request, an effect change wipes per-pixel (`"i"`) writes. Switch to
  Solid first, then paint.
- Per-pixel writes freeze the segment (`frz`). Effects stay frozen until you
  send `"frz": false`.
- In 2D mode, per-pixel indexes are grid cells (`x + y·width`), not strip
  positions. Translate through the ledmap.
- `/json/live` may be disabled. The power estimate in `/json/info` is a usable
  read-back: ~18 mA per fully lit single-colour LED over the idle baseline.
- The Fade effect's slowest full cycle is ~6.5 s (`65536 / (speed/8 + 10)` ms).
  For slow changes, use a playlist with long transitions.

## Light and colour

- **Gamma 2.2 on colours** makes mixed colours drift toward their strongest
  channel: "warm white" turns orange, and sky blue and purple both land near
  pure blue. Pick colours by their on-LED hue (apply the gamma before
  comparing).
- **Brightness is linear** (`light.gc.bri` = 1) even though colours are
  gamma-corrected, so master × segment brightness is what the LEDs get. That
  lets looks keep their power-cap levels on segments and leaves master
  brightness free for day/evening dimming.
- **The global brightness factor (`light.scale-bri`) doesn't apply live.**
  `POST /json/cfg` stores it, but it only takes effect after a reboot. WLED
  **timers do apply live** through `/json/cfg`, and firing a brightness-only
  preset (`{"bri": N}` saved with `"o": true`) dims whatever look is showing.
  Timers don't fire retroactively after a reboot, though.
- **The power limiter couples everything.** If one part of a look pulses (a
  breathing cat) while the total is near the cap, WLED dims everything else in
  time with it. Keep the peak under the cap.
- **Measure power over a full cycle** (≥ 2 breaths) and only after the
  transition finishes, or the previous look skews the reading.
- Through the diffuser, people can't count LEDs. Use a distinct colour per
  thing you need told apart.

## Streaming from a computer

- WLED takes ~50–57 ms per HTTP JSON frame regardless of content, so streamed
  animations top out around 13–17 fps. The faster DDP/UDP path means enabling
  realtime receive, which lets anything on the network drive the lamp. The
  reference build leaves it off.
