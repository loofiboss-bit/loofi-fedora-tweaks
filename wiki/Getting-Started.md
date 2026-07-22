# Getting Started

This guide will help you get started with Loofi Fedora Tweaks, whether you prefer the GUI or CLI interface.

---

## Run Modes

Loofi Fedora Tweaks supports four distinct run modes:

| Mode | Command | Use Case |
|------|---------|----------|
| **GUI** | `loofi-fedora-tweaks` | Daily desktop usage with visual interface |
| **CLI** | `loofi-fedora-tweaks --cli <command>` | Scripting, automation, remote administration |
| **Daemon** | `loofi-fedora-tweaks --daemon` | Background scheduled tasks |
| **Web API** | `loofi-fedora-tweaks --web` | Headless/remote integration (optional) |

### Shell Alias Recommendation

For easier CLI usage, add this to your `~/.bashrc` or `~/.zshrc`:

```bash
alias loofi='loofi-fedora-tweaks --cli'
```

Then use: `loofi info` instead of `loofi-fedora-tweaks --cli info`

---

## First-Run Wizard

The first time you launch the GUI, a 5-step wizard guides you through initial setup:

| Step | Description |
|------|-------------|
| **1. Welcome** | Introduction to key features and capabilities |
| **2. System Detection** | Auto-detects hardware profile, package manager (dnf vs rpm-ostree), and desktop environment |
| **3. Health Check** | Scans for: disk space, package system health, firewall status, backup tools, SELinux state |
| **4. Recommended Actions** | Suggests fixes for detected issues (e.g., "Enable firewall", "Install backup tool") with risk badges |
| **5. Ready** | Confirms setup is complete and opens the main window |

The wizard creates a profile at `~/.config/loofi-fedora-tweaks/profile.json` and won't appear again unless you delete that file.

---

## GUI Navigation

### Focused Sidebar

Standard mode uses six destinations:

| Area | Purpose |
|------|---------|
| **Home** | Prioritized status, recommendations, and safe links |
| **Software & Updates** | Applications, repositories, updates, cleanup, upgrades, and Action Center |
| **System** | System information, performance, processes, hardware, storage, diagnostics, and recovery points |
| **Network & Security** | Connections, DNS, privacy, firewall, exposure, and backups |
| **Desktop** | Appearance, windows, and displays |
| **Settings** | Appearance, behavior, Advanced mode, Repair Loofi, and About |

Enable **Settings → Advanced Tools** to add the Advanced destination. Specialist routes remain available without changing their safety or confirmation requirements.

### Key UI Features

- **Global Search**: Press `Ctrl+K` to find routes, settings, and safe action entry points
- **Favorites**: Pin any route, including advanced routes hidden from the default sidebar
- **Action Search**: Press `Ctrl+Shift+K` to filter the same search model to safe action entry points
- **Page Header**: Shows current area, route context, and common actions
- **Toast Notifications**: Transient success/error messages appear in the status bar
- **Status Bar Undo**: Click the undo button to revert the last privileged action (via `HistoryManager`)

### Tab Anatomy

Most tabs follow this layout:

1. **Header**: Tab title and description
2. **Action Buttons**: Primary actions (e.g., "Refresh", "Install", "Apply")
3. **Content Area**: Forms, tables, cards, or command output
4. **Output Section** (for command tabs): Shows command output with Copy/Save/Cancel toolbar

---

## Quick CLI Tour

### System & Health Commands

```bash
# Display system information
loofi info

# Run health check
loofi health

# Check for missing dependencies
loofi doctor

# View hardware details
loofi hardware

# Generate support bundle (for bug reports)
loofi support-bundle
```

### Maintenance Commands

```bash
# Clean package cache, journal logs, temp files
loofi cleanup all

# Clean journal logs from last 7 days
loofi cleanup journal --days 7

# Apply power profile tweak
loofi tweak power --profile balanced

# Auto-tune system
loofi tuner analyze
loofi tuner apply
```

### Package Management

```bash
# Search for a package
loofi package search --query firefox --source all

# Install a package
loofi package install firefox

# Remove a package
loofi package remove firefox
```

### Logs & Services

```bash
# View error logs from last 2 hours
loofi logs errors --since "2h ago"

# List all failed services
loofi service list --filter failed

# Restart a service
loofi service restart sshd
```

### Security & Network

```bash
# Run security audit
loofi security-audit

# Configure DNS provider
loofi network dns --provider cloudflare

# View firewall ports
loofi firewall ports
```

### JSON Output for Scripting

Add `--json` flag to any command for machine-readable output:

```bash
loofi --json info
loofi --json health
loofi --json package search --query vim
```

Example JSON output:

```json
{
  "version": "40.0.0",
  "codename": "Foundation",
  "python_version": "3.12.1",
  "os": "Fedora 44",
  "package_manager": "dnf"
}
```

### Dry-Run Mode

Test commands without executing them (added in v35.0.0):

```bash
loofi --dry-run cleanup all
```

Output shows what would be executed without making any changes.

---

## GUI Quick Start

### 1. Launch the Application

```bash
loofi-fedora-tweaks
```

### 2. Complete First-Run Wizard

Follow the 5-step wizard to configure your system profile.

### 3. Explore Key Tabs

**For general users:**
- **Home** — Dashboard with system overview and quick actions
- **Maintenance** — Check for updates, clean up disk space
- **Software** — Browse and install applications
- **Network** — Configure Wi-Fi, DNS, and VPN

**For advanced users:**
- **Performance** — Auto-tune system for better performance
- **Virtualization** — Manage VMs and VFIO GPU passthrough
- **AI Lab** — Run local LLMs with Ollama
- **Automation** — Schedule recurring tasks

**For troubleshooting:**
- **Health Timeline** — View system health scores over time
- **Logs** — Search and filter system logs
- **Diagnostics** — Run diagnostic tools and generate support bundles

### 4. Use Command Palette

Press `Ctrl+K` and start typing:
- "update" → Jump to Maintenance Updates
- "firewall" → Open Security Firewall settings
- "cleanup" → Run cleanup actions
- "about" → View app version and credits

---

## Next Steps

- **Explore Tabs**: [GUI Tabs Reference](GUI-Tabs-Reference) — Detailed guide for all 28 tabs
- **Master CLI**: [CLI Reference](CLI-Reference) — Complete command reference with examples
- **Customize**: [Configuration](Configuration) — Themes, quick actions, favorites
- **Troubleshooting**: [Troubleshooting](Troubleshooting) — Common issues and solutions
