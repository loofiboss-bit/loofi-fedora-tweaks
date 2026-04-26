# Architecture Spec — v4.0.0 "Atlas"

## Design Rationale

`v4.0.0` "Atlas" marks a major architectural shift from a multi-tool utility to a guided system assistant. 
It introduces a centralized diagnostic intelligence layer (Health & Repair Autopilot) and a goal-oriented 
task dashboard. Key design pillars include safety-first operations (rollback-first), Atomic Fedora parity, 
and user-centric guided workflows (wizards).

## Core Components

### 1. Health & Repair Autopilot (HRA)
- `HealthRegistry`: Central hub for system diagnostics.
- `HealthCheck` / `HealthResult`: Structured data models for consistent reporting.
- Real-world detection logic integrated with `ActionExecutor`.

### 2. Guided Dashboard
- `AtlasDashboardTab`: Replaces traditional metrics with actionable "Task Cards".
- `TaskManager`: Maps high-level goals to specific health checks and repairs.

### 3. Safety Layer
- `SystemAction`: Encapsulates commands with risk assessment and revert hints.
- `AtlasTaskWizard`: Implements the 4-step guided repair lifecycle.

## Reviewed Inputs

- `ROADMAP.md` (v4.0.0 section)
- `docs/architecture/V4_ATLAS_PLAN.md`
- `services/system/system.py` (Atomic/rpm-ostree detection)
- `core/executor/action_executor.py`
