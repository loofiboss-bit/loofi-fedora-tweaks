# v17 Phase 2 -- Independent Update Plans

Date: 2026-07-20
Status: implementation and deterministic matrix complete

- Software & Updates presents separate Fedora, Flatpak, and firmware review
  actions; the former direct Update All path no longer mutates.
- Traditional Fedora plans exact NEVRA candidates and verifies those identities
  plus package database health after `upgrade`.
- Atomic Fedora stages one `rpm-ostree upgrade`, records the pending deployment
  checksum, waits for reboot, and succeeds only when that deployment is booted.
- Flatpak plans exact refs/commits and uses non-interactive update flags.
- Firmware plans GUID/version/checksum facts and uses fwupd JSON history with a
  reboot-aware terminal failure when expected history is absent after reboot.

Unit coverage verifies all branches without host mutation. Physical Atomic and
firmware evidence remains a Phase 6 release gate.
