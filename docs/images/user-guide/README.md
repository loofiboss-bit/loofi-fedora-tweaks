# User Guide Screenshot Catalog

Canonical screenshot assets for user-facing docs.

**Last verified**: v18.0.0 "Haven" release on 2026-07-22

**Status**: These assets remain available for stable user-doc links. The
complete Home, Updates, Install App, Troubleshoot, Cleanup, and Action Center
set must be recaptured on Fedora 44 KDE Wayland after the planned workflow UI
changes; older captures are not physical qualification for the current
release.

## Current Files

- `home-dashboard.png` -- Home
- `upgrade-assistant.png` -- Software & Updates > Maintenance > Upgrade Assistant
- `release-readiness.png` -- Home > Release Readiness
- `release-readiness-advanced.png` -- Release Readiness advanced details
- `system-monitor.png` -- System > Performance and processes
- `maintenance-updates.png` -- Software & Updates > Maintenance updates workflow
- `network-overview.png` -- Network tab overview
- `security-privacy.png` -- Security & Privacy tab
- `ai-lab-models.png` -- Advanced route > AI Lab models view
- `community-legacy-extensions.png` -- Advanced > Local Profiles > Legacy Extensions
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
3. Use the default dark theme (Abyss Dark through the semantic theme engine).
4. Navigate to each tab listed above and capture the screenshot.
5. Save with the **same filename** to avoid breaking doc references.
6. Optimize images: `optipng -o5 *.png` or similar.
7. Verify rendering in Markdown preview before merging.

### Tabs to screenshot (priority order)

| Screenshot | Navigate To | Notes |
|------------|-------------|-------|
| `home-dashboard.png` | Home | Show canonical Home and the six-destination Standard sidebar |
| `upgrade-assistant.png` | Software & Updates > Maintenance > Upgrade Assistant | Show Fedora 44 stable and Fedora 45 preview planning |
| `release-readiness.png` | Home > Release Readiness | Show grouped beginner readiness findings |
| `release-readiness-advanced.png` | Home > Release Readiness > Advanced | Show command/recommendation metadata |
| `system-monitor.png` | System > Performance | Show CPU/RAM/process data |
| `maintenance-updates.png` | Software & Updates > Maintenance > Updates | Show update workflow |
| `network-overview.png` | Network & Security > Network | Show connections view |
| `security-privacy.png` | Network & Security > Security | Show security score |
| `ai-lab-models.png` | Search/direct route > AI Lab | Show models list |
| `community-legacy-extensions.png` | Advanced > Local Profiles > Legacy Extensions | Show local profiles and the non-executing legacy extension inventory |
| `settings-appearance.png` | Settings > Appearance | Show appearance options |

### Additional screenshots to consider next

- `extensions-tab.png` -- Manage > Extensions (new in v37)
- `backup-tab.png` -- Manage > Backup (new in v37)
- `diagnostics-tab.png` -- Developer > Diagnostics
- `agents-tab.png` -- Automation > Agents
