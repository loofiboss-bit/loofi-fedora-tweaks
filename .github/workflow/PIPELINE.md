# Workflow Pipeline

Release work follows this sequence:

1. Align version metadata with `scripts/bump_version.py`.
2. Update active release docs, workflows, RPM spec metadata, and generated adapter instructions.
3. Implement service/core logic before GUI, CLI, or packaging exposure.
4. Add deterministic tests with mocked host/system calls.
5. Run stabilization, adapter, release-doc, lint, type, test, coverage, RPM, and CLI smoke validation.

For v8.1.0 Breeze, active build and COPR references target Fedora 44. Navigation work must route through `core/navigation`, keep the focused five-area sidebar, and avoid adding another major feature tab.
