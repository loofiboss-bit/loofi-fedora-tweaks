# v17 Phase 4 -- Diagnosis and Cleanup

Date: 2026-07-20
Status: complete

- Slow-system diagnosis remains read-only and only hands an exact failed unit
  to `restart-failed-service`.
- Cleanup analysis hands off to `dnf-clean-all`, `fstrim-all`,
  `vacuum-journal`, or `autoremove-packages`.
- Journal retention accepts only 7, 14, or 30 days and verifies fresh disk
  usage after apply.
- Autoremove records and regenerates the exact preflight package list, verifies
  every removal, and remains manual-only on Atomic Fedora.
- RPM database repair is described as manual troubleshooting, not reclaim.
