# Release checklist

Use this checklist to prepare a version candidate and qualify its package.
The repository's `master` push and `v*` tag workflows can publish automatically,
so keep local verification separate from release authorization.

## 1. Choose a version

Check the active source version and inspect local and remote tags before
selecting the next version. Never reuse a tag that points to another commit
lineage. Select the next version and codename from the reviewed branch and
available tag history; do not copy an older candidate value.

```bash
python3 scripts/bump_version.py --check
git tag --list 'v*'
git ls-remote --tags origin
```

Run `scripts/bump_version.py` with the reviewed version and codename using
`--dry-run`. Review its proposed changes, then repeat the command without
`--dry-run` and run `--check` to confirm the active version sources agree.

The script checks and updates `loofi-fedora-tweaks/version.py`,
`loofi-fedora-tweaks.spec`, and `pyproject.toml`. It does not require retired
statistics or adapter tools and does not create workflow scaffolding.

## 2. Keep documentation current

- [ ] Add an accurate unreleased or dated release entry to `CHANGELOG.md`.
- [ ] Update `ROADMAP.md` to distinguish candidate, released, and deferred work.
- [ ] Regenerate `docs/TWEAKS.md` from the catalog.
- [ ] Update current documentation version headings and preserve physical
  qualification as pending or unverified until it has been performed.

```bash
python3 scripts/gen_tweaks_doc.py
python3 scripts/gen_tweaks_doc.py --check
```

## 3. Verify code and packages

Run the maintained gates from the repository root:

```bash
just verify
just build-rpm
just check-packaging
```

`just verify` includes lint, mypy, architecture checks, tests, and the 85%
coverage gate. `just check-packaging` checks generated requirements and builds
the package manifest. `just build-rpm` creates a local RPM; neither command
installs it or publishes it.

Also inspect the final changes and working tree:

```bash
git diff --check
git status --short
python3 scripts/bump_version.py --check
python3 scripts/gen_tweaks_doc.py --check
```

## 4. Qualify desktop behavior

In a GNOME session, try all GNOME Files controls. In a KDE Plasma session,
try the Dolphin and KWin controls, including KWin runtime readback. For each setting, verify the selected value
by reading it back, then use its history-based restore and verify the previous
value. Check that a missing Files schema or Dolphin installation is reported
as unavailable. Do not infer physical desktop qualification from offscreen
tests or package builds; record each desktop as verified, pending, or
unverified.

## 5. Understand publication triggers

The CI workflow validates pull requests and pushes. The auto-release workflow
also runs on pushes to `master` and `v*` tags; when all release gates pass, it
can create the version tag and publish release artifacts, then publish to the
configured COPR project. Do not push a candidate to `master`, create a release
tag, or start a release workflow unless publication has been explicitly
authorized.

For an authorized release, verify the workflow's checks and independently read
back the tag, GitHub release assets, and COPR build/package before describing
the release as public. A green local build or an edited document is not
publication evidence.

## Local package installation

When local installation is explicitly in scope, inventory the installed RPM
and running application, back up app settings privately, and simulate the
exact package transaction. Install only after the simulation succeeds. Read
back NEVRA, package integrity, CLI behavior, settings checksum, and package
consistency. Preserve user settings and do not infer physical qualification
from generated screenshots.
