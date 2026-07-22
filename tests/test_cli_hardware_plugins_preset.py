"""Additional CLI handler coverage for hardware/plugins/preset commands."""

import argparse
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'loofi-fedora-tweaks'))

from cli.main import cmd_hardware, cmd_plugins, cmd_preset


class TestHardwareCommand(unittest.TestCase):
    """Tests for cmd_hardware."""

    @patch('cli.main._print')
    @patch('services.hardware.hardware_profiles.detect_hardware_profile')
    def test_cmd_hardware_text_output(self, mock_detect, mock_print):
        mock_detect.return_value = (
            'hp',
            {
                'label': 'HP EliteBook',
                'battery_limit': True,
                'nbfc': False,
                'fingerprint': True,
                'power_profiles': True,
                'thermal_management': 'intel_pstate',
            },
        )

        with patch('cli.main._json_output', False):
            rc = cmd_hardware(argparse.Namespace())

        self.assertEqual(rc, 0)
        self.assertTrue(mock_print.called)

    @patch('cli.main._output_json')
    @patch('services.hardware.hardware_profiles.detect_hardware_profile')
    def test_cmd_hardware_json_output(self, mock_detect, mock_output_json):
        mock_detect.return_value = ('generic', {'label': 'Generic'})

        with patch('cli.main._json_output', True):
            rc = cmd_hardware(argparse.Namespace())

        self.assertEqual(rc, 0)
        mock_output_json.assert_called_once()


class TestPluginsCommand(unittest.TestCase):
    """Tests for read-only legacy extension inventory."""

    @patch('cli.main._print')
    @patch('cli.main.LegacyExtensionService.list_extensions', return_value=[])
    def test_cmd_plugins_list_text(self, mock_extensions, mock_print):
        with patch('cli.main._json_output', False):
            rc = cmd_plugins(argparse.Namespace(action='list', name=None))

        self.assertEqual(rc, 0)
        self.assertIn('execution disabled', mock_print.call_args_list[0].args[0])

    @patch('cli.main._output_json')
    @patch('cli.main.LegacyExtensionService.list_extensions', return_value=[])
    def test_cmd_plugins_list_json(self, mock_extensions, mock_output_json):
        with patch('cli.main._json_output', True):
            rc = cmd_plugins(argparse.Namespace(action='list', name=None))

        self.assertEqual(rc, 0)
        self.assertEqual(mock_output_json.call_args.args[0]['execution'], 'disabled')

    @patch('cli.main._print')
    def test_cmd_plugins_enable_missing_name(self, mock_print):
        with patch('cli.main._json_output', False):
            rc = cmd_plugins(argparse.Namespace(action='enable', name=None))
        self.assertEqual(rc, 2)

    @patch('cli.main._output_json')
    def test_cmd_plugins_disable_json(self, mock_output_json):
        with patch('cli.main._json_output', True):
            rc = cmd_plugins(argparse.Namespace(action='disable', name='demo'))

        self.assertEqual(rc, 2)
        self.assertEqual(mock_output_json.call_args.args[0]['error'], 'feature_retired')

    def test_cmd_plugins_unknown_action(self):
        rc = cmd_plugins(argparse.Namespace(action='unknown', name=None))
        self.assertEqual(rc, 2)


class TestPresetCommand(unittest.TestCase):
    """Tests for cmd_preset."""

    @patch('cli.main._print')
    @patch('cli.main.PresetManager')
    def test_cmd_preset_list_text(self, mock_manager_cls, mock_print):
        manager = MagicMock()
        manager.list_presets.return_value = ['gaming', 'battery']
        mock_manager_cls.return_value = manager

        with patch('cli.main._json_output', False):
            rc = cmd_preset(argparse.Namespace(action='list', name=None, path=None))

        self.assertEqual(rc, 0)
        self.assertTrue(mock_print.called)

    @patch('cli.main._output_json')
    @patch('cli.main.PresetManager')
    def test_cmd_preset_apply_json_success(self, mock_manager_cls, mock_output_json):
        manager = MagicMock()
        manager.create_review_plan.return_value = MagicMock(
            plan_id="plan-1", to_dict=MagicMock(return_value={"plan_id": "plan-1"})
        )
        mock_manager_cls.return_value = manager

        with patch('cli.main._json_output', True):
            rc = cmd_preset(argparse.Namespace(action='apply', name='gaming', path=None))

        self.assertEqual(rc, 0)
        mock_output_json.assert_called_once()
        self.assertFalse(mock_output_json.call_args.args[0]["applied"])

    @patch('cli.main._output_json')
    @patch('cli.main.PresetManager')
    def test_cmd_preset_apply_json_not_found(self, mock_manager_cls, mock_output_json):
        manager = MagicMock()
        manager.create_review_plan.side_effect = ValueError("Local profile 'missing' is missing or invalid.")
        mock_manager_cls.return_value = manager

        with patch('cli.main._json_output', True):
            rc = cmd_preset(argparse.Namespace(action='apply', name='missing', path=None))

        self.assertEqual(rc, 1)
        mock_output_json.assert_called_once()

    @patch('cli.main._print')
    @patch('cli.main.PresetManager')
    def test_cmd_preset_export_missing_args(self, mock_manager_cls, _mock_print):
        mock_manager_cls.return_value = MagicMock()
        rc = cmd_preset(argparse.Namespace(action='export', name=None, path=None))
        self.assertEqual(rc, 1)

    @patch('cli.main._print')
    @patch('cli.main.PresetManager')
    def test_cmd_preset_export_success(self, mock_manager_cls, _mock_print):
        manager = MagicMock()
        manager.export_preset.return_value = True
        mock_manager_cls.return_value = manager

        # Windows locks NamedTemporaryFile while open — close before writing
        tf = tempfile.NamedTemporaryFile(delete=False, suffix='.json')
        tf.close()
        try:
            rc = cmd_preset(argparse.Namespace(action='export', name='gaming', path=tf.name))
        finally:
            os.unlink(tf.name)

        self.assertEqual(rc, 0)

    @patch('cli.main._print')
    @patch('cli.main.PresetManager')
    def test_cmd_preset_export_write_error(self, mock_manager_cls, _mock_print):
        manager = MagicMock()
        manager.export_preset.return_value = False
        mock_manager_cls.return_value = manager

        rc = cmd_preset(argparse.Namespace(action='export', name='gaming', path='/tmp/x.json'))

        self.assertEqual(rc, 1)


if __name__ == '__main__':
    unittest.main()
