# v18 Phase 6 Local Release Readiness

Date: 2026-07-22  
Candidate state: committed Haven implementation on `v18-haven`, based on
`6630c92` with release metadata and documentation prepared for the final
release commit

Release decision: **LOCAL PASS / AUTHORIZED FOR PUBLICATION**

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

Fresh isolated builds passed for RPM, source distribution, and Flatpak. The
RPM `%check` import smoke and AppStream validation passed. Direct artifact
inspection confirmed `18.0.0` / `Haven` in the source archive, RPM NEVRs of
`1:18.0.0-1.fc44`, and Flatpak commit
`96c8022d11bb8d9da6ff057aff439baed5401246c647cd47476e6f044efb46a4`
with the same embedded version.

## Publication-only gates

- Canonical CodeQL must run in GitHub Actions from the release
  commit. Local Bandit and dependency audit results do not replace it.
- The current Fedora 44 KDE physical host passed a native Wayland smoke at
  1920x1080 and 1.4x scale plus an XCB/XWayland smoke at requested 1,180 DIP.
  The signed Kinoite 44 install and real rpm-ostree reboot/readback evidence is
  carried forward from v17; a fresh v18 Atomic guest installation was not
  repeated. See [V18_PLATFORM_CERTIFICATION.md](V18_PLATFORM_CERTIFICATION.md).
- Fedora 45 remains preview-only until stable and independently certified.
- Remote readback confirms that historical Sentinel is preserved as
  `legacy-v18.0.0-sentinel`. Creating the canonical Haven tag and publishing
  GitHub and COPR artifacts remain pending.

The complete implementation is committed and pushed on `v18-haven`. The old
Sentinel tag was preserved under its explicit legacy name before the obsolete
`v18.0.0` tag was removed. The canonical Haven tag must be created only by the
release workflow from the exact release commit.
