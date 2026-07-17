# v15 Phase 2 Startup Evidence

## Scope

This report records the Phase 2 top-level lazy-loading result against the
authoritative v14 measurements in `V15_PHASE0_BASELINE.md`. It does not cover
the Phase 3 shell rewrite or any later v15 work.

## Method

The benchmark used one discarded warm-up and ten separate Python processes on
the same workstation. Each process used a temporary Standard-mode profile,
empty favorites, `QT_QPA_PLATFORM=offscreen`, and the same meaningful Home
marker: the `atlas_dashboard` placeholder realizing `AtlasDashboardTab`.

```bash
PYTHONDONTWRITEBYTECODE=1 \
QT_QPA_PLATFORM=offscreen \
PYTHONPATH=loofi-fedora-tweaks \
python3 scripts/benchmark_startup.py \
  --warmups 1 \
  --runs 10 \
  --output /tmp/loofi-v15-phase2-startup.json
```

The command records raw per-run milestones, RSS, imports, plugin instances,
Qt widgets, active timers, running QThreads, and subprocess probes. It writes
no telemetry and does not alter the user's persisted profile.

## Results

| Measurement | v14 Phase 0 | v15 Phase 2 | Change |
| --- | ---: | ---: | ---: |
| GUI import median | 149.132 ms | 97.502 ms | 34.62% lower |
| MainWindow median | 4544.718 ms | 165.995 ms | 96.35% lower |
| Meaningful Home median | 4552.202 ms | 172.452 ms | 96.21% lower |
| Meaningful Home range | 4063.653–5181.762 ms | 169.127–178.130 ms | — |
| RSS median | 107446 KiB | 80304 KiB | 25.26% lower |
| RSS range | 106768–107812 KiB | 80104–80384 KiB | — |
| Imported modules | 527 | 331 | 37.19% lower |
| Imported `ui` modules | 38 | 8 | 78.95% lower |
| Imported `ui.*_tab` modules | 30 | 2 | 93.33% lower |
| Built-in runtime instances | 29 | 1 | 96.55% lower |
| Live Qt widgets | 2425 | 333 | 86.27% lower |
| Active page/shell timers at marker | 9 | 0 | eliminated |
| Running QThreads at marker | 2 | 0 | eliminated |
| Subprocess probes before marker | 54 | 0 | eliminated |

All ten measured runs registered 29 data-only specs and exactly one runtime
plugin instance (`atlas_dashboard`). No specialist UI module was imported.

## Phase 2 conclusion

The measured startup root cause is removed. The Phase 0 targets of at least 25%
faster meaningful Home and at least 15% lower RSS are both exceeded. Deferred
notification, status, dependency, and update work is scheduled after the Home
marker, while tray and Pulse initialization is conditional on the existing
background setting.
