"""Data-only plugin specifications for deferred built-in loading."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Literal, Mapping

from core.plugins.metadata import PluginMetadata

PluginVisibility = Literal["standard", "advanced"]


@dataclass(frozen=True)
class PluginSpec:
    """Static metadata needed to render navigation before importing plugin UI."""

    id: str
    name: str
    description: str
    icon: str
    destination_id: str
    module: str
    class_name: str
    component: str = "core"
    visibility: PluginVisibility = "standard"
    compat: Mapping[str, Any] = field(default_factory=dict)
    category: str = "System"
    badge: str = ""
    order: int = 100

    def __post_init__(self) -> None:
        required = {
            "id": self.id,
            "name": self.name,
            "destination_id": self.destination_id,
            "module": self.module,
            "class_name": self.class_name,
            "component": self.component,
        }
        missing = [name for name, value in required.items() if not str(value).strip()]
        if missing:
            raise ValueError("PluginSpec fields must not be empty: %s" % ", ".join(missing))
        if self.visibility not in {"standard", "advanced"}:
            raise ValueError("Invalid plugin visibility: %s" % self.visibility)
        object.__setattr__(self, "compat", MappingProxyType(dict(self.compat)))

    def metadata(self) -> PluginMetadata:
        """Return legacy metadata without importing the implementation module."""
        return PluginMetadata(
            id=self.id,
            name=self.name,
            description=self.description,
            category=self.category,
            icon=self.icon,
            badge=self.badge,
            compat=dict(self.compat),
            order=self.order,
        )


def _spec(
    plugin_id: str,
    name: str,
    description: str,
    category: str,
    icon: str,
    badge: str,
    order: int,
    module: str,
    class_name: str,
    destination_id: str,
    *,
    component: str = "core",
    visibility: PluginVisibility = "standard",
) -> PluginSpec:
    return PluginSpec(
        id=plugin_id,
        name=name,
        description=description,
        icon=icon,
        destination_id=destination_id,
        module=module,
        class_name=class_name,
        component=component,
        visibility=visibility,
        category=category,
        badge=badge,
        order=order,
    )


BUILTIN_PLUGIN_SPECS: tuple[PluginSpec, ...] = (
    _spec("atlas_dashboard", "Home", "System status, the next useful action, and common Fedora tasks.", "System", "home", "recommended", 0, "ui.atlas_dashboard_tab", "AtlasDashboardTab", "home"),
    _spec("agents", "Agents", "Manage autonomous system agents for automated monitoring and maintenance.", "Maintenance", "🤖", "", 40, "ui.agents_tab", "AgentsTab", "advanced", component="specialist", visibility="advanced"),
    _spec("automation", "Automation", "Schedule tasks and replicate system configurations automatically.", "Maintenance", "⏰", "", 50, "ui.automation_tab", "AutomationTab", "advanced", component="specialist", visibility="advanced"),
    _spec("system_info", "System Info", "Detailed system information including hardware specs, kernel, and uptime.", "System", "ℹ️", "recommended", 20, "ui.system_info_tab", "SystemInfoTab", "system"),
    _spec("monitor", "System Monitor", "Live CPU, memory, and process monitoring with performance graphs.", "System", "📊", "recommended", 30, "ui.monitor_tab", "MonitorTab", "system"),
    _spec("health", "Health", "System health metrics timeline for tracking CPU, RAM, disk, and thermal trends.", "Maintenance", "📈", "", 10, "ui.health_timeline_tab", "HealthTimelineTab", "system"),
    _spec("logs", "Logs", "Smart log viewer with pattern detection, error summary, and log export.", "Maintenance", "📋", "advanced", 20, "ui.logs_tab", "LogsTab", "advanced", component="specialist", visibility="advanced"),
    _spec("hardware", "Hardware", "Hardware info and settings including CPU governor, GPU mode, fan control, and battery.", "Hardware", "⚡", "recommended", 10, "ui.hardware_tab", "HardwareTab", "system"),
    _spec("performance", "Performance", "Auto-tuner engine for workload detection, kernel tunables, and performance recommendations.", "Hardware", "🚀", "advanced", 20, "ui.performance_tab", "PerformanceTab", "advanced", component="specialist", visibility="advanced"),
    _spec("storage", "Storage", "Disk information, SMART health monitoring, and filesystem management.", "Hardware", "💾", "", 40, "ui.storage_tab", "StorageTab", "system"),
    _spec("software", "Software", "Application installer and repository management for Fedora packages.", "Packages", "📦", "recommended", 10, "ui.software_tab", "SoftwareTab", "software_updates"),
    _spec("maintenance", "Maintenance", "System updates, cache cleanup, and overlay management for Fedora.", "Packages", "🔧", "recommended", 20, "ui.maintenance_tab", "MaintenanceTab", "software_updates"),
    _spec("snapshots", "Snapshots", "Unified snapshot management across Timeshift, Snapper, and Btrfs backends.", "Packages", "📸", "advanced", 30, "ui.snapshot_tab", "SnapshotTab", "system"),
    _spec("virtualization", "Virtualization", "VM lifecycle management, GPU passthrough setup, and disposable virtual machines.", "Tools", "🖥️", "advanced", 20, "ui.virtualization_tab", "VirtualizationTab", "advanced", component="specialist", visibility="advanced"),
    _spec("development", "Development", "Container management and developer tools including language version managers and VS Code extensions.", "Tools", "🛠️", "", 10, "ui.development_tab", "DevelopmentTab", "advanced", component="specialist", visibility="advanced"),
    _spec("network", "Network", "Comprehensive network management including connections, DNS, privacy, and monitoring.", "Network", "🌐", "recommended", 10, "ui.network_tab", "NetworkTab", "network_security"),
    _spec("mesh", "Loofi Link", "Mesh network device discovery, clipboard sync, and file transfer between peers.", "Network", "🔗", "advanced", 20, "ui.mesh_tab", "MeshTab", "advanced", component="specialist", visibility="advanced"),
    _spec("security", "Security & Privacy", "Security hardening including firewall, USB guard, port auditing, and telemetry removal.", "Security", "🛡️", "recommended", 10, "ui.security_tab", "SecurityTab", "network_security"),
    _spec("desktop", "Desktop", "Window manager configuration, tiling setup, theming, and dotfile synchronization.", "Appearance", "🎨", "", 10, "ui.desktop_tab", "DesktopTab", "desktop"),
    _spec("profiles", "Profiles", "System profile quick-switch for applying and managing configuration profiles.", "Appearance", "👤", "", 30, "ui.profiles_tab", "ProfilesTab", "advanced", visibility="advanced"),
    _spec("gaming", "Gaming", "Gaming optimization tools including driver setup and performance tweaks.", "Hardware", "🎮", "", 40, "ui.gaming_tab", "GamingTab", "advanced", component="specialist", visibility="advanced"),
    _spec("ai_lab", "AI Lab", "AI model management, voice transcription, and knowledge base indexing.", "Tools", "🧠", "advanced", 30, "ui.ai_enhanced_tab", "AIEnhancedTab", "advanced", component="specialist", visibility="advanced"),
    _spec("teleport", "State Teleport", "Capture and restore workspace state including git repos and environment snapshots.", "Maintenance", "📡", "advanced", 60, "ui.teleport_tab", "TeleportTab", "advanced", component="specialist", visibility="advanced"),
    _spec("diagnostics", "Diagnostics", "System diagnostics including service health, boot analysis, and journal review.", "Maintenance", "🔭", "", 30, "ui.diagnostics_tab", "DiagnosticsTab", "system"),
    _spec("community", "Community", "Browse and apply community presets and configurations from the marketplace.", "System", "🌍", "", 40, "ui.community_tab", "CommunityTab", "advanced", component="specialist", visibility="advanced"),
    _spec("extensions", "Extensions", "Manage GNOME Shell and KDE Plasma desktop extensions.", "Appearance", "🧩", "new", 20, "ui.extensions_tab", "ExtensionsTab", "advanced", visibility="advanced"),
    _spec("backup", "Backup", "Create, manage, and restore system snapshots via Timeshift or Snapper.", "Security", "💾", "new", 20, "ui.backup_tab", "BackupTab", "network_security"),
    _spec("settings", "Settings", "Configure appearance, behavior, and advanced application options.", "Appearance", "⚙️", "", 100, "ui.settings_tab", "SettingsTab", "settings"),
)

BUILTIN_SPEC_BY_ID = {spec.id: spec for spec in BUILTIN_PLUGIN_SPECS}
