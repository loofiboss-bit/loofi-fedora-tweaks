# V23 Phase 6 — Local Release Readiness

Date: 2026-07-29
Release candidate: v23.0.0 "Compass"
Source identity: `WORKTREE@a26b540c71be86b9e4f4fcd74f1d062da4fbad23`
Status: local candidate ready; exact-commit and external gates open

## Result

Compass product metadata, release notes, changelog, AppStream metadata,
beginner/user/admin/troubleshooting documentation, and deterministic candidate
screenshots are synchronized to v23.0.0. Five local release artifacts plus
checksums, a CycloneDX SBOM, and in-toto provenance pass the local candidate
gate.

This is not an exact-commit, signed, installed, or public release. The source
identity combines the current Git HEAD with dirty WORKTREE content. The
machine-readable
[`V23_PHASE6_LOCAL_CANDIDATE.json`](V23_PHASE6_LOCAL_CANDIDATE.json) binds the
artifact hashes to a SHA-256 snapshot of every tracked or untracked source
input except the self-referential candidate report.

## Candidate artifacts

The isolated candidate contains exactly:

- `loofi-fedora-tweaks-23.0.0-1.fc44.noarch.rpm`
- `loofi-fedora-tweaks-api-23.0.0-1.fc44.noarch.rpm`
- `loofi-fedora-tweaks-daemon-23.0.0-1.fc44.noarch.rpm`
- `loofi-fedora-tweaks-v23.0.0.flatpak`
- `loofi_fedora_tweaks-23.0.0.tar.gz`
- `SHA256SUMS.txt`
- `loofi-fedora-tweaks.cdx.json`
- `loofi-fedora-tweaks.intoto.jsonl`

The local gate verifies:

- complete SHA-256 coverage of the candidate directory;
- matching CycloneDX and in-toto subjects;
- v23.0.0 RPM names, epoch/version/release/architecture, payload digests, and
  expected base/API/daemon boundaries;
- v23.0.0 source-distribution metadata plus an isolated no-dependency wheel
  build/install/readback;
- import of the Flatpak bundle into a fresh temporary OSTree repository; and
- unsigned local status without presenting digest verification as a signature.

Artifact and evidence hashes are recorded only in the machine-readable report.
They are local WORKTREE identities and must be rebuilt after an authorized
release commit.

## Documentation and screenshots

The Phase 6 documentation describes the six closed profiles, explicit
collection, **Possibly related** boundary, one safe next step, compatible
follow-up comparison, retrieval-only API, and Support Bundle v13. It also
states that v22.0.0 remains the public release.

[`V23_PHASE6_SCREENSHOTS.json`](V23_PHASE6_SCREENSHOTS.json) records 12
offscreen frames and six retained contact sheets across wide and compact
viewports. The real lazy `MainWindow` is used with isolated HOME/XDG state and
mutating/asynchronous commands rejected. This is deterministic presentation
evidence only; it does not prove physical Wayland, keyboard traversal, or Orca
speech.

## Authorized skips kept open

The user authorized Phase 6 work to continue without treating these human or
external gates as blockers:

- fresh Fedora 44 Kinoite/Atomic profile qualification;
- manual keyboard-only traversal; and
- audible Orca journey.

Each remains `open-user-authorized-skip` in the race lock and candidate report.
None is reported as passed.

## External gates still required

- Resolve the occupied historical `v23.0.0` tag without overwriting, moving, or
  deleting its Architecture Hardening evidence.
- Create an intentional clean release commit and rebuild all artifacts from
  that exact commit.
- Sign RPMs and verify signatures separately from payload digests.
- Run disposable-target v22-to-v23 upgrade and clean v23 install lifecycles;
  no host installation was authorized here.
- Read back canonical CI, CodeQL, GitHub attestations/assets, COPR terminal
  success, public repository metadata, clean Fedora 44 installation, wiki, and
  public documentation.

No commit, push, tag mutation, host installation, signing, COPR action, GitHub
release, wiki change, or other remote publication was performed.
