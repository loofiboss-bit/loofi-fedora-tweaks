# Built-in Provider Architecture — v28.0.2 "Ease"

To guarantee system stability, user security, and verifiable maintenance, external untyped Python plugin loaders and dynamic third-party extensions are intentionally retired. All maintenance capabilities and system providers are built-in, statically typed, and audited directly within the main repository.

This page documents how built-in providers and maintenance actions are structured and integrated.

---

## 1. Provider Design Requirements

Every provider implemented within Loofi Fedora Tweaks must adhere to these standards:

1. **Strict Decoupling**: Keep PyQt6 presentation logic in `ui/`, domain contracts in `core/`, and system probes in `services/`.
2. **Lazy Initialization**: Defer UI widget construction and expensive system probes until the relevant view is explicitly activated.
3. **Capability Classification**: Classify all provider capabilities as one of:
   - `host`: Modifies the underlying Fedora operating system (requires Action Center plan).
   - `app_state`: Modifies Loofi application preferences (local user state).
   - `session`: Affects only the current desktop session.
   - `manual_only`: Provides instructions for manual operator action when automation is unsafe.
4. **No Direct Subprocesses in UI**: UI classes must never invoke `subprocess.run`, `pkexec`, or shell utilities directly. All host modifications must be orchestrated via `ActionCenterOrchestrator`.

---

## 2. Registering in `core.product_catalog`

The `core.product_catalog` module is the single source of truth for all destinations, routes, capabilities, and risk assessments.

When introducing a new maintenance feature:
- Define the capability identifier and required platform prerequisites (e.g. requires `dnf5`, or requires `sysfs` battery threshold node).
- Specify risk tier (`safe`, `low`, `moderate`, `high`).
- Define whether a system reboot is required.

---

## 3. Defining an Action Center Definition

Every persistent system modification requires a formal action definition:

```python
definition = ActionDefinition(
    id="example-action",
    capability_id="maintenance.example",
    title="Example maintenance action",
    description="Apply one reviewed maintenance operation.",
    parameter_schema={},
    risk_level="low",
    privileged=True,
    confirmation_policy="explicit",
    recovery_guidance="Re-run the independent verification probe if needed.",
    rollback_supported=False,
    command_renderer=render_command,
    preflight_checker=check_preconditions,
    verifier=verify_result,
    operation_class="host",
    supported_variants=frozenset({"traditional", "atomic"}),
    reboot_policy="none",
    affected_resources=("example-resource",),
)
```

### The Three Required Callbacks
- **`preflight_checker`**: Runs before execution to confirm preconditions (e.g. disk space, package manager lock availability, hardware support).
- **`command_renderer`**: Returns an explicit sequence of command arguments (no shell string) for the audited executor.
- **`verifier`**: Probes the host post-execution to confirm that the change took effect.

`ActionDefinition` also requires a `capability_id`, typed `parameter_schema`, recovery guidance, and an explicit confirmation policy. Optional fields such as `parameter_validator` and `privilege_resolver` can tighten validation and privilege decisions further.

---

## 4. Testing Your Provider

Every provider must be accompanied by comprehensive tests:
- **Unit Tests**: Test data parsing, argument construction, and error handling with mocked system calls.
- **Offscreen UI Tests**: Verify widget rendering and user interactions using Qt offscreen mode.
- **Contract Tests**: Ensure the catalog definitions match `PlatformProfile` contracts.

```bash
# Run tests for your provider
just test-file test_product_catalog_records
just test-file test_services_hardware_manager
```
