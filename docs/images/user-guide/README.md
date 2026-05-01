# User Guide Screenshot Catalog

Canonical screenshot assets for user-facing docs.

**Last verified**: v6.0.0 "Compass"

**Status**: Screenshot references are current for v6 docs. The Release Readiness images are generated with `scripts/capture_v6_readiness_screenshots.py`.

## Current Files

- `home-dashboard.png` -- Overview/Home
- `release-readiness.png` -- Atlas Home > Release Readiness
- `release-readiness-advanced.png` -- Release Readiness advanced details
- `system-monitor.png` -- Overview/System Monitor
- `maintenance-updates.png` -- Manage/Maintenance updates workflow
- `network-overview.png` -- Network tab overview
- `security-privacy.png` -- Security & Privacy tab
- `ai-lab-models.png` -- Developer/AI Lab models view
- `community-presets.png` -- Automation/Community presets view
- `community-marketplace.png` -- Automation/Community marketplace view
- `settings-appearance.png` -- Personalize/Settings appearance

## Referenced By

- `docs/USER_GUIDE.md`
- `docs/BEGINNER_QUICK_GUIDE.md`
- `docs/ADVANCED_ADMIN_GUIDE.md`
- `README.md`

## Regeneration Instructions

Release readiness screenshots can be regenerated from real PyQt widgets:

```bash
PYTHONPATH=loofi-fedora-tweaks python3 scripts/capture_v6_readiness_screenshots.py
```

General screenshots must be captured manually on a running instance. To regenerate:

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
| `home-dashboard.png` | Overview > Home | Show health score, quick actions |
| `release-readiness.png` | Overview > Home > Release Readiness | Show grouped beginner readiness findings |
| `release-readiness-advanced.png` | Overview > Home > Release Readiness > Advanced | Show command/recommendation metadata |
| `system-monitor.png` | Overview > System Monitor | Show CPU/RAM/process data |
| `maintenance-updates.png` | Manage > Maintenance > Updates | Show update workflow |
| `network-overview.png` | Network & Security > Network | Show connections view |
| `security-privacy.png` | Network & Security > Security | Show security score |
| `ai-lab-models.png` | Developer > AI Lab | Show models list |
| `community-presets.png` | Automation > Community | Show presets tab |
| `community-marketplace.png` | Automation > Community | Show marketplace tab |
| `settings-appearance.png` | Personalize > Settings | Show appearance options |

### Additional screenshots to consider after v5

- `extensions-tab.png` -- Manage > Extensions (new in v37)
- `backup-tab.png` -- Manage > Backup (new in v37)
- `diagnostics-tab.png` -- Developer > Diagnostics
- `agents-tab.png` -- Automation > Agents
