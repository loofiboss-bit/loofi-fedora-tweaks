# Built-in Provider Development

Haven retires the external Python Plugin SDK and public Marketplace. Loofi does
not discover, import, install, update, or execute third-party Python extensions.
This page documents the internal provider contract for main-repository
maintainers.

## External extensions

Existing extension files remain in the user's configuration directories. The
**Advanced → Local Profiles → Legacy Extensions** view can inventory and export
their paths, but it never imports their modules or deletes their files.

The legacy CLI spellings remain only for deterministic compatibility:

```bash
# Read-only inventory; no Python code is imported.
loofi-fedora-tweaks --cli plugins list

# Returns exit status 2 and a schema-v3 feature_retired result.
loofi-fedora-tweaks --cli --json plugin-marketplace search
```

`plugins enable` and `plugins disable` also return `feature_retired`. Use a
built-in feature or a data-only local profile instead.

## Canonical catalog

`core.product_catalog` owns the reviewed product metadata. Generated, read-only
compatibility views expose:

- built-in `PluginSpec` records;
- stable navigation routes and aliases;
- destination and section placement;
- visibility, compatibility, and risk metadata.

Do not add a second hand-maintained registry. Add or change the canonical
catalog record, then regenerate its projections with the repository's existing
generation command and run the drift gate.

## Provider requirements

Every built-in provider must:

- ship in the reviewed application source tree;
- use stable catalog IDs and preserve documented aliases;
- defer its UI import and widget construction until route activation;
- keep PyQt6 code in `ui/` and domain logic in `core/` or `services/`;
- use `BaseTab` and `CommandRunner` for asynchronous GUI command flows;
- send host mutations through `ActionCenterOrchestrator`;
- classify each operation as `host`, `app_state`, `session`, or `manual_only`;
- use `self.tr("...")` for user-facing strings and semantic theme tokens for
  presentation;
- include deterministic tests for routes, lazy loading, availability, and
  mutation policy.

Background providers, agents, schedulers, and the daemon may create Action
Center plans. They may not confirm or execute a host mutation.

## UI skeleton

Use the existing built-in tabs as the source for exact construction patterns.
A minimal page follows the shared base class:

```python
from PyQt6.QtWidgets import QLabel

from ui.base_tab import BaseTab


class ExampleTab(BaseTab):
    def __init__(self) -> None:
        super().__init__()
        self.content_layout.addWidget(QLabel(self.tr("Example")))
```

Do not put subprocess calls, package-manager selection, filesystem mutation, or
business rules in the tab. Put those in a service and expose any host mutation
as a classified Action Center definition.

## Action definitions

Haven's Action Center catalog contains 56 first-party definitions. A definition
must declare:

- operation class;
- Traditional and Atomic Fedora support;
- reboot policy;
- affected resources;
- a closed parameter schema;
- preflight and preview behavior;
- confirmation and rollback acknowledgement;
- independent verification and recovery guidance.

Unsupported host operations must remain visible as `manual_only`; do not hide
them behind direct execution or a generic subprocess helper.

## Local profiles

Local profiles are explicit JSON files, not plugins. The accepted schema is
closed and data-only:

```json
{
  "schema_version": 1,
  "name": "work",
  "theme": "system",
  "icon_theme": null,
  "cursor_theme": null,
  "color_scheme": null,
  "battery_limit": 80,
  "power_profile": "balanced"
}
```

Imports reject unknown fields, unsupported schemas, symlinks, non-JSON files,
files larger than 1 MiB, and invalid values. Accepted data becomes a reviewable
Action Center plan before any host setting changes. Private Gist sync may back
up a user's profiles; it is not a discovery or executable distribution channel.

## Verification

Run targeted tests for the changed provider first, then the release gates:

```bash
just test-file test_product_catalog
just check-drift
just verify
```

Choose the closest existing test file if the provider has a dedicated suite.
Tests must remain rootless and mock system calls, file I/O, OS probes, and
network access.

See the repository's
[built-in provider contract](https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/master/docs/PLUGIN_SDK.md)
and
[architecture document](https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/master/ARCHITECTURE.md)
for the canonical boundaries.
