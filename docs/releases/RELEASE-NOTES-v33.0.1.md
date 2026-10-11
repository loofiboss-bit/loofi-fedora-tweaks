# Loofi Fedora Tweaks 33.0.1 “Concord”

Concord makes the main Fedora workflows clearer and keeps their review and
verification context together. It prioritizes the Overview's CPU, RAM, GPU,
and storage readings; brings Settings and Profiles together in Tweaks; and
organizes application discovery, installed applications, and package sources
under Apps.

Published on 2026-10-12 (Europe/Stockholm). [Publication evidence](../reports/V33.0.1_RELEASE_PUBLICATION.md) records the exact tag, public assets, attestation, and successful COPR build 11109761.

## Highlights

- Preserve profile drafts while moving between settings and profiles. Show
  each setting's user or computer scope and its requested and verified values.
- Review only the exact profile copy that was saved successfully.
- Keep application selections independent from search filters and show exact
  package, source, and installation scope before a reviewed operation.
- Keep operation origin, result, and return navigation together. Link to
  Activity only when the operation has a real run ID.
- Preserve existing route IDs, CLI and JSON contracts, portable profile
  format, history schema, and Action Center execution ownership.

## Qualification

The feature source passed the maintained automated, package, rendering, and
previous Fedora 44 KDE/X11 disposable-VM qualification recorded in
[the v33 qualification report](../V33_QUALIFICATION.md).

The exact 33.0.1 candidate failed two subsequent VM GUI runs:
[CI run 38178492268](https://github.com/loofiboss-bit/loofi-fedora-tweaks/actions/runs/38178492268)
reported an AT-SPI/WebDriver timeout after five passed tests, and
[release run 38178492259](https://github.com/loofiboss-bit/loofi-fedora-tweaks/actions/runs/38178492259)
reported a guest Python/Qt6Gui crash after four passed tests. The root cause
remains unresolved. The maintainer explicitly authorized publication with
this VM qualification exception. All other release gates, including unit
tests, Fedora package review, installed RPM smoke tests, checksums,
attestations, and COPR package verification, remain required.

Physical desktop hardware, human screen-reader use, Wayland input, GNOME, and
Atomic workflows were not qualified by these results.

## Install from COPR

```bash
pkexec dnf copr enable loofitheboss/loofi-fedora-tweaks
pkexec dnf install loofi-fedora-tweaks
```

See the [changelog](../../CHANGELOG.md) and [roadmap](../../ROADMAP.md) for
the full release history and qualification boundaries.
