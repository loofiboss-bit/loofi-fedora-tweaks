# Testing — v27.0.1 "Core"

## Current evidence

- **Automated suite:** 4,780 passed, 73 skipped, 0 failed.
- **Coverage:** 86.94% line coverage for the maintained V27 surface; the
  blocking gate is 85%.
- **Quality:** lint, mypy, architecture, product-contract, stabilization,
  packaging, dependency-sync, and compile checks passed locally.
- **Manual gates:** physical desktop, keyboard/Orca, Polkit agent, reboot, and
  fresh Atomic installation are **unverified** under the explicit v27.0.1
  release decision.

The complete test suite still exercises compatibility-only modules. The
repository-wide 90% target is deferred to the next release and is not claimed
by this version.

## Run the suite

```bash
LOOFI_IPC_MODE=disabled QT_QPA_PLATFORM=offscreen just test
LOOFI_IPC_MODE=disabled QT_QPA_PLATFORM=offscreen just test-coverage
just lint
just typecheck
just verify
```

The offscreen environment makes local evidence deterministic; it does not
prove physical display, keyboard, screen-reader, authorization-agent, reboot,
or Atomic behavior.

## Release validation

```bash
just validate-release
just check-packaging
just stats-check
just check-drift
```

Release claims must link to the exact tag, workflow run, artifact checksums,
attestations, package metadata, and public documentation readback. Never infer
a host result from a mocked subprocess or an offscreen run.
