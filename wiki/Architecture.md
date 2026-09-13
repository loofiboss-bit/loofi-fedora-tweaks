# Architecture — v27.0.1 "Core"

The repository's canonical architecture contract is
[ARCHITECTURE.md](https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/master/ARCHITECTURE.md)
and [.workflow/specs/arch-v27.0.1.md](https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/master/.workflow/specs/arch-v27.0.1.md).

## Runtime shape

```text
main.py
├── GUI: ui/ → core/ + services/ (typed state and signals)
└── CLI: cli/ → core/ + services/ (no UI imports)
```

The five primary destinations are Home, Updates & Apps, System Health,
Protection & Recovery, and Changes. Settings is a header-level route.

## Boundaries

- `core/` owns immutable contracts, catalog policy, Action Center planning,
  persistence, diagnostics, and verification.
- `services/` owns bounded, PyQt-free host probes and adapters.
- `ui/` owns presentation and accessibility; it does not run subprocesses.
- `cli/` parses the reduced public interface and serializes typed results; it
  does not import UI modules or execute arbitrary commands.
- `PlatformProfile` is the shared Fedora version/desktop/session/backend
  authority and fails closed when detection is unknown.

## Distribution boundary

The supported artifact is one COPR-backed RPM (plus a development sdist). The
Core release has no background daemon, local Web API, specialist suite,
external plugin execution, custom Polkit policy package, or Flatpak bundle.

Older wiki pages may describe historical releases; they are not current runtime
or packaging instructions. See the current [CLI reference](CLI-Reference),
[Installation](Installation), and [Security Model](Security-Model).
