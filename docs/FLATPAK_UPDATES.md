# Installation-bound Flatpak updates

The v34.0.1 Accord candidate connects installed applications, update review,
independent verification, and optional runtime maintenance. It is local candidate
work; the latest published release remains v33.0.1 Concord.

## Choose an installation and applications

In **Apps > Installed**, select a Flatpak installation and choose **Check for
updates**. The check reads available candidates; it does not install an update.
In **Updates > Flatpak**, candidates remain grouped by installation. Select one
or several applications, or select all candidates in that installation, and
review the selection. Filtering does not discard the selection.

The user installation, default system installation, and each configured named
installation are distinct. The same application ID, architecture, and branch
can exist in more than one installation. A successful update in one does not
establish the state of another.

Checks show their observation time and can be cancelled. Missing optional
PyGObject/libflatpak support, unreachable sources, unavailable installations,
timeouts, and partial results are explicit. An unavailable installation is not
reported as up to date. Reopening a page or following a navigation link does
not start a check.

## Review and apply

The shared Action Center review shows the selected applications, installation,
origin, versions, and the dependencies or related extensions required by the
resolved transaction. Exact refs and commits are available in the details.

Approval is bound to that resolved operation set, its sources, and its before
and target commits. A changed installation, installed version, source, or
transaction requires a new review. New remotes, application rebases, and
uninstall operations are not automatically approved by this workflow.

The helper runs as the invoking user. Shared installations use Flatpak's native
authorization; never run Loofi or its helper as root. User data is preserved.
Unsigned local `file:` sources in system and named system installations are
unavailable for this workflow. Their native update path cannot guarantee the
reviewed commit; local system sources require verification of signed commits
and signed repository summaries. This restriction does not apply to user
installations. Source trust settings are included in the review binding.
Updates have no automatic rollback. If an update causes a regression, inspect
the exact Activity result and use the application's source for recovery.

## Read the result

Loofi independently reads installed commits from the same installation after
execution. Results distinguish selected applications and reviewed dependencies,
including partial completion, cancellation, failures, and unavailable readback.
A command's exit status alone does not establish successful verification.

The result links to its actual Activity run. **Inspect unused runtimes** opens
the existing maintenance flow with the relevant installation selected. Runtime
inspection and removal remain separate explicit actions. The link does not
promise recoverable disk space or start cleanup.

Older saved plans and runs stay readable. When they lack installation-bound
evidence, Loofi requires a fresh review rather than guessing an installation.

## CLI

Read-only discovery uses the same service as the GUI:

```bash
loofi-fedora-tweaks --cli updates flatpaks
loofi-fedora-tweaks --cli --json updates flatpaks --installation user
loofi-fedora-tweaks --cli updates flatpaks --installation work \
  --ref app/org.example.Editor/x86_64/stable
```

Repeat `--ref` to inspect several exact refs. This command does not prepare or
execute an update. A failed or partial inspection returns a nonzero exit code
while retaining available installation results.

Prepare a separately reviewed action with the existing changes interface:

```bash
loofi-fedora-tweaks --cli changes apply update-flatpaks \
  --param installation=user \
  --param 'refs=["app/org.example.Editor/x86_64/stable"]' --dry-run
```

The optional `installation` and `refs` parameters narrow the update. With no
filters, review covers all available installations explicitly and execution
processes their transactions sequentially. The existing CLI confirmation,
plan identity, and verification rules still apply.

## Evidence boundaries

Automated qualification uses mocked domain tests, Qt interaction/rendering
tests, package checks, and a disposable Fedora KDE guest with a local Flatpak
repository. See [v34 qualification](V34_QUALIFICATION.md) for actual results.
These checks do not establish behavior for every remote, physical desktop,
hardware configuration, or assistive technology.
