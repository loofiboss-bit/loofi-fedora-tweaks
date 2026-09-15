# User Guide Screenshot Catalog

Canonical screenshot assets for user-facing docs.

**Last verified**: v29.0.1 "Utility" release candidate on 2026-09-15

**Status**: The current set is captured from the real PyQt application with an
isolated temporary profile and the offscreen backend. It verifies rendering and
route integration but does not claim physical desktop, keyboard, scaling, or
assistive-technology qualification.

## Current Files

- `home-dashboard.png` -- Home
- `install-app.png` -- curated Install catalog
- `tune-profile.png` -- editable Tune profile
- `troubleshoot.png` -- symptom-first Fix
- `maintenance-updates.png` -- System, Flatpak, and Firmware Update cards
- `activity-recovery.png` -- Activity & Recovery
- `settings-appearance.png` -- Settings > Appearance

## Referenced By

- `docs/USER_GUIDE.md`
- `docs/BEGINNER_QUICK_GUIDE.md`
- `docs/ADVANCED_ADMIN_GUIDE.md`
- `README.md`

## Regeneration Instructions

User-guide screenshots can be regenerated from real PyQt widgets:

```bash
PYTHONPATH=loofi-fedora-tweaks python3 scripts/capture_v8_user_guide_screenshots.py
```

The capture script uses a temporary clean profile by default so onboarding,
favorites, and local navigation settings do not affect release images. Wiki
pages reference the canonical repository assets instead of storing duplicate
PNG files. Set `LOOFI_SCREENSHOT_REAL_HOME=1` only when intentionally capturing
a local user profile.

For manual verification after regeneration:

1. Launch the app: `./run.sh` or `PYTHONPATH=loofi-fedora-tweaks python3 loofi-fedora-tweaks/main.py`
2. Set the window to a consistent size (e.g., 1280x800).
3. Use the semantic dark theme.
4. Navigate to each destination listed above and capture the screenshot.
5. Save with the **same filename** to avoid breaking doc references.
6. Optimize images: `optipng -o5 *.png` or similar.
7. Verify rendering in Markdown preview before merging.

### Tabs to screenshot (priority order)

| Screenshot | Navigate To | Notes |
|------------|-------------|-------|
| `home-dashboard.png` | Home | Show Fedora profile, recommendation, and four job shortcuts |
| `install-app.png` | Install | Show search, category filtering, source labels, and selection |
| `tune-profile.png` | Tune | Show the editable profile and operation availability |
| `troubleshoot.png` | Fix | Show the symptom-first starting point |
| `maintenance-updates.png` | Update | Show the three state-driven source cards |
| `activity-recovery.png` | Activity & Recovery | Show Needs you, In progress, and History |
| `settings-appearance.png` | Settings > Appearance | Show appearance options |
