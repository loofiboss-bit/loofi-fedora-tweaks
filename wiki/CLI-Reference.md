# CLI Reference — v29.0.1 "Utility"

The CLI is a bounded, read-first companion to the GUI. It accepts registered
commands and typed parameters only; it never evaluates arbitrary shell text or
starts an unattended background service.

```bash
loofi-fedora-tweaks --cli [--json] [--timeout SECONDS] COMMAND
```

## Commands

| Command | Purpose |
| --- | --- |
| `info` | Show Fedora, desktop, session, and deployment profile |
| `check` | Run the explicit read-only System Check |
| `updates` | Inspect independent update sources |
| `troubleshoot` | List or run bounded symptom profiles |
| `activity` | Inspect Activity & Recovery entries |
| `changes` | v29 compatibility alias and explicit saved-plan completion |
| `doctor` | Inspect dependencies and authorization prerequisites |
| `support-bundle` | Export a bounded redacted diagnostic archive |

Examples:

```bash
alias loofi='loofi-fedora-tweaks --cli'

loofi info
loofi --json check
loofi updates check
loofi troubleshoot profiles
loofi troubleshoot run system_slow
loofi activity list
loofi activity show EVENT_ID
loofi doctor
loofi support-bundle
```

`changes list` and `changes show` resolve through Activity during v29.
`changes apply PLAN_ID --yes` and `changes verify RUN_ID` remain available only
to finish explicitly selected compatible saved state.

Unknown Fedora variants, unavailable tools, invalid parameters, and unsupported
mutation backends fail closed. Host changes still require fresh preflight,
policy-appropriate confirmation, bounded authorization, and independent
verification.
