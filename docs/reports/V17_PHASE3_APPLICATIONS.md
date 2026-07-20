# v17 Phase 3 -- Application Plans

Date: 2026-07-20
Status: complete

- Application install/remove controls create exactly one Action Center plan and
  open its review surface.
- Fedora RPM and Flatpak are accepted; URLs, option-like values, shell catalog
  entries, vendor RPM downloads, and repository bootstrap remain manual-only.
- Traditional Fedora verifies exact install NEVRA or package absence. Atomic
  Fedora verifies the requested package set in a staged deployment, then the
  expected boot. Flatpak verifies exact commit or absence.
- Install is low risk with confirmation. Remove is medium risk and requires
  explicit no-rollback acceptance.
- Hidden batch controls and their direct execution paths were removed.
