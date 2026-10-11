# Roadmap

The published baseline is [v32.8.0 Guide](https://github.com/loofiboss-bit/loofi-fedora-tweaks/releases/tag/v32.8.0). The three-stage plan below is implemented in the current working tree and remains unreleased. No next version or release date is assigned. KDE on traditional Fedora with DNF5 is the first full qualification target. GUI, CLI, and saved-session compatibility remain part of each stage.

## 1. Reliability and clearer everyday workflows

The working tree hardens older health checks so failed commands and incomplete observations cannot become a green result. Health, CLI, and support export retain explicit source state and limitations. Restore conflicts expose the saved previous value, last verified value, current value, and whether an external change or missing appearance scheme blocks restoration. Storage observations include free inodes, read-only state, and separate `/boot` where available while grouping mounts that share a filesystem. The KDE **Folder workspace** preset uses the existing profile review and verification flow.

DNF5 offline updates, exact app-origin inspection, and guided workflows retain their existing review and verification boundaries. Automated regression coverage is in place for denied authorization, persisted settings, and state interpretation. The disposable Fedora 44 KDE VM flow now covers denied Polkit, app restart with persisted setting and restoration history, and direct DNF configuration readback after restore. Verification after a system reboot remains a separate pending qualification.

Cold-start, first-page, and search latency measurements, measured responsiveness fixes, and visual/accessibility checks at light, dark, high-contrast, keyboard-only, and 100–200% scaling remain qualification tasks. Do not treat offscreen tests as physical desktop evidence.

## 2. Deeper troubleshooting and hardware guidance

Health and global search expose exact application-start, network, battery/energy, display/docking, input, and printer symptoms. Each check uses bounded, cancellable local observations, preserves per-field failures and missing-tool limitations, and offers the existing relevant settings or workflow destination. Application troubleshooting selects one exact RPM or Flatpak installation and reads recent error counts only after the user confirms a prior launch attempt. It never starts the selected application. Network troubleshooting separates active link, default routes, resolver configuration, and NetworkManager's reported connectivity; it sends no external test traffic. Hardware guidance reads battery/power, KScreen, input-device/KDE settings, and CUPS metadata without changing devices or queues.

The troubleshooting CLI uses the same versioned profiles and returns text or JSON. Older app and network sessions keep their original profile contract; incompatible comparisons remain not comparable. KDE energy, mouse, touchpad, and printer handoffs check the installed module before opening.

Automated code and compatibility checks do not qualify Wayland behavior, physical hardware, private print jobs, or real network recovery. Those checks remain pending on the target Fedora/KDE setup.

## 3. Continuity, printers, and personal workflows

CUPS diagnostics show service state, queue state, and the current user's pending-job count. They store no document names or printer addresses and do not print or modify queues. Existing Health sessions can be explicitly rechecked and compared; unresolved or incompatible evidence stays visible as such. Upgrade preparation now saves the selected target, dated local observations, third-party source IDs, and user-confirmed backup statements. Older observations become stale after a target change, future timestamp, or seven days; backup statements remain user attestations.

The **Folder workspace** preset configures Dolphin to reopen folders and tabs, open external folders in a new tab, and confirm before closing multiple tabs. It uses the regular profile review and independent verification.

Stage completion requires its automated regression suite, `just verify`, catalog and packaging checks, and RPM build. Each stage also requires its own KDE/Fedora operational qualification and visual/accessibility pass. Physical Wayland and hardware evidence is recorded separately. GNOME and Atomic support claims remain limited to individually verified workflows.

## Published releases

- **v32.8.0 Guide** — resumable everyday workflows, guide discovery, saved progress, and read-only CLI inspection. [Release](https://github.com/loofiboss-bit/loofi-fedora-tweaks/releases/tag/v32.8.0); its [qualification report](docs/GUIDE_VERIFICATION.md) is a dated record for that release, not evidence for later changes.
- **v32.7.0 Routine** — installation comparisons, Health storage guidance, DNF5 restart advice, precise next-step navigation, and profile comparisons. [Release](https://github.com/loofiboss-bit/loofi-fedora-tweaks/releases/tag/v32.7.0).
- **v32.6.0 Personal** — broader RPM app discovery, editable profile copies, DNF source overview, and reviewed KDE controls. [Release](https://github.com/loofiboss-bit/loofi-fedora-tweaks/releases/tag/v32.6.0).
- **v32.5.0 Companion** — personal profile library, Flatpak access explanations, saved Health comparisons, screen-sharing diagnostics, and Fedora upgrade preparation. [Release](https://github.com/loofiboss-bit/loofi-fedora-tweaks/releases/tag/v32.5.0).

Earlier release history and qualification reports remain available in the [changelog](CHANGELOG.md) and `docs/`.

## Product boundaries

Keep background monitoring while views are hidden, mesh/network sharing, AI features, and a plugin marketplace out of scope. Direct battery charge-limit control, display changes, driver replacement, automatic repair, and unattended troubleshooting are also out of scope. Expand GNOME and Atomic support only when the affected workflows can be qualified.
