import json
import time
from typing import Any, Dict
from .report_exporter import ReportExporter
from ..diagnostics.health_registry import HealthRegistry
from ..executor.action_executor import ActionExecutor


class SupportBundleV2:
    """
    v4.0 "Atlas" Support Bundle.
    Aggregates system info, health results, and action logs into a
    structured diagnostic bundle.
    """

    def __init__(self, health_registry: HealthRegistry):
        self.registry = health_registry
        self.exporter = ReportExporter()
        self.executor = ActionExecutor()

    def generate_bundle(self) -> Dict[str, Any]:
        """
        Gathers all diagnostic data into a single dictionary.
        Safe for export: filters out secrets/personal files.
        """
        # 1. Base system info
        system_info = self.exporter.gather_system_info()

        # 2. Run all registered health checks
        health_results = []
        for check in self.registry.list_checks():
            result = self.registry.run_check(check.id)
            health_results.append({
                "id": check.id,
                "title": check.title,
                "severity": check.severity,
                "status": result.status,
                "message": result.message
            })

        # 3. Get recent action logs (command history)
        action_history = self.executor.get_action_log(limit=50)

        # 4. Aggregate
        bundle = {
            "v": "4.0.0-atlas",
            "timestamp": time.time(),
            "system": system_info,
            "health": health_results,
            "actions": action_history,
            "network_summary": self.exporter.gather_network_info(),
            "selinux": self.exporter.gather_selinux_info()
        }

        return bundle

    def save_json(self, path: str) -> str:
        """Saves the bundle as a pretty-printed JSON file."""
        bundle = self.generate_bundle()
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(bundle, f, indent=4)
        return path
