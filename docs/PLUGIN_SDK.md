# Built-in Page Provider Contract

The v27 Core product has no third-party Python plugin or marketplace API.
Loofi Fedora Tweaks does not discover, import, install, update, or execute
external extensions.  This is an intentional security and support boundary.

## Internal providers

Application-owned pages use the built-in lazy-loading mechanism.  Product
metadata comes from `core.product_catalog.ProductCatalogEntry` and is exposed
through generated, read-only `PluginSpec`, `NavigationRoute`, `RoutePlacement`,
and `SectionDefinition` compatibility views.

Internal providers must:

- live in the application source tree and ship with the reviewed RPM;
- use stable product-catalog IDs and existing route aliases;
- keep imports lazy so startup constructs only Home;
- keep PyQt code in `ui/` and domain logic in `core/` or `services/`;
- send persistent host changes through `ActionCenterOrchestrator`;
- use translated user-facing strings and semantic theme tokens;
- include deterministic tests for navigation, lazy loading, and mutation policy.

This contract is for maintainers of the main repository.  It is not an
extension, marketplace, or distribution API.

## Local data

Local profiles and presets are non-executable data.  Imports must validate the
schema, reject unsafe paths and unknown operations, and translate accepted
content into an Action Center plan.  User-owned backup transports remain
optional and are never discovery or executable distribution channels.

Historical release notes may describe the former extension system.  They are
retained as history and do not describe current behavior.
