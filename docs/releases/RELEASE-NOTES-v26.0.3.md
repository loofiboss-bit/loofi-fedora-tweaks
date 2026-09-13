# v26.0.3 "Everyday"

Published 2026-09-13. Public release evidence is recorded in [V26_RELEASE_PUBLICATION.md](../reports/V26_RELEASE_PUBLICATION.md).

## Changes

- Check System, Flatpak and Firmware explicitly from Updates. Results retain
  freshness, source failures, candidates and restart information independently.
- Return to saved runs from Home and explicitly check pending results.
- Use clearer action labels and distinguish waiting for restart from verified success.
- Keep technical output and plan explanations behind accessible disclosures.

## Compatibility and limits

No new public CLI/API surface or execution authority. Existing Action Center
records and six destinations are preserved. The overview is advisory and uses
versioned atomic saved state; future schemas are not overwritten.

Physical Wayland, screen-reader, Polkit, reboot and fresh Kinoite qualification
are separate from offscreen checks. See [qualification](../reports/V26_RELEASE_QUALIFICATION.md)
and [publication evidence](../reports/V26_RELEASE_PUBLICATION.md).
