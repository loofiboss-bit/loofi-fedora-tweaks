# Loofi Fedora Tweaks 36.2.0 “Blueprint”

Loofi Fedora Tweaks **36.2.0** builds on the v36.1.0 Blueprint foundation with
stability fixes, a more cohesive control-center UX, architectural cleanup, and
full Fedora 45 / KDE Plasma 6 readiness.

## Highlights

- **Stability & Packaging:** Fixed Qt/AT-SPI scroll ownership transitions across
  main shell routes (`owns_scroll = True`), removed the `.copr/Makefile` `%check`
  bypass, and aligned Fedora 44/45 support metadata across `SECURITY.md`,
  `ROADMAP.md`, and AppStream metainfo.
- **UX & Core Integration:**
  - **Overview:** Streamlined task-oriented start view with a collapsible
    hardware monitor and contextual next-step actions.
  - **Tweaks:** Clearer current-vs-target value comparison, explanation cues,
    and responsive profile search.
  - **My Fedora configuration (Blueprint):** Side-by-side comparison summary and
    quick review actions for portable `loofi.setup/v1` configurations, linked
    directly from pre/post-upgrade preparation in **Updates**.
  - **Health, Updates & Activity:** Inline recovery banners and cross-workflow
    routing between diagnostics, updates, tweaks, and execution history.
- **Architecture Consolidation:** Retired legacy compatibility shims
  (`core/profiles/*`, `ui/logs_tab.py`, `ui/performance_tab.py`,
  `cli/action_plans.py`, and `core/diagnostics/gaming_audit.py`), decomposed
  oversized hardware and shell modules below architectural budgets, and cached
  static OS/CPU inventory reads.
- **KDE Plasma 6 & Fedora 45:** Qualified Fedora 45 release target
  (`FedoraReleasePolicy.fedora45_qualified()`), added everyday KDE Plasma 6
  tweaks (`kde-touchpad-natural-scroll` and `kde-dolphin-browse-archives`
  across 84 cataloged controls), and added `--fedora-release {44,45}` support in
  the E2E VM harness.

## Installation

### Fedora COPR (`fedora-44-x86_64` and `fedora-45-x86_64`)

```bash
sudo dnf copr enable loofitheboss/loofi-fedora-tweaks
sudo dnf install loofi-fedora-tweaks
```

### Direct RPM from GitHub Releases

Download `loofi-fedora-tweaks-36.2.0-1.*.noarch.rpm` along with `SHA256SUMS.txt`
from this release, verify the checksum, and install:

```bash
sha256sum -c SHA256SUMS.txt --ignore-missing
sudo dnf install ./loofi-fedora-tweaks-36.2.0-1.*.noarch.rpm
```
