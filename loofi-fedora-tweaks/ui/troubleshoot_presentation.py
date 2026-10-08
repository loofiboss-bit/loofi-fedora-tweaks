"""Closed presentation vocabulary for the Compass troubleshooting journey."""

SOURCE_LABELS = {
    "screen-sharing-state": "Session, PipeWire, WirePlumber and advertised ScreenCast support",
    "system-check": "System Check",
    "flatpak-update-health": "Flatpak inventory, local remotes and runtimes",
    "firmware-update-health": "Firmware tool, service and devices",
    "audio-state": "Audio services, default output and volume",
    "bluetooth-state": "Bluetooth service, adapter, radio and paired devices",
    "observability": "Saved resource trends",
    "change-journal": "Trusted Change Journal",
    "package-health": "Package health",
    "deployment-state": "Atomic deployment state",
    "pending-reboot": "Pending reboot",
    "action-center": "Action Center",
    "application-inventory": "Application inventory",
    "network-state": "NetworkManager state",
    "dns-state": "DNS resolver metadata",
    "storage-reclaim": "Storage and reclaim preview",
    "boot-analysis": "Boot analysis",
    "failed-services": "Failed services",
    "package-history": "Package history",
    "deployment-history": "Deployment history",
}

STATE_LABELS = {
    "completed": "Completed",
    "empty": "No issue found",
    "partial": "Partial",
    "stale": "Stale",
    "unavailable": "Unavailable",
    "timed_out": "Timed out",
    "failed": "Failed",
    "cancelled": "Cancelled",
}

SYMPTOMS = (
    ("no_internet", "No internet", "network_problem", ""),
    (
        "sound_not_working",
        "Sound is not working",
        "sound_not_working",
        "This check reads audio metadata. Confirm actual playback yourself.",
    ),
    (
        "bluetooth_not_working",
        "Bluetooth is not working",
        "bluetooth_not_working",
        "This check reads local Bluetooth metadata without scanning or pairing. Confirm device connectivity yourself.",
    ),
    ("screen_sharing_not_working", "Screen sharing is not working", "screen_sharing_not_working",
     "This check reads existing services and advertised portal support. It does not record the screen. Test sharing in your application yourself."),
    ("updates_failed", "Updates failed", "updates_failed", ""),
    ("app_wont_start", "An app will not start", "application_failed", ""),
    ("system_slow", "The system feels slow", "system_slow", ""),
    ("storage_full", "Storage is full", "storage_pressure", ""),
    (
        "something_else",
        "Something else",
        "system_slow",
        "This general check reviews system health. It may not cover a device-specific problem.",
    ),
)

SESSION_STATUS = {
    "completed": ("Completed", "success"),
    "partial": ("Partially completed", "warning"),
    "cancelled": ("Cancelled", "neutral"),
    "failed": ("Failed", "error"),
}

__all__ = ["SESSION_STATUS", "SOURCE_LABELS", "STATE_LABELS", "SYMPTOMS"]
