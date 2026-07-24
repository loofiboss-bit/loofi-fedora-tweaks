# v19 Phase 2 Explicit Home System Check

## Outcome

Phase 2 adds one visible `Check now` action to empty, stale, and
recoverable-error Home states. Collection starts only from that explicit user
activation. Home still constructs from persisted data without collectors,
subprocess probes, timers, or worker threads.

The operation uses the existing `BaseWorker`/`QThread` convention through a
small `SystemCheckWorker` adapter. Progress names the current closed-profile
source, percentage, elapsed time, unavailable sources, and cancellation state.
Completed and partial results refresh Home by rereading the persisted
`HealthSnapshot`; cancellation and failure preserve the previous saved result.
Closing Home requests cooperative cancellation and safely detaches a worker
that does not finish within the bounded shutdown wait.

Home remains bounded to one primary recommendation, at most three attention
items, and four common tasks. Every result review and Action Center control is
navigation-only. Home has no plan, run, verify, privilege, or command-rendering
authority.

## Startup evidence

The final comparable idle-host offscreen series used the plan command with one
warmup:

| Evidence | Result |
| --- | ---: |
| Host idle before benchmark | 98.70 percent |
| Meaningful Home median | 152.750 ms |
| Meaningful Home range | 151.307-155.162 ms |
| Median RSS | 76,136 KiB |
| Realized runtime plugins | `atlas_dashboard` only |
| Cold-start subprocess probes | 0 |
| Active timers | 0 |
| Running `QThread` instances | 0 |
| System Check service/worker imports | 0 |
| Qt widgets | 384 |

Meaningful Home remains below the public v18 ceiling of 172.618 ms and RSS
remains below 86,466 KiB. Every structural startup contract passes.

The active Code/Codex, Firefox, Baloo, and local development-service cgroups
were paused only for the benchmark by a separate transient user-systemd
service. A second transient watchdog provided independent recovery. The
benchmark service restored every cgroup and the original `balanced` power
profile before reporting success; readback confirmed each freezer state was
`running` and both transient units were inactive or removed.

Earlier active-desktop diagnostics measured 208.980-220.424 ms and a
cache-neutral master/Phase 2 delta of 4.549 ms. Those runs remain useful
environment-sensitivity evidence but do not replace the final comparable
idle-host release gate.

## UI and interaction evidence

- Empty, stale, partial, cancelled, failed, and completed/error paths are
  covered by deterministic service and UI fixtures; critical finding ordering
  is covered by Home service tests.
- The Phase 2 Home matrix covers system, dark, light, and high-contrast themes;
  860, 1180, and 1400 DIP widths; and 100, 140, and 200 percent font scales:
  36 combinations passed.
- The inherited real-shell validator passed 400/400 offscreen theme, navigation
  mode, viewport, scale, and locale cases with keyboard navigation, visible
  focus, resize, pointer, and contrast checks.
- Keyboard-only Check now, cancel, Action Center review, and route activation
  passed.

These are isolated offscreen results, not physical Wayland/X11 or assistive
technology certification. Live desktop and 1.4/2.0 compositor-scale evidence
remain Phase 6 work.

## Verification

```text
just test-file test_home_service              16 passed
just test-file test_home_ui                    8 passed, 39 subtests passed
just test-file test_system_check_home_flow     8 passed
just test-file test_system_check_service       8 passed
benchmark_startup.py --runs 10 --warmups 1     startup, RSS, and structure passed
validate_v16_phase7_ui.py --scope automated    400 passed
just lint                                      passed
just typecheck                                 passed
```

## Compatibility and deferred work

- Stable routes, aliases, settings, favorites, and persisted v18 data remain
  unchanged.
- The same read-only collector profile retains explicit Traditional and Atomic
  applicability; no package or deployment mutation moved into Home.
- Action Center remains the sole execution trust boundary.
- Phase 3 owns the canonical System Check page and compatibility adapters.
- Phase 4 owns the reviewed Action Center v3-to-v4 finding-context migration.
- Physical Fedora and live accessibility certification remain Phase 6 work.

Proposed commit message:

```text
feat(home): add explicit asynchronous system check
```
