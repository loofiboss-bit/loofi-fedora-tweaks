# Loofi Fedora Tweaks 33.0.1 “Concord”

Concord makes the main Fedora workflows clearer and keeps their review and
verification context together. It prioritizes the Overview's CPU, RAM, GPU,
and storage readings; brings Settings and Profiles together in Tweaks; and
organizes application discovery, installed applications, and package sources
under Apps.

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
Fedora 44 KDE/X11 disposable-VM qualification recorded in
[the v33 qualification report](../V33_QUALIFICATION.md). The package version
change from the tested v33.0.0 candidate to 33.0.1 does not change product
behavior; the release workflow builds and reviews the exact 33.0.1 RPM before
publishing it.

Physical desktop hardware, human screen-reader use, Wayland input, GNOME, and
Atomic workflows were not qualified by these results.

## Install from COPR

```bash
pkexec dnf copr enable loofitheboss/loofi-fedora-tweaks
pkexec dnf install loofi-fedora-tweaks
```

See the [changelog](../../CHANGELOG.md) and [roadmap](../../ROADMAP.md) for
the full release history and qualification boundaries.
