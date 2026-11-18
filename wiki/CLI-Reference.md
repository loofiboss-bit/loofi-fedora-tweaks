# CLI Reference — v36.2.0 "Blueprint"

The CLI is a bounded, read-first companion to the GUI. It accepts registered
commands and typed parameters only; it never evaluates arbitrary shell text or
starts an unattended background service.

```bash
loofi-fedora-tweaks --cli [--json] [--timeout SECONDS] [--dry-run] COMMAND
```

## Commands

| Command | Purpose |
| --- | --- |
| `info` | Show Fedora, desktop, session, and deployment profile |
| `check` | Run and persist the explicit read-only System Check |
| `updates` | Inspect update sources, `flatpaks`, `sources`, `restart-advice`, and `prepare-upgrade` |
| `troubleshoot` | Run or inspect bounded troubleshooting profiles and sessions |
| `changes` | Compatibility alias for Activity with retained apply and verify verbs |
| `activity` | Inspect the Trusted Change Journal and create reviewed recovery plans |
| `doctor` | Inspect dependencies, Fedora release support, and Polkit status |
| `support-bundle` | Export a bounded redacted diagnostic archive |
| `tweaks` | `list`, `get`, `set`, `restore`, `profile`, and `preset` controls (see [TWEAKS.md](https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/master/docs/TWEAKS.md)) |
| `apps` | `list`, `install`, `installed`, `compare`, `permissions`, `remove`, `access`, `details`, `unused`, and `cleanup` |
| `guides` | `list` and `show` everyday Fedora guides and progress |
| `setup` | `list`, `show`, and `compare` saved My Fedora configurations (`loofi.setup/v1`) |

Examples:

```bash
alias loofi='loofi-fedora-tweaks --cli'

loofi info
loofi --json check
loofi updates check
loofi updates flatpaks --installation user
loofi troubleshoot profiles
loofi troubleshoot run system_slow
loofi activity list
loofi activity show EVENT_ID
loofi doctor
loofi support-bundle
loofi tweaks list
loofi tweaks get gnome-hot-corners
loofi tweaks set gnome-hot-corners false --yes
loofi tweaks profile library compare focus privacy-basics
loofi apps list --category Utilities
loofi guides list
loofi setup list
loofi setup compare SETUP_ID
```

`changes list` and `changes show` resolve through Activity during v29.
`changes apply PLAN_ID --yes` and `changes verify RUN_ID` remain available only
to finish explicitly selected compatible saved state.

Unknown Fedora variants, unavailable tools, invalid parameters, and unsupported
mutation backends fail closed. Host changes still require fresh preflight,
policy-appropriate confirmation, bounded authorization, and independent
verification.
