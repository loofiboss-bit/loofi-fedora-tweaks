from .health_model import HealthCheck, HealthResult
from .health_registry import HealthRegistry

class GamingAuditor:
    """
    Gaming Mode Audit foundation for v4.0 "Atlas".
    Provides safe checks for gaming-related system state.
    """
    def __init__(self, health_registry: HealthRegistry):
        self.registry = health_registry
        self._initialize_gaming_checks()

    def _initialize_gaming_checks(self):
        """Register gaming-focused health checks."""
        
        # 1. GameMode Status
        self.registry.register(HealthCheck(
            id="gaming-gamemode",
            title="Feral GameMode",
            severity="info",
            category="hardware",
            description="Checks if GameMode is installed and functional for performance optimization.",
            suggested_fix="Install 'gamemode' package via DNF.",
            manual_commands=["dnf install gamemode", "gamemoded -s"]
        ))

        # 2. MangoHud Availability
        self.registry.register(HealthCheck(
            id="gaming-mangohud",
            title="MangoHud Overlay",
            severity="info",
            category="hardware",
            description="Checks if MangoHud is available for performance monitoring in-game.",
            suggested_fix="Install 'mangohud' package via DNF.",
            manual_commands=["dnf install mangohud"]
        ))

        # 3. NVIDIA Driver/Wayland Compatibility
        self.registry.register(HealthCheck(
            id="gaming-nvidia-wayland",
            title="NVIDIA + Wayland Hints",
            severity="warning",
            category="hardware",
            description="Checks for potential VRR/G-Sync issues on NVIDIA + Wayland configurations.",
            suggested_fix="Ensure 'nvidia-drm.modeset=1' is set and consider KDE Plasma 6.1+ for Explicit Sync.",
            docs_link="https://kde.org/announcements/plasma/6/6.1.0/"
        ))

        # 4. CPU Governor Performance
        self.registry.register(HealthCheck(
            id="gaming-cpu-governor",
            title="CPU Governor for Gaming",
            severity="info",
            category="hardware",
            description="Checks if the CPU governor is set to 'performance' for minimal latency.",
            suggested_fix="Set CPU governor to performance when gaming.",
            manual_commands=["powerprofilesctl set performance"]
        ))

        # 5. Steam Device Rules
        self.registry.register(HealthCheck(
            id="gaming-steam-udev",
            title="Steam Controller / VR udev Rules",
            severity="warning",
            category="hardware",
            description="Checks if necessary udev rules for Steam controllers and VR headsets are present.",
            suggested_fix="Install 'steam-devices' package.",
            manual_commands=["dnf install steam-devices"]
        ))

    def run_gaming_audit(self) -> list[HealthResult]:
        """Runs the gaming audit suite."""
        gaming_checks = [
            "gaming-gamemode",
            "gaming-mangohud",
            "gaming-nvidia-wayland",
            "gaming-cpu-governor",
            "gaming-steam-udev"
        ]
        results = []
        for cid in gaming_checks:
            results.append(self.registry.run_check(cid))
        return results
