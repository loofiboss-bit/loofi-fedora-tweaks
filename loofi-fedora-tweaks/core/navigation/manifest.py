"""Central navigation route manifest.

This module is intentionally PyQt-free so command palette, quick actions,
favorites, CLI diagnostics, and release checks can validate navigation without
importing the UI layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable, Literal

RiskLevel = Literal["none", "low", "medium", "high"]
Visibility = Literal["beginner", "advanced", "all"]


@dataclass(frozen=True)
class NavigationRoute:
    """A stable route users and persisted UI state can reference."""

    id: str
    label: str
    plugin_id: str
    category: str
    icon: str
    description: str
    aliases: tuple[str, ...] = field(default_factory=tuple)
    keywords: tuple[str, ...] = field(default_factory=tuple)
    risk: RiskLevel = "none"
    visibility: Visibility = "all"
    subroute: str = ""


def _route(
    route_id: str,
    label: str,
    plugin_id: str,
    category: str,
    icon: str,
    description: str,
    *,
    aliases: Iterable[str] = (),
    keywords: Iterable[str] = (),
    risk: RiskLevel = "none",
    visibility: Visibility = "all",
    subroute: str = "",
) -> NavigationRoute:
    return NavigationRoute(
        id=route_id,
        label=label,
        plugin_id=plugin_id,
        category=category,
        icon=icon,
        description=description,
        aliases=tuple(aliases),
        keywords=tuple(keywords),
        risk=risk,
        visibility=visibility,
        subroute=subroute,
    )


_ROUTES: tuple[NavigationRoute, ...] = (
    _route(
        "atlas_dashboard",
        "Home",
        "atlas_dashboard",
        "System",
        "home",
        "Navigation hub with task cards and release readiness guidance.",
        aliases=("atlas", "atlas-home", "fedora-control-center"),
        keywords=("home", "beacon", "tasks", "readiness"),
        visibility="beginner",
    ),
    _route(
        "dashboard",
        "Live Overview",
        "dashboard",
        "System",
        "overview-dashboard",
        "System overview, health score, and dashboard quick actions.",
        aliases=("dashboard", "system-overview", "live overview"),
        keywords=("overview", "health", "quick actions"),
        visibility="beginner",
    ),
    _route("system_info", "System Info", "system_info", "System", "info", "Hardware, OS, kernel, and release details.", aliases=("System Info", "system-info", "os-details"), keywords=("fedora", "kernel", "hardware", "specs"), visibility="beginner"),
    _route("monitor", "System Monitor", "monitor", "System", "overview-dashboard", "Performance graphs and process management.", aliases=("System Monitor",), keywords=("cpu", "memory", "process", "traffic"), visibility="beginner"),
    _route("system-monitor:performance", "Performance", "monitor", "System", "cpu-performance", "CPU, memory, disk, and network activity.", aliases=("monitor:performance", "Performance", "CPU Usage", "Memory", "Disk I/O", "Network Traffic"), keywords=("cpu", "ram", "memory", "disk", "network"), subroute="performance"),
    _route("system-monitor:processes", "Processes", "monitor", "System", "terminal-console", "Running process list and process actions.", aliases=("monitor:processes", "Processes", "Kill Process"), keywords=("process", "pid", "top", "htop", "kill"), risk="medium", subroute="processes"),
    _route("community", "Community", "community", "System", "network-connectivity", "Community presets, marketplace entries, and featured plugins.", aliases=("Community",), keywords=("presets", "marketplace", "plugins")),
    _route("community:presets", "Presets", "community", "System", "settings", "Local and community configuration presets.", aliases=("Presets", "preset", "profile"), keywords=("preset", "configuration", "share"), subroute="presets"),
    _route("community:marketplace", "Marketplace", "community", "System", "install", "Discover and install shared presets and plugins.", aliases=("Marketplace",), keywords=("marketplace", "download", "share"), subroute="marketplace"),
    _route("community:plugins", "Plugins", "community", "System", "developer-tools", "Plugin discovery and management.", aliases=("Plugins",), keywords=("plugin", "extension"), subroute="plugins"),
    _route("community:featured", "Featured", "community", "System", "status-ok", "Featured community content.", aliases=("Featured",), keywords=("featured", "recommended"), subroute="featured"),
    _route("agents", "Agents", "agents", "Maintenance", "developer-tools", "Automation agents and activity.", aliases=("Agents",), keywords=("agent", "automation"), visibility="advanced"),
    _route("agents:dashboard", "Agents Dashboard", "agents", "Maintenance", "overview-dashboard", "Agent summary and status.", aliases=("Agent Dashboard",), keywords=("agent", "dashboard"), visibility="advanced", subroute="dashboard"),
    _route("agents:my-agents", "My Agents", "agents", "Maintenance", "developer-tools", "Configured local agents.", aliases=("My Agents",), keywords=("agent", "list"), visibility="advanced", subroute="my-agents"),
    _route("agents:create", "Create Agent", "agents", "Maintenance", "install", "Create a new local automation agent.", aliases=("Create Agent",), keywords=("agent", "create"), visibility="advanced", subroute="create"),
    _route("agents:activity", "Activity Log", "agents", "Maintenance", "logs", "Agent execution activity log.", aliases=("Activity Log",), keywords=("agent", "log", "activity"), visibility="advanced", subroute="activity"),
    _route("software", "Software", "software", "Packages", "packages-software", "Applications, repositories, Flatpak, and package sources.", aliases=("Software", "Packages"), keywords=("apps", "repos", "flatpak", "packages"), visibility="beginner"),
    _route("software:apps", "Applications", "software", "Packages", "install", "Install and review application packages.", aliases=("Apps", "Applications", "Install Apps", "Multimedia Codecs"), keywords=("apps", "install", "software", "codecs"), subroute="applications"),
    _route("software:repos", "Repositories", "software", "Packages", "packages-software", "RPM Fusion, Flathub, COPR, and package repositories.", aliases=("Repos", "Repositories", "RPM Fusion", "Flathub", "COPR Repos"), keywords=("repo", "repository", "rpmfusion", "copr", "flathub"), risk="medium", subroute="repositories"),
    _route("software:flatpak", "Flatpak Manager", "software", "Packages", "packages-software", "Flatpak application and remote management.", aliases=("Flatpak Manager", "Flatpak"), keywords=("flatpak", "flathub", "remote"), subroute="flatpak"),
    _route("maintenance", "Maintenance", "maintenance", "Packages", "maintenance-health", "System updates, cache cleanup, and overlays.", aliases=("Maintenance",), keywords=("update", "cleanup", "overlays"), visibility="beginner"),
    _route("maintenance:updates", "Updates", "maintenance", "Packages", "update", "System, Flatpak, and firmware update actions.", aliases=("Updates", "Update System", "Update Flatpaks", "Firmware Update", "update_all"), keywords=("dnf", "rpm-ostree", "flatpak", "firmware"), risk="medium", subroute="updates"),
    _route("maintenance:cleanup", "Cleanup", "maintenance", "Packages", "cleanup", "Cache, journal, trim, autoremove, and RPM database cleanup.", aliases=("Cleanup", "Clean DNF Cache", "Vacuum Journal", "Vacuum Journals", "SSD Trim", "Trim SSD", "Remove Unused Packages", "Rebuild RPM DB", "clean_cache"), keywords=("clean", "cache", "journal", "trim", "autoremove", "rpmdb"), risk="medium", subroute="cleanup"),
    _route("maintenance:smart-updates", "Smart Updates", "maintenance", "Packages", "update", "Guided update planning and safety checks.", aliases=("Smart Updates",), keywords=("smart", "updates", "plan"), risk="medium", subroute="smart-updates"),
    _route("maintenance:upgrade-assistant", "Upgrade Assistant", "maintenance", "Packages", "update", "Guided Fedora release planning, readiness checks, action review, and support export.", aliases=("Upgrade Assistant", "Release Upgrade", "Waypoint", "Harbor"), keywords=("upgrade", "release", "readiness", "fedora45", "waypoint", "harbor", "action-center"), risk="medium", subroute="upgrade-assistant"),
    _route("maintenance:action-center", "Action Center", "maintenance", "Packages", "maintenance-health", "Preview, queue, confirm, verify, and review recent maintenance actions.", aliases=("Action Center", "Action Inbox", "Harbor Actions"), keywords=("action", "preview", "queue", "rollback", "maintenance", "harbor"), risk="medium", subroute="upgrade-assistant"),
    _route("maintenance:overlays", "Overlays", "maintenance", "Packages", "packages-software", "Atomic Fedora overlay package management.", aliases=("Overlays",), keywords=("atomic", "rpm-ostree", "layered"), risk="high", visibility="advanced", subroute="overlays"),
    _route("snapshots", "Snapshots", "snapshots", "Packages", "logs", "Create, list, and restore system snapshots.", aliases=("Snapshots", "Create Snapshot"), keywords=("snapshot", "timeshift", "snapper", "btrfs"), risk="medium", visibility="advanced"),
    _route("hardware", "Hardware", "hardware", "Hardware", "hardware-performance", "Hardware tuning, power, battery, and sensors.", aliases=("Hardware", "HP Tweaks", "Power Profile", "Power Profile Manager", "Fan Control", "Battery Limit", "Audio Restart", "Fingerprint", "power_profile"), keywords=("hp", "battery", "fan", "power", "audio", "fingerprint"), visibility="beginner"),
    _route("performance", "Performance", "performance", "Hardware", "cpu-performance", "Performance tuning and workload history.", aliases=("Auto-Tune Performance", "CPU Governor", "Show CPU Governor"), keywords=("governor", "performance", "tuning", "cpu"), visibility="advanced"),
    _route("storage", "Storage", "storage", "Hardware", "storage-disk", "Disk, mount, SMART, and usage diagnostics.", aliases=("Storage", "Show Disk Usage"), keywords=("disk", "mount", "smart", "usage"), visibility="beginner"),
    _route("gaming", "Gaming", "gaming", "Hardware", "cpu-performance", "GameMode, MangoHud, Proton, Wine, and shader cache.", aliases=("Gaming", "GameMode", "MangoHud", "Proton", "Wine", "Shader Cache", "Steam", "gaming_mode"), keywords=("game", "steam", "proton", "mangohud"), visibility="beginner"),
    _route("network", "Network", "network", "Network", "network-connectivity", "Connections, DNS, privacy, and network monitoring.", aliases=("Network",), keywords=("dns", "privacy", "connections", "traffic"), visibility="beginner"),
    _route("network:connections", "Connections", "network", "Network", "network-connectivity", "Network interfaces, Wi-Fi, and VPN connections.", aliases=("Connections", "Network Connections"), keywords=("interface", "wifi", "vpn"), subroute="connections"),
    _route("network:dns", "DNS", "network", "Network", "network-connectivity", "DNS provider and resolver configuration.", aliases=("DNS", "DNS Provider", "Show DNS Config", "Flush DNS Cache"), keywords=("dns", "nameserver", "resolver"), risk="medium", subroute="dns"),
    _route("network:privacy", "Network Privacy", "network", "Network", "security-shield", "Network privacy and MAC randomization.", aliases=("Network Privacy", "MAC Randomization"), keywords=("mac", "randomization", "privacy"), risk="medium", subroute="privacy"),
    _route("network:monitoring", "Monitoring", "network", "Network", "network-traffic", "Network traffic and connection monitoring.", aliases=("Monitoring", "Network Monitor"), keywords=("traffic", "bandwidth", "connection"), subroute="monitoring"),
    _route("mesh", "Loofi Link", "mesh", "Network", "network-connectivity", "Device mesh, shared clipboard, and file drop.", aliases=("Loofi Link", "Mesh"), keywords=("mesh", "devices", "clipboard", "file drop"), visibility="advanced"),
    _route("loofi-link:devices", "Devices", "mesh", "Network", "network-connectivity", "Nearby mesh devices.", aliases=("mesh:devices", "Devices"), keywords=("mesh", "device"), visibility="advanced", subroute="devices"),
    _route("loofi-link:clipboard", "Clipboard", "mesh", "Network", "terminal-console", "Shared clipboard between trusted devices.", aliases=("mesh:clipboard", "Clipboard"), keywords=("clipboard", "copy", "paste"), visibility="advanced", subroute="clipboard"),
    _route("loofi-link:file-drop", "File Drop", "mesh", "Network", "install", "Local file drop between trusted devices.", aliases=("mesh:file-drop", "File Drop"), keywords=("file", "drop", "transfer"), visibility="advanced", subroute="file-drop"),
    _route("security", "Security & Privacy", "security", "Security", "security-shield", "Security posture, ports, firewall, USB, and sandboxing.", aliases=("Security", "Security & Privacy"), keywords=("security", "privacy", "firewall", "ports"), visibility="beginner"),
    _route("security:overview", "Security Overview", "security", "Security", "security-shield", "Security score and hardening overview.", aliases=("Security Score", "Run Security Scan"), keywords=("score", "audit", "hardening"), subroute="overview"),
    _route("security:firewall", "Firewall", "security", "Security", "security-shield", "Firewall zones and service exposure.", aliases=("Firewall", "Toggle Firewall"), keywords=("firewall", "firewalld", "zone"), risk="medium", subroute="firewall"),
    _route("security:privacy", "Privacy", "security", "Security", "security-shield", "Telemetry and privacy controls.", aliases=("Telemetry", "Security Privacy"), keywords=("telemetry", "tracking", "privacy"), risk="medium", subroute="privacy"),
    _route("security:ports", "Ports", "security", "Security", "search", "Open port auditing.", aliases=("Port Auditor", "Check Open Ports"), keywords=("port", "scan", "ss"), subroute="ports"),
    _route("backup", "Backup", "backup", "Security", "storage-disk", "Guided backup creation and restore workflows.", aliases=("Backup",), keywords=("backup", "restore", "snapshot"), risk="medium", visibility="beginner"),
    _route("desktop", "Desktop", "desktop", "Appearance", "appearance-theme", "Window management, theming, and display settings.", aliases=("Desktop", "Director", "Theming"), keywords=("window", "theme", "display"), visibility="beginner"),
    _route("desktop:director", "Window Manager", "desktop", "Appearance", "appearance-theme", "Window manager and tiling preset controls.", aliases=("Director", "Window Manager", "Tiling Presets"), keywords=("window", "kwin", "tiling"), subroute="window-manager"),
    _route("desktop:theming", "Theming", "desktop", "Appearance", "appearance-theme", "GTK, Qt, icons, and font theme controls.", aliases=("Theming", "Icons", "Fonts"), keywords=("theme", "icons", "fonts", "gtk", "qt"), subroute="theming"),
    _route("desktop:display", "Display", "desktop", "Appearance", "overview-dashboard", "Display and monitor preferences.", aliases=("Display",), keywords=("display", "monitor", "screen"), subroute="display"),
    _route("profiles", "Profiles", "profiles", "Appearance", "settings", "System tuning profiles and active profile state.", aliases=("Profiles",), keywords=("profile", "preset"), risk="medium"),
    _route("extensions", "Extensions", "extensions", "Appearance", "developer-tools", "Desktop extensions and compatibility state.", aliases=("Extensions",), keywords=("extension", "plugin")),
    _route("settings", "Settings", "settings", "Appearance", "settings", "Application appearance, behavior, and advanced settings.", aliases=("Settings",), keywords=("settings", "preferences"), visibility="beginner"),
    _route("settings:appearance", "Appearance", "settings", "Appearance", "appearance-theme", "Application appearance preferences.", aliases=("Settings Appearance",), keywords=("appearance", "theme"), subroute="appearance"),
    _route("settings:behavior", "Behavior", "settings", "Appearance", "settings", "Application behavior preferences.", aliases=("Behavior",), keywords=("behavior", "preferences"), subroute="behavior"),
    _route("settings:advanced", "Advanced", "settings", "Appearance", "settings", "Advanced application preferences.", aliases=("Advanced",), keywords=("advanced", "developer"), visibility="advanced", subroute="advanced"),
    _route("development", "Development Tools", "development", "Tools", "developer-tools", "Containers and developer tool setup.", aliases=("Development", "Developer Tools", "Developer"), keywords=("developer", "containers", "podman", "code"), visibility="beginner"),
    _route("development:containers", "Containers", "development", "Tools", "developer-tools", "Container and Distrobox tooling.", aliases=("Containers", "Distrobox", "Podman"), keywords=("podman", "docker", "distrobox", "container"), subroute="containers"),
    _route("development:developer", "Developer Tools", "development", "Tools", "terminal-console", "Editors, compilers, Git, and SDK packages.", aliases=("Developer", "VS Code"), keywords=("git", "gcc", "make", "vscode", "sdk"), subroute="developer-tools"),
    _route("ai_lab", "AI Lab", "ai_lab", "Tools", "cpu-performance", "Local AI models, voice, and knowledge tools.", aliases=("AI Lab", "Ollama", "AI Models", "Chat"), keywords=("ai", "llm", "ollama", "models"), visibility="advanced"),
    _route("ai-lab:models", "Models", "ai_lab", "Tools", "cpu-performance", "Local AI model inventory and recommendations.", aliases=("ai_lab:models", "Models", "Ollama", "AI Models"), keywords=("models", "llm", "ollama"), visibility="advanced", subroute="models"),
    _route("ai-lab:voice", "Voice", "ai_lab", "Tools", "terminal-console", "Voice and transcription tools.", aliases=("ai_lab:voice", "Voice"), keywords=("voice", "transcribe", "audio"), visibility="advanced", subroute="voice"),
    _route("ai-lab:knowledge", "Knowledge", "ai_lab", "Tools", "logs", "Local knowledge and context tooling.", aliases=("ai_lab:knowledge", "Knowledge"), keywords=("knowledge", "rag", "documents"), visibility="advanced", subroute="knowledge"),
    _route("automation", "Automation", "automation", "Maintenance", "settings", "Scheduler and replicator automation workflows.", aliases=("Automation", "Scheduler", "Replicator"), keywords=("schedule", "replicate", "automation"), visibility="advanced"),
    _route("automation:scheduler", "Scheduler", "automation", "Maintenance", "settings", "Scheduled tasks and systemd timer automation.", aliases=("Scheduler", "Cron Jobs"), keywords=("schedule", "cron", "timer"), visibility="advanced", subroute="scheduler"),
    _route("automation:replicator", "Replicator", "automation", "Maintenance", "restart", "Export and import system state as repeatable automation.", aliases=("Replicator", "Ansible Export"), keywords=("ansible", "export", "import", "iac"), visibility="advanced", subroute="replicator"),
    _route("health", "Health", "health", "Maintenance", "maintenance-health", "Health timeline and system signals.", aliases=("Health",), keywords=("health", "timeline", "history"), visibility="beginner"),
    _route("logs", "Logs", "logs", "Maintenance", "logs", "System logs and error pattern review.", aliases=("Logs",), keywords=("journal", "logs", "errors"), visibility="advanced"),
    _route("diagnostics", "Diagnostics", "diagnostics", "Maintenance", "maintenance-health", "Watchtower diagnostics and boot analysis.", aliases=("Diagnostics", "Watchtower", "Boot"), keywords=("diagnostics", "boot", "watchtower"), visibility="beginner"),
    _route("diagnostics:watchtower", "Watchtower", "diagnostics", "Maintenance", "maintenance-health", "System diagnostic checks and recommendations.", aliases=("Watchtower",), keywords=("diagnostic", "doctor", "health"), subroute="watchtower"),
    _route("diagnostics:boot", "Boot", "diagnostics", "Maintenance", "restart", "Boot time analysis and kernel parameter review.", aliases=("Boot", "Boot Analysis", "Kernel Params"), keywords=("boot", "startup", "kernel", "grub"), visibility="advanced", subroute="boot"),
    _route("teleport", "State Teleport", "teleport", "Maintenance", "network-traffic", "Capture, list, and restore workspace state.", aliases=("State Teleport", "Teleport"), keywords=("state", "teleport", "capture", "restore"), risk="medium", visibility="advanced"),
    _route("virtualization", "Virtualization", "virtualization", "Packages", "terminal-console", "Virtual machines, GPU passthrough, and disposable environments.", aliases=("Virtualization", "VMs"), keywords=("vm", "virt", "gpu", "passthrough"), risk="medium", visibility="advanced"),
    _route("virtualization:vms", "VMs", "virtualization", "Packages", "terminal-console", "Virtual machine list and actions.", aliases=("VMs", "Virtual Machines"), keywords=("vm", "virsh", "libvirt"), risk="medium", visibility="advanced", subroute="vms"),
    _route("virtualization:gpu-passthrough", "GPU Passthrough", "virtualization", "Packages", "hardware-performance", "VFIO GPU passthrough planning.", aliases=("GPU Passthrough", "VFIO"), keywords=("gpu", "vfio", "passthrough"), risk="high", visibility="advanced", subroute="gpu-passthrough"),
    _route("virtualization:disposable", "Disposable", "virtualization", "Packages", "cleanup", "Disposable virtualization workflows.", aliases=("Disposable",), keywords=("temporary", "sandbox", "vm"), risk="medium", visibility="advanced", subroute="disposable"),
)

_ROUTE_BY_ID: dict[str, NavigationRoute] = {route.id: route for route in _ROUTES}


def _normalize_key(value: str) -> str:
    value = str(value or "").strip().lower()
    value = value.replace("_", "-")
    value = value.replace(" ", "-")
    while "--" in value:
        value = value.replace("--", "-")
    return value.strip("-")


def _alias_pairs() -> Iterable[tuple[str, NavigationRoute]]:
    for route in _ROUTES:
        yield route.id, route
        yield _normalize_key(route.id), route
        yield route.label, route
        yield _normalize_key(route.label), route
        for alias in route.aliases:
            yield alias, route
            yield _normalize_key(alias), route


_ROUTE_BY_ALIAS: dict[str, NavigationRoute] = {}
for alias, route in _alias_pairs():
    key = str(alias)
    _ROUTE_BY_ALIAS.setdefault(key, route)
    _ROUTE_BY_ALIAS.setdefault(_normalize_key(key), route)


def all_routes() -> tuple[NavigationRoute, ...]:
    """Return every canonical route."""
    return _ROUTES


def get_route(route_id: str) -> NavigationRoute | None:
    """Return an exact canonical route by ID."""
    return _ROUTE_BY_ID.get(route_id)


def resolve(route_id_or_alias: str) -> NavigationRoute | None:
    """Resolve a canonical route ID or legacy alias to a route."""
    if not route_id_or_alias:
        return None
    key = str(route_id_or_alias).strip()
    return _ROUTE_BY_ID.get(key) or _ROUTE_BY_ALIAS.get(key) or _ROUTE_BY_ALIAS.get(_normalize_key(key))


def routes_for_palette() -> tuple[NavigationRoute, ...]:
    """Routes searchable from the command palette."""
    return _ROUTES


def routes_for_quick_actions() -> tuple[NavigationRoute, ...]:
    """Routes available to quick-action navigation."""
    return _ROUTES


def validate_routes(
    plugin_ids: Iterable[str],
    icon_resolver: Callable[[str], str | None] | None = None,
) -> list[str]:
    """Return validation errors for manifest/plugin/icon drift."""
    errors: list[str] = []
    ids = [route.id for route in _ROUTES]
    duplicate_ids = sorted({route_id for route_id in ids if ids.count(route_id) > 1})
    for route_id in duplicate_ids:
        errors.append(f"duplicate route id: {route_id}")

    plugin_id_set = set(plugin_ids)
    for route in _ROUTES:
        if route.plugin_id not in plugin_id_set:
            errors.append(f"route {route.id} references unknown plugin {route.plugin_id}")
        if ":" in route.id and not route.subroute:
            errors.append(f"route {route.id} is missing subroute")
        if route.risk not in ("none", "low", "medium", "high"):
            errors.append(f"route {route.id} has invalid risk {route.risk}")
        if route.visibility not in ("beginner", "advanced", "all"):
            errors.append(f"route {route.id} has invalid visibility {route.visibility}")
        if icon_resolver is not None and not icon_resolver(route.icon):
            errors.append(f"route {route.id} icon does not resolve: {route.icon}")

    return errors
