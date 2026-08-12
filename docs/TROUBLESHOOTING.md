# Loofi Fedora Tweaks — Troubleshooting

Common issues and recovery steps for v25.0.4 "Proof".

## 1) Quick Diagnostics

Run these first:

```bash
loofi-fedora-tweaks --cli doctor
loofi-fedora-tweaks --cli info
loofi-fedora-tweaks --cli support-bundle
```

Proof is the current public release. Historical v25.0.0–v25.0.3 tags remain
preserved as separate lineages.

Optional alias:

```bash
alias loofi='loofi-fedora-tweaks --cli'
```

Do not run Loofi with `sudo`. Privileged operations request authorization
through `pkexec` and polkit.

---

## 2) App Does Not Start

### Missing PyQt6

```bash
pkexec dnf install python3-pyqt6
```

### Qt platform plugin errors (`wayland` / `xcb`)

```bash
pkexec dnf install qt6-qtwayland
QT_QPA_PLATFORM=xcb loofi-fedora-tweaks
```

### Startup crash without a clear UI message

```bash
tail -n 200 ~/.local/share/loofi-fedora-tweaks/startup.log
```

Proof loads built-in pages on demand. A failing specialist page should not stop
Home or the six Standard destinations from opening. Include the exact route and
startup log when reporting an import failure.

---

## 3) A Route Is Missing or Unavailable

The primary shell shows Home, Software & Updates, System, Network & Security,
Desktop, and Settings. Specialist routes remain grouped and searchable under
Specialist Tools.

Use `Ctrl+K` to search routes and settings. `Ctrl+Shift+K` uses the same search
model filtered to actions. Both shortcuts use this unified search surface.
Policy may keep a result unavailable when:

- a logical specialist component is missing or incomplete;
- the route is incompatible with Traditional or Atomic Fedora;
- a required host capability is absent.

Do not bypass the unavailable state by importing a UI module directly. Proof
ships logical core/specialist isolation in the base RPM; there is no physical
`loofi-fedora-tweaks-extras` package.

---

## 4) CLI Command Fails

Use the full command:

```bash
loofi-fedora-tweaks --cli info
```

For a source checkout:

```bash
PYTHONPATH=loofi-fedora-tweaks python3 loofi-fedora-tweaks/main.py --cli info
```

GUI grouping does not remove CLI commands. If a specialist CLI command fails,
inspect its reported host dependency.

---

## 5) Privileged Actions Fail

Symptoms include failed package/service/firewall operations or a missing auth
prompt.

```bash
which pkexec
pkexec true
ls /usr/share/polkit-1/actions/org.loofi.fedora-tweaks.policy
```

Confirm that a desktop polkit agent is running. Supported commands use
list-based executor policy. If the preview reports that a command is rejected
or not allowlisted, use the supported GUI or CLI workflow instead of a shell
string.

---

## 6) Action Center Does Not Run or Verify

Action Center is intentionally fail-closed. Common outcomes:

- **Plan expired:** create and review a fresh plan. Plans are not reusable after
  expiry.
- **Preflight changed:** review the new system state before confirming again.
- **Confirmation required:** apply only the exact reviewed plan with explicit
  confirmation.
- **No rollback acknowledgement required:** read the warning and acknowledge it
  separately only if you accept the risk.
- **Mutation lease busy:** another GUI or CLI process owns the single-mutation
  lease; wait for it to finish or inspect the recorded owner.
- **Interrupted run:** inspect history. Loofi never resumes, retries, or rolls
  back automatically.
- **Verification failed:** treat the run as unverified even when the command
  exited successfully.
- **Manual-only:** the definition does not permit execution on this Fedora
  variant or is outside the supported local host-mutation boundary.

Read-only inspection:

```bash
loofi-fedora-tweaks --cli action-center list --target 44
loofi-fedora-tweaks --cli action-center history --limit 20
```

Home and global search may open or preselect an Action Center item, but they
cannot create a plan or execute it.

---

## 7) Traditional vs Atomic Fedora

Check the detected system:

```bash
loofi-fedora-tweaks --cli info
```

Traditional Fedora uses DNF. Atomic Fedora uses rpm-ostree-aware paths and
keeps operations manual-only when the DNF contract is not safe. In particular,
do not force Traditional package-cache commands on an Atomic host. Review the
unavailable explanation and follow the documented rpm-ostree guidance.

---

## 8) State Doctor and Recovery

- **Corrupt JSON or database:** run
  `loofi-fedora-tweaks --cli --json state doctor`, preserve the reported file,
  and follow its domain-specific guidance. Corruption is never silently treated
  as healthy empty history.
- **Disk full:** free space outside Loofi first. Atomic writes leave the
  canonical file intact when replacement fails.
- **Permission denied:** verify ownership before restricting the file to the
  current user. Do not run Loofi with `sudo`.
- **Stale lock:** confirm no GUI, CLI, or daemon owner is active before archiving
  a lock reported stale. Lock timeout is a busy condition, not corruption.
- **Failed migration:** retain the legacy file and `.lkg` copy. Future schemas
  stay read-only; do not downgrade them by hand.
- **Restore rejected:** do not bypass validation. Check the plan ID, hashes,
  schema, duplicate paths, traversal checks, and size limits.

Loofi preserves settings, favorites, routes, and readable Action Center
v1-v3 records. Writable Action Center plans and runs migrate atomically to
schema v4; unknown future schemas remain read-only. Package installation does
not migrate per-user XDG files.

If an Action Center run is verified but the finding still appears, run
**Check again** after any required reboot. `verified` describes the action
verifier; `resolved` requires a later compatible System Check. A
`not_comparable` result means the required source was unavailable or the
profile, Fedora variant, or ordering did not match. Support Bundle v13
preserves the bounded System Check and Trusted Change Journal evidence and can
include one explicitly selected troubleshooting session. Paths, identities,
secrets, network identifiers, command output, and recovery commands are
stripped or redacted.

---

## 9) Retired Marketplace and Local Profiles

```bash
loofi-fedora-tweaks --cli --json plugin-marketplace search
loofi-fedora-tweaks --cli plugins list
```

The first command returns exit status 2 with a stable schema-v3
`feature_retired` result. This is expected: Proof has no public Marketplace or
external Python execution path.

Existing third-party files remain untouched. Open **Specialist Tools → Local
Profiles → Legacy Extensions** or run `plugins list` to inventory them without
importing their code. Export anything you need before removing files manually.

Use a reviewed built-in provider for application features. Use an explicit
local JSON profile for data-only settings; invalid schemas, paths, values, and
oversized imports are rejected. For help with migration, attach a support bundle
to a GitHub issue without including the extension code itself.

---

## 10) Specialist Tool Checks

Virtualization:

```bash
systemctl status libvirtd
lscpu | grep -i virtualization
lsmod | grep -i kvm
```

Loofi Link:

```bash
systemctl status avahi-daemon
pkexec dnf install avahi avahi-tools nss-mdns
```

AI Lab:

```bash
ollama --version
ollama list
```

These tools live under Specialist Tools and may report an unavailable state
when their host dependencies are absent.

---

## 11) Logs and Support Bundle

```bash
loofi-fedora-tweaks --cli support-bundle
loofi-fedora-tweaks --cli troubleshoot export SESSION_ID
journalctl --user --since "1 hour ago"
```

The selected-session form writes Support Bundle v13 with at most one retained
session, one comparison, 50 findings, 25 related changes, and 25 linked
plan/run status records. It never starts a troubleshooting collection.

---

## 12) Reporting Issues

Include:

1. Fedora version and whether it is Traditional or Atomic
2. whether the affected route is a primary or Specialist Tools route
3. exact route, action, or command
4. full error output and reproduction steps
5. support-bundle path

Issues: <https://github.com/loofiboss-bit/loofi-fedora-tweaks/issues>
