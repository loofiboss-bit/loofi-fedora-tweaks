# Roadmap

The published baseline is [v32.8.0 Guide](https://github.com/loofiboss-bit/loofi-fedora-tweaks/releases/tag/v32.8.0). The stabilization and everyday-UX work below is implemented in the current working tree and remains unreleased; no next version or release date is assigned. KDE on traditional Fedora with DNF5 is the first full qualification target; GUI, CLI, and persisted formats remain compatible.

## 1. Stabilize existing workflows — implemented locally, qualification pending

- DNF5 offline updates now offer `dnf5 offline reboot` as a separately reviewed and confirmed Action Center operation. Cancelled or denied authorization preserves the prepared run; post-reboot verification checks actual DNF5 transaction history and package health.
- Settings use `StatePaths`; custom XDG migration is atomic and retains the source file. Future schemas remain read-only, malformed values recover safely, and StateDoctor reports the issue.
- Complete structured command output is separate from bounded history/log output. Firmware and rpm-ostree JSON is limited to 1 MiB; malformed or oversized evidence remains unavailable rather than being treated as an empty update set.
- Atomic RPM layering is unavailable unless a supported preflight query path exists; the current UI explains that boundary.
- Release status and user guidance identify v32.5.0–v32.8.0 as published releases and distinguish those dated checks from this unreleased working tree.

Automated regression coverage has been added for these boundaries. On 2026-10-11, `LOOFI_IPC_MODE=disabled QT_QPA_PLATFORM=offscreen just verify` passed: 5,153 tests passed, 33 skipped, 2,066 subtests passed, and coverage was 85.53%. This is automated evidence; final acceptance still requires a disposable KDE/Fedora pass covering setting change/restore, offline update, denied Polkit, exact Flatpak removal, and verification after app restart. Record physical results separately from automated evidence.

## 2. Improve everyday UX and app insight — implemented locally, user testing pending

- Overview guide cards show the goal and next step first, disclose step details, and surface relevant failed or pending work before optional progress.
- Health leads with a concise summary, relevant observed facts, and a next action; source limitations stay in a disclosure.
- App details expose selected installation, reported origin, runtime, access, and maintenance warnings. Exact Flatpak identity and scope persist through review; a single reported DNF repo ID opens the configured-source view filtered to that exact ID.
- Guide results count only when verified evidence belongs to a compatible action family. Other links use neutral “Result linked” wording.

Validate these flows with everyday KDE users: change and restore a setting, understand an app's source, and find the next step after an update failure. This user testing remains pending. Keep GNOME and Atomic support claims within the evidence available for each workflow.

## 3. Add hardware guidance after qualification

- Add read-only battery and energy observations with checked KDE settings handoff.
- Add display and session observations with before/after comparison and existing settings links.
- Add printer and queue diagnostics only; do not change queues or send test prints until that behavior is separately qualified.

## Published releases

- **v32.8.0 Guide** — resumable everyday workflows, guide discovery, saved progress, and read-only CLI inspection. [Release](https://github.com/loofiboss-bit/loofi-fedora-tweaks/releases/tag/v32.8.0); its [qualification report](docs/GUIDE_VERIFICATION.md) is a dated record for that release, not evidence for later changes.
- **v32.7.0 Routine** — installation comparisons, Health storage guidance, DNF5 restart advice, precise next-step navigation, and profile comparisons. [Release](https://github.com/loofiboss-bit/loofi-fedora-tweaks/releases/tag/v32.7.0).
- **v32.6.0 Personal** — broader RPM app discovery, editable profile copies, DNF source overview, and reviewed KDE controls. [Release](https://github.com/loofiboss-bit/loofi-fedora-tweaks/releases/tag/v32.6.0).
- **v32.5.0 Companion** — personal profile library, Flatpak access explanations, saved Health comparisons, screen-sharing diagnostics, and Fedora upgrade preparation. [Release](https://github.com/loofiboss-bit/loofi-fedora-tweaks/releases/tag/v32.5.0).

Earlier release history and qualification reports remain available in the [changelog](CHANGELOG.md) and `docs/`.

## Product boundaries

Keep background monitoring while views are hidden, mesh/network sharing, AI features, and a plugin marketplace out of scope. Expand support for Fedora spins and Atomic desktops only when the affected workflows can be qualified.
