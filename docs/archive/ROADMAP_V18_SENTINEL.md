# Archived Roadmap v18.0 "Sentinel" — Autonomous System Agents

This document preserves the pre-renormalization v18 plan. Those agent features
were implemented in historical development and are not the authority for the
current v18.0.0 "Haven" release. The canonical plan is
`docs/plans/LOOFI_FEDORA_TWEAKS_V18_PLAN.md`.

## Historical vision

Sentinel proposed autonomous system agents, a scheduler, natural-language
planning, agent UI and CLI commands, and five built-in monitoring/maintenance
agent types. It also proposed a future agent marketplace.

## Historical safety model

New agents defaulted to dry-run, applied rate and severity gates, avoided
privilege escalation, and bounded history. Haven supersedes this model for host
mutation: agents may inspect and create Action Center plans, but they may not
confirm or execute host changes unattended.

## Historical implementation references

- Agent framework, runner, scheduler, planner, UI, and CLI were added before the
  repository's canonical version-history normalization.
- The original `v18.0.0` tag points to historical Sentinel commit
  `f0cb0bf2be8a873de368341a400186158e12498f`.
- That tag must be preserved as `legacy-v18.0.0-sentinel` before a separately
  authorized Haven release reuses the canonical version number.
