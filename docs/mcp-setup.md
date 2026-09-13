# GitHub Automation Guide — v27.0.1 "Core"

This page documents the repository's current GitHub automation surface. It is
not a runtime API guide: Loofi Fedora Tweaks v27.0.1 ships a local PyQt6 GUI
and CLI, and does not ship a web API, background daemon, or MCP server.

## Current automation

The maintained workflows are:

| Workflow or service | Purpose |
| --- | --- |
| `.github/workflows/ci.yml` | Pull-request and master validation: lint, typecheck, tests, security, docs, and RPM/sdist packaging |
| GitHub CodeQL default setup | Python and GitHub Actions code scanning on pull requests and the weekly schedule |
| `.github/workflows/auto-release.yml` | Master/tag validation, Fedora review, RPM/sdist release assets, checksums, SBOM, provenance, and COPR handoff |
| `.github/workflows/copr-publish.yml` | Explicit manual COPR publication for an already tagged release |
| `.github/workflows/publish-wiki.yml` | Synchronizes the tracked `wiki/` directory to the GitHub wiki repository |

CodeQL is configured for `python` and `actions`, the languages present in the
current repository. JavaScript/TypeScript scanning is intentionally disabled;
there is no JavaScript/TypeScript product source to analyze.

## Local validation

Use the same deterministic command as CI:

```bash
LOOFI_IPC_MODE=disabled QT_QPA_PLATFORM=offscreen just verify
```

The current maintained gate is 85% coverage. V27.0.1 records approximately
86.9% local coverage. The repository-wide 90% target is deferred to a later
release by an explicit release decision; it is not represented as a hidden
failure or an unverified success claim.

Packaging can be checked locally with:

```bash
just check-packaging
just build-rpm
just build-sdist
```

## Release authority and safety

The canonical release is created from the exact master commit by
`auto-release.yml`. The workflow refuses to move an existing tag and verifies
the peeled tag commit before publishing. Release evidence is read back from
GitHub and COPR before the release is called public.

Application host mutations remain behind Action Center review and explicit
user confirmation. CI/offscreen tests do not prove a physical desktop,
Polkit-agent, reboot, or fresh Atomic-Fedora qualification; those gates remain
explicitly unverified when they have not been run.

## Historical MCP material

Older repository snapshots contained experimental Copilot/MCP and bot-workflow
notes. Those experiments are not part of the V27 runtime or release process.
Use the current workflow files and [the documentation index](README.md) as the
source of truth.
