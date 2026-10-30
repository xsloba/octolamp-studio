# Examples

## Weather refresh (macOS LaunchAgent)

`com.octolamp.weather.plist` runs `lamp.py weather --if-active` every 30
minutes and once at login. `--if-active` means it only recolours the lamp while
the Weather look is showing, so it never overrides another look you've put on.

```bash
sed "s|__HOME__|$HOME|g" examples/com.octolamp.weather.plist > ~/Library/LaunchAgents/com.octolamp.weather.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.octolamp.weather.plist
tail ~/Library/Logs/octolamp-weather.log
```

This assumes the skill is linked at `~/.claude/skills/octolamp` and that
`skill/octolamp/config.json` has your location. The first run may fail with
"No route to host" until macOS grants background Python **Local Network**
access (System Settings → Privacy & Security → Local Network).

Remove it with:

```bash
launchctl bootout gui/$(id -u)/com.octolamp.weather && rm ~/Library/LaunchAgents/com.octolamp.weather.plist
```

On Linux, the same command works from cron:
`*/30 * * * * python3 -I ~/.claude/skills/octolamp/scripts/lamp.py weather --if-active`.
