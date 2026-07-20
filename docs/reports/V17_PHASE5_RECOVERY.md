# v17 Phase 5 -- Recovery-point Convergence

Date: 2026-07-20
Status: complete

- Backup and Snapshot creation share `create-recovery-point`.
- Timeshift and Snapper are the only executable backends. Raw Btrfs remains
  manual-only.
- Preflight records the backend and existing listing; verification requires a
  newly listed recovery point with the exact description.
- Restore and delete remain separate manual/high-risk operations outside the
  Assurance claim.
- The five canonical UI surfaces report zero direct execution paths under
  `scripts/validate_v17_assurance.py`.
