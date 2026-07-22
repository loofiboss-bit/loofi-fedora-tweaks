"""Import smoke tests for built-in Haven surfaces."""

import importlib
import unittest


TAB_MODULES = {
    "ui.atlas_dashboard_tab": "AtlasDashboardTab",
    "ui.system_info_tab": "SystemInfoTab",
    "ui.monitor_tab": "MonitorTab",
    "ui.maintenance_tab": "MaintenanceTab",
    "ui.hardware_tab": "HardwareTab",
    "ui.software_tab": "SoftwareTab",
    "ui.security_tab": "SecurityTab",
    "ui.network_tab": "NetworkTab",
    "ui.gaming_tab": "GamingTab",
    "ui.desktop_tab": "DesktopTab",
    "ui.development_tab": "DevelopmentTab",
    "ui.automation_tab": "AutomationTab",
    "ui.community_tab": "CommunityTab",
    "ui.diagnostics_tab": "DiagnosticsTab",
    "ui.virtualization_tab": "VirtualizationTab",
}


class TestBuiltInUiImports(unittest.TestCase):
    def test_all_builtin_tab_modules_import(self):
        for module_name, class_name in TAB_MODULES.items():
            with self.subTest(module=module_name):
                module = importlib.import_module(module_name)
                self.assertTrue(hasattr(module, class_name))

    def test_plugin_runtime_exports_only_builtin_architecture(self):
        module = importlib.import_module("core.plugins")

        self.assertTrue(hasattr(module, "PluginLoader"))
        self.assertTrue(hasattr(module, "PluginSpec"))
        self.assertFalse(hasattr(module, "PluginAdapter"))
        self.assertFalse(hasattr(module, "PluginSandbox"))


if __name__ == "__main__":
    unittest.main()
