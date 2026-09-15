# Troubleshooting Runbooks — v29.0.1 "Utility"

When experiencing issues with Loofi Fedora Tweaks or underlying system services, follow these diagnostic runbooks. Loofi is built to fail closed: when a capability is missing or unverified, it reports the exact reason rather than guessing.

---

## 1. Initial Diagnostic Triad

Always begin with these three read-only diagnostic checks:

```bash
# 1. Inspect dependency health, pkexec availability, and environment
loofi-fedora-tweaks --cli doctor

# 2. Inspect platform facts and detected deployment backend
loofi-fedora-tweaks --cli --json info

# 3. Export a sanitized diagnostic archive
loofi-fedora-tweaks --cli support-bundle
```

The support bundle archive is created in your home directory by default as `~/loofi-support-bundle-YYYYMMDD_HHMMSS.zip`; the CLI output prints the exact path. It contains redacted environment facts and recent change journal records.

---

## 2. The Application Does Not Launch

### Symptom: Command returns immediately or shows error
1. **Verify Binary & Version**:
   ```bash
   which loofi-fedora-tweaks
   loofi-fedora-tweaks --version
   ```
2. **Check for Prohibited Root Launch**:
   If you launched with `sudo loofi-fedora-tweaks`, the application will abort. Loofi must run as a regular desktop user.
3. **Qt Platform Plugin Errors**:
   On Wayland sessions, if Qt cannot initialize the Wayland client:
   ```bash
   # Test with explicit Wayland platform
   QT_QPA_PLATFORM=wayland loofi-fedora-tweaks

   # Fallback test with X11 / XWayland
   QT_QPA_PLATFORM=xcb loofi-fedora-tweaks
   ```
4. **Inspect Application Logs**:
   GUI startup diagnostics are stored in `~/.local/share/loofi-fedora-tweaks/startup.log`. The centralized application log is stored in `${XDG_STATE_HOME:-~/.local/state}/loofi-fedora-tweaks/app.log`.

---

## 3. Authorization Dialog Does Not Appear

### Symptom: Applying a change hangs or fails with authorization error
Persistent system changes require privilege escalation via Polkit through `pkexec`.
1. **Verify `pkexec` binary**:
   ```bash
   command -v pkexec
   pkexec --version
   ```
2. **Check Active Desktop Polkit Agent**:
   Ensure your desktop environment has a running authentication agent:
   - GNOME: `/usr/libexec/polkit-gnome-authentication-agent-1`
   - KDE: `/usr/libexec/polkit-kde-authentication-agent-1`
   - Sway / Hyprland: `polkit-gnome` or `polkit-kde-agent`
3. **User Cancellation**:
   If the Polkit prompt was dismissed or timed out, restart the task from its owning page. Saved follow-up state remains visible in **Activity & Recovery**.

---

## 4. Package Manager or DNF Lock Contention

### Symptom: Update checks or package changes fail with lock error
DNF5 protects its state using lock files. If another package transaction (e.g. background check from GNOME Software or KDE Discover) is running:
- Do not run `kill -9` on DNF5 processes.
- Allow the active transaction to complete.
- Verify whether other package managers are running:
  ```bash
  ps aux | grep -E 'dnf|rpm-ostree|packagekit'
  ```
- Once clear, re-run `loofi updates check`.

---

## 5. Update shows a source as "Unavailable"

### Symptom: One source shows an error or unavailable status
Loofi treats system packages, Flatpaks, and firmware as separate sources.
- **System Packages**: On Atomic hosts, DNF is intentionally unavailable; `rpm-ostree` is used instead.
- **Flatpak**: If the `flatpak` binary is missing or no remotes are configured, Flatpak is marked unavailable.
- **Firmware (`fwupd`)**: Ensure the `fwupd` daemon is running:
  ```bash
  systemctl status fwupd.service
  ```

---

## 6. Atomic Staged Deployment Awaiting Reboot

### Symptom: Update executed, but system still reports previous versions
On Fedora Silverblue, Kinoite, and Atomic desktops, `rpm-ostree` creates staged deployment trees:
1. The upgrade is downloaded and staged into a new ostree commit.
2. The change only becomes active when you reboot.
3. Loofi deliberately **does not** reboot your machine automatically.
4. Restart when convenient using normal desktop controls.
5. After reboot, run:
   ```bash
   loofi changes verify RUN_ID
   ```

---

## 7. Reporting an Issue

When opening an issue on [GitHub Issues](https://github.com/loofiboss-bit/loofi-fedora-tweaks/issues), include:
1. Fedora release and architecture (`cat /etc/fedora-release && uname -m`).
2. Desktop environment and display server (Wayland or X11).
3. Output of `loofi-fedora-tweaks --cli doctor`.
4. Relevant excerpts from the support bundle.
