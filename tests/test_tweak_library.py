"""Deterministic local profile library and Companion preset contracts."""
from __future__ import annotations

import argparse
import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core.tasks.tweak_library import ProfileLibrary, LibraryEntry
from core.tasks.tweak_profiles import TweakProfile
from core.tasks.tweak_presets import profile_for_preset
from core.tasks.tweaks import BY_ID
from cli.commands.tweaks_commands import _handle_profile
from cli.parser_domains.tweaks import register_tweaks_command
from test_tweaks_v30_1 import profile


class ProfileLibraryTests(unittest.TestCase):
    def setUp(self):
        self.library = ProfileLibrary(Path('/test/profiles'))
        self.profile = TweakProfile('Personal', 'kde', (('kde-single-click', 'false'),))

    @patch('core.tasks.tweak_library.save_profile')
    @patch('pathlib.Path.is_symlink', return_value=False)
    @patch('pathlib.Path.mkdir')
    def test_add_validates_and_uses_stable_content_identity(self, mkdir, symlink, save):
        first = self.library.add(self.profile)
        second = self.library.add(self.profile)
        self.assertEqual(first.id, second.id)
        self.assertEqual(len(first.id), 64)
        self.assertFalse(first.builtin)
        mkdir.assert_called_with(parents=True, exist_ok=True, mode=0o700)
        save.assert_called_with(self.library.root / (first.id + '.json'), self.profile)

    @patch('pathlib.Path.mkdir')
    def test_invalid_profile_rejected_before_creating_directory(self, mkdir):
        with self.assertRaises(ValueError):
            self.library.add(TweakProfile('', 'kde', ()))
        mkdir.assert_not_called()

    @patch('pathlib.Path.unlink')
    def test_builtin_and_traversal_removal_rejected(self, unlink):
        for entry_id in ('focus', '../private', 'a' * 63, 'A' * 64):
            with self.assertRaises(ValueError):
                self.library.remove(entry_id)
        unlink.assert_not_called()
        self.library.remove('a' * 64)
        unlink.assert_called_once_with()

    @patch('core.tasks.tweak_library.load_profile')
    @patch('pathlib.Path.is_symlink', return_value=False)
    @patch('pathlib.Path.glob')
    @patch('pathlib.Path.exists', return_value=True)
    def test_list_keeps_builtins_when_custom_files_are_corrupt(self, exists, glob, symlink, load):
        glob.return_value = [Path('/test/profiles/' + 'a' * 64 + '.json')]
        load.side_effect = ValueError('bad JSON')
        entries = self.library.list(profile('kde'))
        self.assertEqual(len(entries), 5)
        self.assertTrue(all(entry.builtin for entry in entries))

    def test_companion_presets_use_current_supported_choices(self):
        for desktop in ('kde', 'gnome'):
            for preset_id in ('focus', 'privacy-basics', 'touchpad-comfort'):
                preset = profile_for_preset(preset_id, profile(desktop))
                for key, value in preset.settings:
                    self.assertEqual(BY_ID[key].desktop, desktop)
                    self.assertIn(value, dict(BY_ID[key].choices))
                    self.assertFalse(BY_ID[key].system_wide)
        self.assertEqual(dict(profile_for_preset('focus', profile('kde')).settings)['kde-focus-stealing-prevention'], '2')


class ProfileLibraryCliTests(unittest.TestCase):
    def test_parser_library_operations(self):
        parser = argparse.ArgumentParser()
        register_tweaks_command(parser.add_subparsers(dest='command'))
        for operation, argument in (('list', []), ('add', ['settings.json']), ('remove', ['a' * 64])):
            args = parser.parse_args(['tweaks', 'profile', 'library', operation, *argument, '--json'])
            self.assertEqual(args.library_action, operation)
            self.assertTrue(args.json)

    @patch('core.tasks.tweak_library.ProfileLibrary')
    @patch('core.tasks.tweak_profiles.load_profile')
    def test_add_dry_run_does_not_write(self, load, library):
        load.return_value = TweakProfile('Personal', 'kde', ())
        output = Mock()
        args = SimpleNamespace(profile_action='library', library_action='add', path='settings.json')
        status = _handle_profile(args, True, output, Mock(), profile('kde'), Mock(), dry_run=True)
        self.assertEqual(status, 0)
        library.return_value.add.assert_not_called()
        self.assertFalse(output.call_args.args[0]['saved'])

    @patch('core.tasks.tweak_library.ProfileLibrary')
    def test_list_has_builtin_metadata(self, library):
        library.return_value.list.return_value = (LibraryEntry('focus', TweakProfile('Focus', 'kde', ()), True),)
        output = Mock()
        args = SimpleNamespace(profile_action='library', library_action='list')
        self.assertEqual(_handle_profile(args, True, output, Mock(), profile('kde'), Mock(), dry_run=False), 0)
        self.assertTrue(output.call_args.args[0]['profiles'][0]['builtin'])


class ProfileLibraryDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def test_builtin_is_read_only_but_custom_can_be_removed(self):
        from ui.tweak_profiles import ProfileLibraryDialog

        dialog = ProfileLibraryDialog((
            LibraryEntry('focus', TweakProfile('Focus', 'kde', ()), True),
            LibraryEntry('a' * 64, TweakProfile('Personal', 'kde', ())),
        ))
        self.assertTrue(dialog.review_button.isEnabled())
        self.assertTrue(dialog.export_button.isEnabled())
        self.assertFalse(dialog.remove_button.isEnabled())
        dialog.entries.setCurrentRow(1)
        self.assertTrue(dialog.remove_button.isEnabled())
        self.assertEqual(dialog.selected_entry().profile.name, 'Personal')
        dialog.close()

    def test_empty_library_has_no_operations(self):
        from ui.tweak_profiles import ProfileLibraryDialog

        dialog = ProfileLibraryDialog(())
        self.assertFalse(dialog.review_button.isEnabled())
        self.assertFalse(dialog.export_button.isEnabled())
        self.assertFalse(dialog.remove_button.isEnabled())
        dialog.close()


if __name__ == '__main__':
    unittest.main()
