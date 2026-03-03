# Loofi Fedora Tweaks — Gemini CLI Instructions

> **Canonical instructions**: `AGENTS.md`
> Read `AGENTS.md` first, then apply this file for Gemini-specific behavior.

---

## Workflow

Use: **PLAN -> IMPLEMENT -> VERIFY -> DOCUMENT -> COMMIT -> PUSH**

---

## Quality Gates

```bash
PYTHONPATH=loofi-fedora-tweaks python -m pytest tests/ -v --tb=short
flake8 loofi-fedora-tweaks/ --max-line-length=150 --ignore=E501,W503,E402,E722,E203
mypy loofi-fedora-tweaks/ --ignore-missing-imports --no-error-summary
```

---

## Workspace Skills

Gemini should prioritize these workspace skills when relevant:

### Claude skills (`.claude/skills/`)
- `fedora-verify`
- `new-tab`

### Codex skills (`.codex/skills/`)
- `fedora-plan`
- `fedora-design`
- `fedora-implement`
- `fedora-test`
- `fedora-validate`
- `fedora-doc`
- `fedora-package`
- `fedora-release`
