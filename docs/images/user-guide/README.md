# User Guide Screenshot Catalog

Canonical screenshot assets for user-facing docs.

**Last verified**: v8.1.0 "Breeze"

**Status**: Screenshot filenames remain stable for v8.1 docs. Current images are generated from the real PyQt application with `scripts/capture_v8_user_guide_screenshots.py`.

## Current Files

- `home-dashboard.png` -- Home
- `release-readiness.png` -- Home > Release Readiness
- `release-readiness-advanced.png` -- Release Readiness advanced details
- `system-monitor.png` -- System & Hardware > System Monitor
- `maintenance-updates.png` -- Software & Updates > Maintenance updates workflow
- `network-overview.png` -- Network tab overview
- `security-privacy.png` -- Security & Privacy tab
- `ai-lab-models.png` -- Advanced route > AI Lab models view
- `community-presets.png` -- Advanced route > Community presets view
- `community-marketplace.png` -- Advanced route > Community marketplace view
- `settings-appearance.png` -- Desktop & Settings > Settings appearance

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

The capture script uses a temporary clean profile by default so first-run wizard, guided tour, favorites, and local experience-level settings do not affect release images. Set `LOOFI_SCREENSHOT_REAL_HOME=1` only when intentionally capturing a local user profile.

For manual verification after regeneration:

1. Launch the app: `./run.sh` or `PYTHONPATH=loofi-fedora-tweaks python3 loofi-fedora-tweaks/main.py`
2. Set the window to a consistent size (e.g., 1280x800).
3. Use the default dark theme (Abyss Dark / `modern.qss`).
4. Navigate to each tab listed above and capture the screenshot.
5. Save with the **same filename** to avoid breaking doc references.
6. Optimize images: `optipng -o5 *.png` or similar.
7. Verify rendering in Markdown preview before merging.

### Tabs to screenshot (priority order)

| Screenshot | Navigate To | Notes |
|------------|-------------|-------|
| `home-dashboard.png` | Home | Show focused sidebar and Home route cards |
| `release-readiness.png` | Home > Release Readiness | Show grouped beginner readiness findings |
| `release-readiness-advanced.png` | Home > Release Readiness > Advanced | Show command/recommendation metadata |
| `system-monitor.png` | System & Hardware > System Monitor | Show CPU/RAM/process data |
| `maintenance-updates.png` | Software & Updates > Maintenance > Updates | Show update workflow |
| `network-overview.png` | Network & Security > Network | Show connections view |
| `security-privacy.png` | Network & Security > Security | Show security score |
| `ai-lab-models.png` | Search/direct route > AI Lab | Show models list |
| `community-presets.png` | Search/direct route > Community | Show presets tab |
| `community-marketplace.png` | Search/direct route > Community | Show marketplace tab |
| `settings-appearance.png` | Desktop & Settings > Settings | Show appearance options |

### Additional screenshots to consider after v5

- `extensions-tab.png` -- Manage > Extensions (new in v37)
- `backup-tab.png` -- Manage > Backup (new in v37)
- `diagnostics-tab.png` -- Developer > Diagnostics
- `agents-tab.png` -- Automation > Agents
