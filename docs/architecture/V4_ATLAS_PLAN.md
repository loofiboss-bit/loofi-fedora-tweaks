# Architecture Plan: v4.0 "Atlas" — Guided Fedora Control Center

## Overview
v4.0 "Atlas" introduces an intelligence and safety layer on top of the existing Loofi Fedora Tweaks service architecture. The goal is to move from "User-triggered commands" to "Goal-oriented tasks" supported by automated diagnostics.

## 1. Health & Repair Autopilot (HRA)

### Component: `loofi-fedora-tweaks/core/diagnostics/autopilot.py`
A central registry for system health checks.

#### Health Item Schema (JSON/Dataclass)
```python
@dataclass
class HealthCheck:
    id: str                 # unique-slug
    title: str              # User-friendly name
    severity: str           # info | warning | error | critical
    category: str           # system | package | security | hardware
    description: str        # What is wrong?
    detection_cmd: list     # Command to run for detection
    expected_output: str    # Regex or value to match
    safe_to_auto_fix: bool  # Can we fix this without user input?
    dry_run_supported: bool
    suggested_fix: str      # User-friendly explanation of the fix
    manual_commands: list   # Commands the user can run manually
    rollback_hint: str      # How to undo
    help_link: str          # URL to docs
```

### Discovery Engine
The HRA engine will run checks in parallel (non-blocking) using the existing `QThread` infrastructure.

## 2. Rollback-First Action Model

### Component: `loofi-fedora-tweaks/core/executor/action_model.py`
Extends `BaseActionExecutor` with safety metadata.

#### Features
- **Preflight Hooks**: Check for DNF locks, disk space, or conflicting services before execution.
- **Command Preview**: Generate a shell script preview of the intended changes.
- **Metadata Bundling**: Store the "why" and "how to revert" alongside the execution result.

## 3. Fedora Upgrade Assistant

### Component: `loofi-fedora-tweaks/core/diagnostics/upgrade_checker.py`
A specialized diagnostic suite focused on Fedora major version transitions.

#### Audit Areas
- **Storage**: Minimum 5GB free on `/`.
- **Packages**: Broken dependencies, duplicate packages, GPG key issues.
- **Repos**: Active COPRs, non-standard repositories that might break.
- **Hardware**: NVIDIA driver/kernel compatibility (akmods status).
- **Atomic**: rpm-ostree rebase readiness.

## 4. Task-Based UI (Dashboard)

### Component: `loofi-fedora-tweaks/ui/dashboard_tasks.py`
A new high-level view that presents the system as a set of actionable tasks rather than just settings.

#### Task Cards
- **"Fix my system"**: Aggregates `error` and `critical` items from HRA.
- **"Optimize for Gaming"**: Bundles GameMode, power profile, and CPU governor checks.
- **"Secure my Fedora"**: Highlights firewall, SELinux, and update status.

## 5. Implementation Phases

### Phase A: Schema & Mocking (Current Focus)
- Define `HealthCheck` and `ActionMetadata` models.
- Implement the HRA Registry.
- Mock 5-10 core checks (DNF lock, service failed, updates pending).

### Phase B: Core Backend
- Implement the detection engine.
- Wire the Fedora Upgrade Assistant backend.
- Create the Support Bundle v2 generator.

### Phase C: UI Wiring
- Add the "Task Cards" to the Dashboard.
- Create the "Fix It" workflow with confirmation/dry-run dialogs.
- Implement the Upgrade Assistant report view.
