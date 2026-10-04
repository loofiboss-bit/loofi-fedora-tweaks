# Screenshots

Current Wayfinder captures live in `wayfinder/`. They use the real PyQt shell
with a fixed KDE fixture and isolated app settings; no desktop values change.

```bash
QT_SCALE_FACTOR=1 python3 scripts/capture_wayfinder_screenshots.py docs/images/wayfinder
QT_SCALE_FACTOR=1.5 python3 scripts/capture_wayfinder_screenshots.py /tmp/wayfinder-150
QT_SCALE_FACTOR=2 python3 scripts/capture_wayfinder_screenshots.py /tmp/wayfinder-200
```

Each run captures Tweaks, Apps, Updates, Health, Settings, and History & Undo
at 900x650 and 1280x800 logical pixels. Separate light, dark, and high contrast
Tweaks captures exercise the existing theme contract. System font selection is
unchanged; the offscreen platform's font/palette can differ from the live desktop.

These qualify rendering and navigation only. Physical interaction, actual
Dolphin window behavior, GNOME sessions, and screen readers remain separate
qualification requirements. Historical v32 images remain in `v32/`.
