# Control Center Redesign Qualification

Local implementation candidate, verified on 2026-10-07. The application version,
CLI, product identity, configuration paths, and operation authority are preserved.
The original qualification excluded Git publication and installation.
The user subsequently authorized local installation and a pull request.

## Automated checks

| Check | Result |
|---|---|
| `just verify` | PASS: lint, mypy, architecture, product catalog, tests and coverage |
| Full suite | 4,698 passed; 33 skipped; 1,885 subtests passed |
| Coverage | 85.72%, above the maintained 85% threshold |
| `just check-packaging` | PASS: requirements synchronization and wheel/sdist manifests |
| `just build-rpm` | PASS: local Fedora 44 RPM build |
| RPM contents | Dashboard service, Overview, shared controller, process sampling helper and stylesheet present |
| `python3 scripts/sync_wiki_docs.py --check` | PASS |
| `git diff --check` | PASS |

The suite emitted 22 warnings, principally SQLite resource warnings, compatibility
import deprecations, and a deliberately duplicated ZIP member fixture. The final
run had no failed tests or Qt callback/worker-destruction aborts.

The focused tests cover route restoration and settings isolation, legacy Tweaks
links, Tools persistence/save failure, search navigation and Action Center review,
success/failure/cancellation/drift in tweak operations, missing/failed/stale metric
sources, multiple batteries and GPUs, counter reset baselines, bounded NVIDIA
queries, sleeping devices, worker pause/resume, and deferred window destruction.

The locally built RPM is `rpmbuild/RPMS/noarch/loofi-fedora-tweaks-32.2.0-1.fc44.noarch.rpm`.
Its SHA-256 is `ec1af12ad0622aa7c61b36e470634968f367ec9b5ecaf307e8b036e28d77d7ca`.
This is build evidence, not installation or repository signature verification.

## Rendering and keyboard evidence

[Machine-readable matrix](control-center-rendering-checks.json) contains 900
captures: 25 canonical reachable primary/tool views, three themes, three window
sizes, and four rendering configurations. The configurations are 100%, 150%,
200% Qt scaling, and enlarged text at 100% scaling. Each configuration also has
one long-description capture, for 904 generated PNGs in total.

All requested logical sizes were preserved: 900x650, 1280x800 and 1600x900.
All 900 entries have zero outer horizontal scroll ranges and zero wrapped-label
height deficiencies. All 18,000 visible keyboard-focus traversals passed.
Technical tables retain their own horizontal scrolling when their full column
names need more space. Representative views were inspected visually, including
small-window enlarged text, System Info actions and values, hardware reflow,
Apps status, Tweaks filters, process/network headers, and Activity empty state.

The committed [Overview](images/control-center/overview-dark-1280x800.png), main
page and tool examples in `images/control-center/` use deterministic example
hardware and saved-result data. The [wiki gallery](../wiki/Screenshots.md) and
repository README now show the redesigned interface.

Reproduce from the repository root:

```sh
just verify
just check-packaging
just build-rpm
PYTHONPATH=loofi-fedora-tweaks python3 scripts/capture_control_center_screenshots.py /tmp/control-center-100 --scale 1
PYTHONPATH=loofi-fedora-tweaks python3 scripts/capture_control_center_screenshots.py /tmp/control-center-150 --scale 1.5
PYTHONPATH=loofi-fedora-tweaks python3 scripts/capture_control_center_screenshots.py /tmp/control-center-200 --scale 2
PYTHONPATH=loofi-fedora-tweaks python3 scripts/capture_control_center_screenshots.py /tmp/control-center-large --large-text
```

The capture script isolates fixture configuration/data and replaces hardware,
network and process probes. Its report does not replace visual inspection.

## Desktop qualification pending

| Surface | Status |
|---|---|
| Physical KDE session, authorization dialogs, actual desktop scaling | `unverified` |
| Physical GNOME session and system color-scheme changes | `unverified` |
| Screen reader and assistive technology | `unverified` |
| Actual multi-GPU/multi-battery systems and NVIDIA hardware | `unverified` |

Perform the KDE manual pass first, then qualify GNOME and assistive technology
separately. Offscreen fixture tests are not physical desktop or hardware evidence.
No collector tools or drivers were installed.

## Authorized local installation follow-up

On 2026-10-07, DNF reinstalled only `loofi-fedora-tweaks` from the locally built
RPM after an assumed-no transaction review. The installed NEVRA remains
`loofi-fedora-tweaks-32.2.0-1.fc44.noarch`; the payload contains the redesign.
No application process was running during replacement.

- `rpm -V loofi-fedora-tweaks`: clean.
- `dnf5 --cacheonly check`: passed.
- All 391 installed Python/stylesheet files match the working tree byte for byte.
- All 31 recorded configuration/data/state files retained their original hashes.
- Installed GUI starts on Overview in an isolated offscreen smoke test; hardware
  collection was replaced with a fixture for that test.

The local command-line package transaction skipped OpenPGP checks. Its SHA-256
was checked against the qualified build; this is not repository signature
verification. Physical desktop qualification remains separate.
