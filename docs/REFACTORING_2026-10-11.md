# Refactoring report — 2026-10-11

This refactor consolidates repeated domain helpers, makes static catalog work
reusable, and gives three maintenance operations the existing Qt operation
adapter and deferred window-shutdown lifecycle. It preserves compatibility
imports and signatures, action policy, output text, command execution, and
catalog ordering.

## Changes and compatibility decisions

- Manual-only action definitions now share one builder. Assurance injects its
  existing denial policy, so the distinct alternative guidance remains intact.
- Assurance reuses the continuity-recovery JSON, boot-ID, and pending-deployment
  helpers through the old assurance import names. Staged, pending, and booted
  deployment priority is unchanged.
- Four monitor/process byte-formatting loops use one shared legacy formatter.
  Their method names and `B`/`KB`/`MB` output remain; the separate `KiB` formatter
  keeps its own contract. The two export backends share Flatpak line parsing,
  while each retains its command, timeout, and error handling.
- Product entries and route/plugin/module indexes are built once. Default
  action definitions and task guidance reuse static metadata; action parameter
  schemas are copied per catalog instance. Injected definitions remain
  caller-owned, and capability probes, preflight decisions, and verification
  results remain fresh.
- Action Center, Updates, and reclaim analysis now use
  `OperationControllerQtAdapter`. The window waits for these page-owned
  operations to deliver a terminal result and stop before teardown. Review,
  apply, and verification remain distinct domain steps.
- Removed `PluginLoader._check_version_compatibility` after a repository-wide
  reference search found no call, export, or string reference. Kept
  `PluginLoader`, its constructor contract, `_parse_version`, and loader
  registration behavior. Kept the `ActionCenterOperationWorker` compatibility
  wrapper because `maintenance_tab` imports it; kept CLI handlers, profile
  exports, and daemon adapters for their existing import and behavior contracts.
- Fixed the duplicate import-test class name that had shadowed four tests.
  Executor export coverage now checks the exact current nine-symbol `__all__`,
  including the command-facade exports. Import-performance tests now time real
  cold imports in isolated Python interpreters. An architecture test also
  asserts that the CLI has no PyQt widget imports.

No runtime Python files were removed: the application keeps 428 files. This
was intentional because the verified redundant code was inside active modules
and the remaining legacy modules still have import or behavior contracts.

## Before and after measurements

The baseline is commit `3cf250a`. File and line counts cover
`loofi-fedora-tweaks/**/*.py`; physical lines use `splitlines()`. The AST
decision count includes `if`, conditional expressions, loops, exception
handlers, each boolean operand after the first, and each `match` case. It is a
consistent structural comparison, not a complexity score.

| Scope | Python files | Physical lines before → after | AST decisions before → after |
| --- | ---: | ---: | ---: |
| Whole application | 428 → 428 | 95,029 → 95,033 | — |
| All changed runtime modules | 18 → 18 | 9,243 → 9,247 | 1,103 → 1,087 |
| Actions | 2 → 2 | 1,504 → 1,468 | 202 → 189 |
| Catalogs | 3 → 3 | 1,800 → 1,829 | 190 → 191 |
| UI worker lifecycle | 4 → 4 | 3,266 → 3,284 | 433 → 439 |
| Formatting and exports | 8 → 8 | 2,550 → 2,558 | 253 → 247 |
| Plugin loader | 1 → 1 | 123 → 108 | 25 → 21 |

The total source size changes by four lines. The affected modules have 16 fewer
AST decision points overall, including reductions in action policy, formatting,
and plugin loading. Catalog caching and UI shutdown ownership add explicit
code, so physical line count is not presented as an overall reduction.

| Subsystem | Repeated or dead implementation | Before → after |
| --- | --- | --- |
| Actions | Manual action-definition bodies | 2 → 1 shared builder, with policy callback |
| Actions | JSON, runtime boot-ID, and pending-deployment helper bodies | 2 copies each → 1 shared definition each, with old names retained as imports |
| Formatting | Legacy byte-formatting loops | 4 → 1 formatter, with four method adapters |
| Exports | Flatpak export-list parsers | 2 → 1 parser; command execution stays per exporter |
| UI | Manual maintenance QThread lifecycle blocks | 3 → 0; all three use the existing adapter |
| Catalogs | Product entries/indexes, default action definitions, and action guidance projection | Rebuilt per use → static portions built or projected once |
| Plugin loader | Unused private version-compatibility helper | 1 → 0 |

Across exact duplicate code, six groups were consolidated: four in actions
(the manual builder and three helpers) and two in formatting/exports. The UI
replaced three manual lifecycle blocks; the loader dropped one dead helper.
Catalog construction reuse is repeated-work reduction rather than a duplicate
function-body count.

Catalog construction and import measurements use the same Python 3.14.8
interpreter and nine repeated fresh processes for baseline and working tree.
Each catalog sample first constructs one instance, then times the second
construction or lookup with `perf_counter` and measures that call's peak
`tracemalloc` allocation. Module import is outside the catalog timer. CLI
samples start a fresh interpreter for each run and time `import cli.main`,
excluding interpreter startup. Values below are medians.

| Operation | Before | After |
| --- | ---: | ---: |
| Second `ActionCatalog()` construction | 11.462 ms / 465,628 B | 5.537 ms / 141,032 B |
| Second `TaskCatalog()` construction | 16.127 ms / 466,164 B | 0.115 ms / 7,160 B |
| Second `product_catalog()` lookup | 0.275 ms / 6,880 B | 0.011 ms / 72 B |
| Cold `import cli.main` | 25.720 ms | 25.681 ms |

These are local microbenchmarks, not end-user startup guarantees. The CLI
import result is effectively unchanged at this precision.

## Verification

Baseline verification at `3cf250a` passed `just verify` with 5,195 tests,
2,069 subtests, 33 skips, and 85.55% coverage; `just check-packaging` passed.

On the refactored tree, `LOOFI_IPC_MODE=disabled QT_QPA_PLATFORM=offscreen
just verify` passed lint, type checking, architecture and catalog checks, and
the full test suite: 5,214 passed, 2,092 subtests passed, 33 skipped, and
85.58% coverage. The run reported 22 warnings. `just check-packaging` passed.

The separate integration run covered product catalog/plugin integration,
main-window and shutdown behavior, OperationController, v29 vertical flows,
Personal UI, maintenance UI, packaging scripts, and the new catalog and
consolidation regression tests: 324 passed, 33 skipped, with one existing
`utils.safety` deprecation warning. No new test failures were observed.

Automated/offscreen checks do not verify physical GNOME/KDE behavior; that
qualification remains outstanding. No host state, user settings, or VM workflow
was changed.
