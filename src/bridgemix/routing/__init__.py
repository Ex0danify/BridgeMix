"""
Per-application audio routing.

This package is independent of the MIDI/SysEx device control: it routes host
application audio streams onto the Bridge Cast's per-channel PulseAudio/PipeWire
sinks (Chat / Game / Music / System), the Linux equivalent of the official app's
"Applications" tab.

  store    — load/save routing rules under ~/.config/bridgemix/routing.json
  backend  — enumerate sinks/streams and move streams, via `pactl --format=json`
  monitor  — poll for stream changes and auto-apply saved rules
"""
