# v25.0.4 “Proof” Release Qualification

**Status:** release candidate prepared for the v25.0.4 canonical workflow.
Rootless/offscreen evidence is separate from package-installation and
physical-host claims.

## Authority and boundaries

- Release target: v25.0.4 “Proof”.
- Public baseline: v24.0.0 “Flow”, release commit
  `709faf837649989724b3d744b60dae538b5cec8b`.
- Candidate baseline checkout: `0d7314b9fd086a662ba94b7dd5e51e0fbf39bd0b`.
- Historical `v25.0.0`–`v25.0.3` tags were read and preserved without
  modification. The separate `v25.0.4` identity resolves the collision without
  retargeting history.
- The release commit, push, tag, GitHub/COPR/wiki publication, package
  installation, reboot, and real-host mutation are separate gates recorded by
  the release workflow and public evidence report.

## Rootless verification contract

The maintained rootless command surface is:

```bash
LOOFI_IPC_MODE=disabled QT_QPA_PLATFORM=offscreen just verify
PYTHONPATH=loofi-fedora-tweaks python3 scripts/check_release_docs.py
just stats-check
just check-drift
just check-packaging
PYTHONPATH=loofi-fedora-tweaks python3 scripts/validate_product_contract.py
PYTHONPATH=loofi-fedora-tweaks python3 scripts/validate_system_check_contract.py
```

IPC is disabled and Qt is offscreen so tests cannot use active host IPC or
physical display state as hidden evidence. System calls, privilege prompts,
network access, package managers, and host probes remain mocked or bounded by
the maintained test contracts.

## Recorded local results

### v24 baseline

The clean v24.0.0 Flow checkout at the candidate baseline produced:

`7076 passed, 61 skipped, 9 warnings, 1237 subtests passed`.

### Proof-focused regression set

The current Proof-focused set includes direct lifecycle, eligibility, settings,
CLI, GUI, Home, Activity & Recovery, change-journal, and v24 Action Center
regressions. The latest broader focused run recorded:

`153 passed, 21 skipped, 1 warning`.

### Final command record

The final rootless command results are recorded here after the final candidate
pass. A command is only marked `passed` when its exit status is zero; unavailable
or externally dependent gates remain explicitly labeled.

| Gate | Result | Scope |
| --- | --- | --- |
| Full rootless `just verify` | passed — 7107 passed, 61 skipped, 20 warnings, 1239 subtests, 86.25% coverage | lint, typecheck, architecture, tests, coverage |
| Release documentation | passed | version, active docs, links, CLI examples, race lock |
| Project stats freshness | passed | generated local project metadata |
| Agent adapter drift | passed | generated adapter consistency |
| Packaging manifest | passed | local metadata/build contents only |
| Product contract | passed | rootless catalog and entrypoint trust boundaries |
| Architecture contract | passed | module budgets and annotation boundary |
| System Check contract | passed | source/route trust contract |

## Explicitly unverified or blocked gates

| Gate | Status | Reason |
| --- | --- | --- |
| Exact v25.0.4 commit and tag | pending | Canonical release workflow must bind the tag to the release commit |
| CI and CodeQL | pending | Awaiting tag-triggered workflow readback |
| GitHub assets, checksums, attestations | pending | Awaiting public release readback |
| COPR build/signature/repodata | pending | Awaiting canonical COPR job and repository readback |
| Clean Fedora KDE 44 installation | unverified | Not performed in this release task |
| Physical Fedora KDE Wayland | unverified | Rootless/offscreen tests cannot prove compositor behavior |
| Fresh Atomic/Kinoite | unverified | No Atomic host qualification was run |
| Keyboard and screen reader | unverified | No physical/manual accessibility session was run |
| Polkit prompt and privileged execution | unverified | Tests mock privilege boundaries; no host authorization was requested |
| Reboot-aware completion | unverified | The lifecycle is unit-tested, but no reboot was performed |
| Manual recovery | unverified | No physical recovery procedure was performed |

These labels are deliberate: a local green suite proves the tested software
contracts, not external publication or physical/manual qualification.
