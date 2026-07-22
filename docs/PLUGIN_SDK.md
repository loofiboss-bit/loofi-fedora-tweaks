# Built-in Page Provider Contract

## v18 status

The external Python Plugin SDK and public Marketplace are retired in v18. Loofi
Fedora Tweaks does not discover, import, install, update, or execute third-party
Python extensions. This is an intentional security boundary, not a temporary
offline state.

Existing extension files remain untouched in the user's configuration directory.
The local **Community → Legacy Extensions** view shows their paths and supports a
data-preserving export. It never loads their code.

The legacy `plugin-marketplace` CLI spelling is accepted during v18 compatibility
handling, is hidden from help, and always returns a machine-readable
`feature_retired` error.

## Internal providers

Application-owned pages continue to use the built-in lazy-loading mechanism.
Their metadata is sourced from `core.product_catalog.ProductCatalogEntry` and
exposed through generated, read-only `PluginSpec`, `NavigationRoute`,
`RoutePlacement`, and `SectionDefinition` compatibility views.

Internal providers must:

- live in the application source tree and ship with the same reviewed package;
- use stable product-catalog IDs and existing route aliases;
- keep imports lazy so startup constructs only the Home provider;
- keep PyQt code in `ui/` and domain logic in `core/` or `services/`;
- send host mutations through `ActionCenterOrchestrator`;
- use translated user-facing strings and semantic theme tokens;
- include deterministic tests for navigation, lazy loading, and mutation policy.

This contract is for maintainers of the main repository. It is not an extension
or distribution API.

## Local profiles

Local presets are non-executable data. Imports must validate the schema, reject
unsafe paths and unknown operations, and translate accepted content into an
Action Center plan. Private, user-owned Gist sync remains an optional backup
transport; it is not a discovery or executable distribution channel.

Historical release notes and reports may describe the former Marketplace. They
are retained as historical evidence and do not describe current behavior.
