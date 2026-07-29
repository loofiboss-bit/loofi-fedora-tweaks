# Architecture — v23.0.2 "Compass"

## Goal

Complete the daemon's least-privilege filesystem contract without widening its
authority or changing application behavior.

## Decisions

- Keep `ProtectSystem=strict`, `ProtectHome=read-only`, and the existing
  system-call restrictions.
- Keep explicit write access limited to the existing config and data paths.
- Let systemd create `$XDG_RUNTIME_DIR/loofi-fedora-tweaks` with
  `RuntimeDirectory=` for collector and Action Center leases.
- Let systemd create `$XDG_STATE_HOME/loofi-fedora-tweaks` with
  `StateDirectory=` for the rotating application log.
- Use mode `0700` for both systemd-managed directories.
- Do not add cache, desktop, package-manager, system, or unrelated home
  write access.

## Verification boundary

The release requires both static unit regression coverage and a real Fedora 44
user-manager run proving D-Bus startup, health collection, zero restart loops,
and no post-start sandbox write errors.
