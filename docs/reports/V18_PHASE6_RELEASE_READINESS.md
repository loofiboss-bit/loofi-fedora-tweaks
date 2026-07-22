# v18 Phase 6 Local Release Readiness

Date: 2026-07-22  
Candidate state: uncommitted Haven implementation on `master`, based on `e7c7c07`  
Release decision: **LOCAL PASS / PUBLIC RELEASE BLOCKED**

## Implemented release boundary

- The 80 stable routes now project from one product catalog. Retired Community
  routes remain hidden compatibility destinations and explain the transition to
  local profiles.
- The 56 first-party Action Center definitions declare operation class, Fedora
  variants, reboot policy, affected resources, closed parameters, preflight,
  preview, confirmation, verification, and recovery policy. Unsupported host
  operations are explicit `manual_only` plans.
- GUI, CLI, daemon, automation, and agents are guarded by the Haven mutation
  gate. Daemon, agent, and scheduler paths may create plans but cannot confirm
  or execute them unattended.
- Action plans and runs use schema v3. Older state is atomically migrated with
  last-known-good backup and readback; unknown future schemas remain read-only.
- External Python plugin discovery, installation, hot reload, dependency
  resolution, reviews, analytics, and public preset distribution are absent
  from active and packaged code. Existing third-party directories are only
  inventoried and exported; they are never imported or deleted.
- Gist and JWT secrets use Secret Service when persistent storage is available.
  Plaintext is removed only after persistent readback; otherwise the value stays
  session-only. The read-only Web API rejects non-loopback binding and supports
  rate-limited token issuance, rotation, and revocation.

## Local verification

| Gate | Result |
| --- | --- |
| Full suite and coverage | 6,796 passed, 68 skipped, 16 warnings; 86.24% |
| Lint | clean |
| mypy | clean; `check_untyped_defs` enabled for Haven boundaries |
| Haven AST/import gate | 80 routes; zero unclassified presentation mutations |
| Architecture gate | 85.51% fully annotated runtime functions; CLI `main()` 23 lines |
| Largest production modules | 967, 923, 882, 870, and 841 non-empty lines |
| Stats, agent drift, release docs | clean |
| Bandit | zero medium/high findings |
| Project dependency audit | no known vulnerabilities in `requirements.txt` or `pyproject.toml` |
| Package manifest | clean |

The final full-suite command was:

```bash
just test-coverage
```

The warnings are pre-existing test-environment or compatibility warnings:
PyGObject and import deprecations, mocked clipboard-server thread cleanup,
legacy health-timeline SQLite resource warnings, and a duplicate-entry archive
fixture. They do not fail the current gate, but they remain visible debt.

An environment-wide audit also reports `PYSEC-2026-196` in the workspace's
development-only `pip 26.1`; `pip 26.1.2` contains the fix. `pip` is not an
application dependency or packaged runtime component, so this does not change
the project dependency result above. The isolated source build additionally
reports Setuptools' forward-looking license-metadata deprecation warning.

## Startup evidence

The final offscreen benchmark used one warmup and ten measured clean-profile
runs. Meaningful Home median was **142.042 ms** and median RSS was **75,408
KiB**. Phase 0 medians were 143.848 ms and 75,188 KiB, so the candidate stays
below the 172.618 ms and 86,466 KiB limits. Every run created exactly one
runtime plugin and reported zero subprocess probes, active timers, and running
QThreads.

## Package evidence

Fresh isolated builds passed for RPM, source distribution, and Flatpak. Each
artifact was opened without installation and passed an import smoke that
verified all 80 routes, the Action Center catalog, absence of the retired hot
reload API, and fail-closed external plugin loading.

The artifacts deliberately identify as v17.0.0. They prove that the current
implementation packages successfully; they are not v18 release artifacts.
The repository version and codename remain `17.0.0` / `Assurance` until every
release-only gate passes and a version bump is explicitly authorized.

## Remaining release blockers

- Canonical CodeQL must run in GitHub Actions from the eventual candidate
  commit. Local Bandit and dependency audit results do not replace it.
- Fedora 44 must be physically verified on Traditional KDE/Workstation and
  Atomic Kinoite/Silverblue. Required Wayland/X11, 860/1,180/1,400 DIP,
  100-200% scaling, theme, keyboard, and focus checks remain physical evidence.
- Fedora 45 remains preview-only until stable and independently certified.
- Remote readback currently shows historical `v18.0.0` at `f0cb0bf`; the
  required `legacy-v18.0.0-sentinel` tag is absent. Preserving that history,
  deleting the old name after readback, committing, pushing, version bumping,
  tagging, and publishing all require separate authorization.

No commit, push, tag mutation, version bump, or public release was performed.
