# Loofi Fedora Tweaks 32.4.0 — Care

Care is an unreleased local candidate built on the existing personalization,
trust, search, accessibility, and responsive-layout work in PR #56.

## Applications and storage

Inspect an exact Flatpak installation for its origin remote, runtime, reported
installed size, and locally recorded app/runtime end-of-life warnings. An absence
of a recorded warning is not a support guarantee. Installed applications can be
filtered by source and installation and sorted by name or reported size.

Review unused runtimes in one installation, choose exact refs, and confirm their
removal through Action Center. Changes to the reviewed inventory require a new
review. Removal preserves application data, checks the remaining inventory, and
records partial failures without an automatic rollback. System and named
installations are shared; other users' private inventories are not inspected.

Reported installed sizes include shared objects and cannot promise reclaimed
disk space. PyGObject and libflatpak are optional recommended RPM dependencies;
missing support is explicitly unavailable and is never installed by the app.

## Updates

Source-specific diagnostics connect failed system, Flatpak, and firmware checks
to Health and the exact recorded operation. Diagnostics are read-only. CLI and
GUI update checks use the same source observations; a failed source is not
reported as up to date.

## Delivery status

See [Care qualification](../CARE_VERIFICATION.md) for dated automated, isolated
integration, rendering, and packaging evidence. Physical KDE/GNOME behavior,
screen-reader use, and real-session Polkit prompts require separate verification.
The built RPM has been installed locally. This candidate has not been merged or
published; physical desktop and assistive-technology qualification remains open.
