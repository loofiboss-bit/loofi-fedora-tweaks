"""Tests for utils/presets.py — PresetManager."""
import sys
import os
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'loofi-fedora-tweaks'))

from utils.presets import PresetManager


class TestPresetManagerInit(unittest.TestCase):
    """Tests for PresetManager initialization."""

    @patch('utils.presets.os.makedirs')
    def test_creates_presets_directory(self, mock_makedirs):
        pm = PresetManager()
        mock_makedirs.assert_called_once_with(pm.PRESETS_DIR, exist_ok=True)


class TestSanitizeName(unittest.TestCase):
    """Tests for _sanitize_name path traversal prevention."""

    def test_normal_name(self):
        self.assertEqual(PresetManager._sanitize_name("my_preset"), "my_preset")

    def test_path_traversal(self):
        result = PresetManager._sanitize_name("../../etc/passwd")
        self.assertNotIn("..", result)
        self.assertNotIn("/", result)

    def test_empty_name(self):
        self.assertEqual(PresetManager._sanitize_name(""), "unnamed_preset")

    def test_dots_only(self):
        result = PresetManager._sanitize_name("..")
        self.assertEqual(result, "unnamed_preset")

    def test_slashes_stripped(self):
        result = PresetManager._sanitize_name("a/b\\c")
        self.assertNotIn("/", result)
        self.assertNotIn("\\", result)


class TestListPresets(unittest.TestCase):
    """Tests for list_presets."""

    @patch('utils.presets.os.makedirs')
    def setUp(self, mock_makedirs):
        self.pm = PresetManager()

    @patch('utils.presets.os.listdir')
    @patch('utils.presets.os.path.exists', return_value=True)
    def test_returns_preset_names(self, mock_exists, mock_listdir):
        mock_listdir.return_value = ["dark.json", "light.json", "readme.txt"]
        result = self.pm.list_presets()
        self.assertEqual(result, ["dark", "light"])

    @patch('utils.presets.os.path.exists', return_value=False)
    def test_returns_empty_when_dir_missing(self, mock_exists):
        result = self.pm.list_presets()
        self.assertEqual(result, [])

    @patch('utils.presets.os.listdir')
    @patch('utils.presets.os.path.exists', return_value=True)
    def test_no_json_files(self, mock_exists, mock_listdir):
        mock_listdir.return_value = ["readme.txt"]
        result = self.pm.list_presets()
        self.assertEqual(result, [])


class TestSavePreset(unittest.TestCase):
    """Tests for save_preset."""

    @patch('utils.presets.os.makedirs')
    def setUp(self, mock_makedirs):
        self.pm = PresetManager()

    @patch('utils.presets.atomic_write_json')
    @patch.object(PresetManager, '_get_power_profile', return_value='balanced')
    @patch.object(PresetManager, '_get_battery_limit', return_value=100)
    @patch.object(PresetManager, '_get_gsettings', return_value='Adwaita')
    def test_save_writes_json(self, mock_gs, mock_bat, mock_power, writer):
        result = self.pm.save_preset("test_preset")
        self.assertTrue(result)
        writer.assert_called_once()
        self.assertEqual(writer.call_args.kwargs["mode"], 0o600)


class TestLoadPreset(unittest.TestCase):
    """Tests for load_preset."""

    @patch('utils.presets.os.makedirs')
    def setUp(self, mock_makedirs):
        self.pm = PresetManager()

    @patch('utils.presets.os.path.exists', return_value=False)
    def test_returns_false_when_missing(self, mock_exists):
        result = self.pm.load_preset("nonexistent")
        self.assertFalse(result)

    @patch('builtins.open', new_callable=mock_open, read_data='{"name":"t","theme":"Adwaita"}')
    @patch('utils.presets.os.path.exists', return_value=True)
    def test_loads_data_without_applying(self, mock_exists, mock_file):
        result = self.pm.load_preset("test")
        self.assertIsInstance(result, dict)
        self.assertEqual(result["theme"], "Adwaita")


class TestDeletePreset(unittest.TestCase):
    """Tests for delete_preset."""

    @patch('utils.presets.os.makedirs')
    def setUp(self, mock_makedirs):
        self.pm = PresetManager()

    @patch('utils.presets.durable_unlink')
    @patch('utils.presets.os.path.exists', return_value=True)
    def test_deletes_existing(self, mock_exists, unlink):
        result = self.pm.delete_preset("old_preset")
        self.assertTrue(result)
        unlink.assert_called_once()

    @patch('utils.presets.os.path.exists', return_value=False)
    def test_returns_false_when_missing(self, mock_exists):
        result = self.pm.delete_preset("nonexistent")
        self.assertFalse(result)


class TestSavePresetData(unittest.TestCase):
    """Tests for validated local profile data."""

    @patch('utils.presets.os.makedirs')
    def setUp(self, mock_makedirs):
        self.pm = PresetManager()

    @patch('utils.presets.atomic_write_json')
    def test_save_local_import_data(self, writer):
        data = {"theme": "Nordic", "icon_theme": "Papirus"}
        result = self.pm.save_preset_data("community", data)
        self.assertTrue(result)

    @patch('utils.presets.atomic_write_json', side_effect=OSError("disk full"))
    def test_save_failure(self, writer):
        result = self.pm.save_preset_data("fail", {"theme": "X"})
        self.assertFalse(result)


class TestLocalProfileImport(unittest.TestCase):
    def test_import_validates_schema_path_and_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.json"
            source.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "name": "travel-profile",
                        "theme": "Breeze",
                        "battery_limit": 80,
                    }
                ),
                encoding="utf-8",
            )
            manager = PresetManager()
            manager.PRESETS_DIR = str(root / "profiles")

            success, name = manager.import_preset(source)

            self.assertTrue(success)
            self.assertEqual(name, "travel-profile")
            imported = root / "profiles" / "travel-profile.json"
            self.assertEqual(imported.stat().st_mode & 0o777, 0o600)

    def test_import_rejects_unknown_schema_and_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "invalid.json"
            source.write_text('{"schema_version": 2, "name": "invalid"}', encoding="utf-8")
            manager = PresetManager()
            manager.PRESETS_DIR = str(root / "profiles")
            self.assertFalse(manager.import_preset(source)[0])
            link = root / "link.json"
            link.symlink_to(source)
            self.assertFalse(manager.import_preset(link)[0])

    @patch("core.actions.orchestrator.ActionCenterOrchestrator")
    def test_valid_profile_becomes_manual_action_center_plan(self, orchestrator):
        manager = PresetManager()
        plan = MagicMock(plan_id="plan-1")
        orchestrator.return_value.plan.return_value = plan
        with patch.object(
            manager,
            "load_preset",
            return_value={"schema_version": 1, "name": "travel", "theme": "Breeze"},
        ):
            self.assertIs(manager.create_review_plan("travel"), plan)
        self.assertEqual(orchestrator.return_value.plan.call_args.args[0], "local-profile-review")


class TestGetGsettings(unittest.TestCase):
    """Tests for _get_gsettings helper."""

    @patch('utils.presets.os.makedirs')
    def setUp(self, mock_makedirs):
        self.pm = PresetManager()

    @patch('utils.presets.subprocess.check_output', return_value="'Adwaita'\n")
    @patch('utils.presets.cached_which', return_value="/usr/bin/gsettings")
    def test_returns_value(self, mock_which, mock_check):
        result = self.pm._get_gsettings("org.gnome.desktop.interface", "gtk-theme")
        self.assertEqual(result, "Adwaita")

    @patch('utils.presets.cached_which', return_value=None)
    def test_returns_none_when_missing(self, mock_which):
        result = self.pm._get_gsettings("org.gnome.desktop.interface", "gtk-theme")
        self.assertIsNone(result)

    @patch('utils.presets.subprocess.check_output', side_effect=subprocess.CalledProcessError(1, "gsettings"))
    @patch('utils.presets.cached_which', return_value="/usr/bin/gsettings")
    def test_returns_none_on_error(self, mock_which, mock_check):
        result = self.pm._get_gsettings("org.gnome.desktop.interface", "bad-key")
        self.assertIsNone(result)


class TestGetPowerProfile(unittest.TestCase):
    """Tests for _get_power_profile helper."""

    @patch('utils.presets.os.makedirs')
    def setUp(self, mock_makedirs):
        self.pm = PresetManager()

    @patch('utils.presets.subprocess.check_output', return_value="performance\n")
    @patch('utils.presets.cached_which', return_value="/usr/bin/powerprofilesctl")
    def test_returns_profile(self, mock_which, mock_check):
        result = self.pm._get_power_profile()
        self.assertEqual(result, "performance")

    @patch('utils.presets.cached_which', return_value=None)
    def test_returns_balanced_when_missing(self, mock_which):
        result = self.pm._get_power_profile()
        self.assertEqual(result, "balanced")


class TestGetBatteryLimit(unittest.TestCase):
    """Tests for _get_battery_limit helper."""

    @patch('utils.presets.os.makedirs')
    def setUp(self, mock_makedirs):
        self.pm = PresetManager()

    @patch('builtins.open', new_callable=mock_open, read_data="80")
    def test_reads_limit(self, mock_file):
        result = self.pm._get_battery_limit()
        self.assertEqual(result, 80)

    @patch('builtins.open', side_effect=FileNotFoundError)
    def test_returns_100_when_missing(self, mock_file):
        result = self.pm._get_battery_limit()
        self.assertEqual(result, 100)


if __name__ == "__main__":
    unittest.main()
