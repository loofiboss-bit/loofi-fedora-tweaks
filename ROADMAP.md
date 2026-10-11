# Roadmap

The latest published release is [v32.8.0 Guide](https://github.com/loofiboss-bit/loofi-fedora-tweaks/releases/tag/v32.8.0). Its follow-up everyday UX and diagnostic work is implemented and merged to `master` through PR #66; it has not been assigned a new release version. No next version or release date is assigned. KDE on traditional Fedora with DNF5 remains the first automated qualification target. GUI, CLI, and saved-session compatibility remain part of each change.

## Completed work awaiting a release decision

The three stages below are complete and merged. Their qualification reports are dated evidence for the tested candidate and do not themselves publish a release. The next implementation stage is the stabilization work below.

## 1. Reliability and clearer everyday workflows

The working tree hardens older health checks so failed commands and incomplete observations cannot become a green result. Health, CLI, and support export retain explicit source state and limitations. Restore conflicts expose the saved previous value, last verified value, current value, and whether an external change or missing appearance scheme blocks restoration. Storage observations include free inodes, read-only state, and separate `/boot` where available while grouping mounts that share a filesystem. The KDE **Folder workspace** preset uses the existing profile review and verification flow.

DNF5 offline updates, exact app-origin inspection, and guided workflows retain their existing review and verification boundaries. Automated regression coverage is in place for denied authorization, persisted settings, and state interpretation. The disposable Fedora 44 KDE VM flow now covers denied Polkit, app restart with persisted setting and restoration history, and direct DNF configuration readback after restore. Two clean-overlay runs also verified saved guide progress and a Dolphin setting across real guest reboots, followed by independently checked restoration. See the completion report for exact RPM hashes and evidence boundaries.

Alternating fresh-process revision measurements, first-page construction and search fixtures are recorded in the [everyday UX completion report](docs/UX_COMPLETION_2026-10-11.md). The fixed 500-row search meets the 150 ms p95 target; the paired startup fixture found no reproducible regression above 10%. The review dialog passed light/dark/high-contrast, 100–200% scaling and enlarged-text cases on native Wayland and offscreen Qt. These targeted checks do not qualify disk-cache-cold startup, every keyboard workflow or human screen-reader use. Do not treat offscreen tests as physical desktop evidence.

## 2. Deeper troubleshooting and hardware guidance

Health and global search expose exact application-start, network, battery/energy, display/docking, input, and printer symptoms. Each check uses bounded, cancellable local observations, preserves per-field failures and missing-tool limitations, and offers the existing relevant settings or workflow destination. Application troubleshooting selects one exact RPM or Flatpak installation and reads recent error counts only after the user confirms a prior launch attempt. It never starts the selected application. Network troubleshooting separates active link, default routes, resolver configuration, and NetworkManager's reported connectivity; it sends no external test traffic. Hardware guidance reads battery/power, KScreen, input-device/KDE settings, and CUPS metadata without changing devices or queues.

The troubleshooting CLI uses the same versioned profiles and returns text or JSON. Older app and network sessions keep their original profile contract; incompatible comparisons remain not comparable. KDE energy, mouse, touchpad, and printer handoffs check the installed module before opening.

The automated evidence is bounded to its fixtures and data sources. It does not establish behavior on every Wayland setup, physical device, private print job, or real network condition. These are evidence limitations, not required manual checks or release blockers.

## 3. Continuity, printers, and personal workflows

CUPS diagnostics show service state, queue state, and the current user's pending-job count. They store no document names or printer addresses and do not print or modify queues. Existing Health sessions can be explicitly rechecked and compared; unresolved or incompatible evidence stays visible as such. Upgrade preparation now saves the selected target, dated local observations, third-party source IDs, and user-confirmed backup statements. Older observations become stale after a target change, future timestamp, or seven days; backup statements remain user attestations.

The **Folder workspace** preset configures Dolphin to reopen folders and tabs, open external folders in a new tab, and confirm before closing multiple tabs. It uses the regular profile review and independent verification.

Stage completion requires its relevant automated regressions, `just verify`, catalog and packaging checks, and RPM build. Use the isolated Fedora KDE VM suite when a change affects behavior it covers. Fresh-disk and Wayland VM runs remain optional automated checks selected according to change risk. Claims for GNOME, Atomic, physical hardware, and assistive technology are limited to the automated evidence available; no manual qualification is required for completion or release.

## Next: interaction and history reliability

- Connect Apps inventory cancellation to the existing cooperative worker callback and preserve completed source results.
- Distinguish empty saved Health history from read failures and unsupported future schemas; let users retry locally.
- Preserve Updates cancellation status when queued partial source results arrive, then restore controls when the worker finishes.
- Add automated regressions for these cases. Keep persisted sessions, CLI output, and Action Center authority unchanged.

## Published releases

- **v32.8.0 Guide** — resumable everyday workflows, guide discovery, saved progress, and read-only CLI inspection. [Release](https://github.com/loofiboss-bit/loofi-fedora-tweaks/releases/tag/v32.8.0); its [qualification report](docs/GUIDE_VERIFICATION.md) is a dated record for that release, not evidence for later changes.
- **v32.7.0 Routine** — installation comparisons, Health storage guidance, DNF5 restart advice, precise next-step navigation, and profile comparisons. [Release](https://github.com/loofiboss-bit/loofi-fedora-tweaks/releases/tag/v32.7.0).
- **v32.6.0 Personal** — broader RPM app discovery, editable profile copies, DNF source overview, and reviewed KDE controls. [Release](https://github.com/loofiboss-bit/loofi-fedora-tweaks/releases/tag/v32.6.0).
- **v32.5.0 Companion** — personal profile library, Flatpak access explanations, saved Health comparisons, screen-sharing diagnostics, and Fedora upgrade preparation. [Release](https://github.com/loofiboss-bit/loofi-fedora-tweaks/releases/tag/v32.5.0).

Earlier release history and qualification reports remain available in the [changelog](CHANGELOG.md) and `docs/`.

## Product boundaries

Keep background monitoring while views are hidden, mesh/network sharing, AI features, and a plugin marketplace out of scope. Direct battery charge-limit control, display changes, driver replacement, automatic repair, and unattended troubleshooting are also out of scope. Expand GNOME and Atomic support only when the affected workflows can be qualified.
