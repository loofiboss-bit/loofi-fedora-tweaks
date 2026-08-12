# Loofi Fedora Tweaks v25.0.4 “Proof” — Phase 0 Baseline

Status: release identity and baseline record. Historical v25.0.0–v25.0.3 tags
remain preserved; v25.0.4 is the separate Proof release identity.

## Baseline identity

| Field | Evidence |
| --- | --- |
| Checkout | `master`, clean before v25 changes |
| Baseline HEAD | `0d7314b` — `docs(release): record v24.0.0 public verification` |
| Current source version | v24.0.0 “Flow” |
| Current public release | v24.0.0, release commit `709faf837649989724b3d744b60dae538b5cec8b` |
| v25 release identity | v25.0.4 “Proof”, selected because v25.0.0–v25.0.3 are historical |
| Supported architecture | Six existing destinations; Action Center remains the sole confirmed mutation authority |
| Runtime boundary | Python 3.12+, PyQt6, traditional Fedora and Atomic Fedora contracts |

The checkout is authoritative. Historical v25 tags are preserved as immutable
lineage and are not evidence for the v25.0.4 Proof release.

## Existing safety invariants

- Host mutations are represented by registered Action Center definitions and executed through the existing `CommandFacade`.
- Command vectors are validated, never shell strings; `shell=True` and `sudo` remain prohibited.
- Every subprocess operation has a timeout and package-manager selection remains delegated to `SystemManager`.
- GUI code is presentation-only and asynchronous; domain services remain PyQt-free.
- API and daemon surfaces remain read-only with respect to host mutation.
- Verification is independent of command exit status; reboot-required and verification-failed outcomes remain explicit.
- Unknown, future, incomplete, manual-only, or unsupported metadata is fail-closed.

## Reproducible baseline verification

Command:

```text
LOOFI_IPC_MODE=disabled QT_QPA_PLATFORM=offscreen just test
```

Result on 2026-08-12:

```text
7076 passed, 61 skipped, 9 warnings, 1237 subtests passed
```

The warnings are existing PyQt thread cleanup warnings in the clipboard test; no test failed. This baseline was rootless, offscreen, and IPC-disabled.

## Required v25 evidence labels

Every later qualification report must distinguish:

- `local`: reproducible repository or offscreen evidence;
- `public`: externally published evidence from the exact release/tag/workflow;
- `blocked`: an explicit policy or environment gate prevents execution;
- `unverified`: a physical/manual claim that cannot be established rootlessly.

Physical Wayland, real camera/input, accessibility hardware, fresh Atomic installation, Polkit interaction, and reboot qualification remain `unverified` unless separately performed by an authorized human.
