"""Profile editing stays local and preserves opaque portable rows."""
from __future__ import annotations

import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core.tasks.tweak_library import ProfileLibrary, edit_profile
from core.tasks.tweak_profiles import TweakProfile
from core.tasks.tweaks import BY_ID, TweakState


class ProfileEditTests(unittest.TestCase):
    def setUp(self):
        self.tweak = BY_ID['kde-single-click']
        self.ready = TweakState(self.tweak, 'ready', 'false', self.tweak.choices)
        self.source = TweakProfile('Original', 'kde', (('kde-single-click', 'false'), ('future-setting', 'custom')))

    def test_edit_keeps_original_and_unknown_rows(self):
        result = edit_profile(self.source, 'Edited', (('kde-single-click', 'true'), ('future-setting', 'custom')), (self.ready,))
        self.assertEqual(result.name, 'Edited')
        self.assertEqual(dict(result.settings)['kde-single-click'], 'true')
        self.assertEqual(dict(self.source.settings)['kde-single-click'], 'false')
        self.assertEqual(dict(result.settings)['future-setting'], 'custom')
        self.assertEqual(result.to_dict()['schema'], 'loofi.tweak-profile/v1')

    def test_unavailable_rows_can_be_retained_or_explicitly_removed(self):
        unavailable = TweakState(self.tweak, 'unavailable', message='Missing tool')
        result = edit_profile(self.source, 'Copy', self.source.settings, (unavailable,))
        self.assertEqual(result.settings, self.source.settings)
        result = edit_profile(self.source, 'Copy', (), (unavailable,))
        self.assertEqual(result.settings, ())
        with self.assertRaisesRegex(ValueError, 'unavailable'):
            edit_profile(self.source, 'Copy', (('kde-single-click', 'true'),), (unavailable,))

    def test_invalid_new_values_and_names_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'supported target'):
            edit_profile(self.source, 'Copy', (('kde-single-click', 'invalid'),), (self.ready,))
        with self.assertRaises(ValueError):
            edit_profile(self.source, '', self.source.settings, (self.ready,))
        with self.assertRaisesRegex(ValueError, 'unavailable'):
            edit_profile(self.source, 'Copy', (('new-unknown', 'true'),), ())

    def test_installed_dynamic_choices_are_authoritative(self):
        tweak = BY_ID['kde-plasma-style']
        source = TweakProfile('Appearance', 'kde', ((tweak.id, 'old-theme'),))
        state = TweakState(tweak, 'ready', 'new-theme', (('new-theme', 'New theme'),))
        retained = edit_profile(source, 'Copy', source.settings, (state,))
        self.assertEqual(retained.settings, source.settings)
        with self.assertRaisesRegex(ValueError, 'supported target'):
            edit_profile(source, 'Copy', ((tweak.id, 'uninstalled-theme'),), (state,))

    @patch('core.tasks.tweak_library.save_profile')
    @patch('pathlib.Path.is_symlink', return_value=False)
    @patch('pathlib.Path.mkdir')
    def test_new_version_has_new_content_id_and_write_failures_propagate(self, mkdir, symlink, save):
        library = ProfileLibrary(Path('/test/profiles'))
        original = library.add(self.source)
        edited = edit_profile(self.source, 'Edited', self.source.settings, ())
        copied = library.add(edited)
        self.assertNotEqual(original.id, copied.id)
        self.assertEqual(save.call_args_list[0].args[0], library.root / (original.id + '.json'))
        self.assertEqual(save.call_args_list[1].args[0], library.root / (copied.id + '.json'))
        save.side_effect = OSError('Read-only directory')
        with self.assertRaisesRegex(OSError, 'Read-only'):
            library.add(edited)


class ProfileEditorDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tweak = BY_ID['kde-single-click']
        self.source = TweakProfile('Original', 'kde', ((self.tweak.id, 'false'), ('future-setting', 'custom')))
        self.state = TweakState(self.tweak, 'ready', 'false', self.tweak.choices)

    @patch('core.actions.operation_controller.OperationController.prepare')
    @patch('core.tasks.tweak_library.ProfileLibrary.add')
    def test_editor_changes_targets_without_saving_or_changing_host(self, add, prepare):
        from ui.tweak_profile_editor import ProfileEditorDialog
        dialog = ProfileEditorDialog(self.source, (self.state,))
        include, control = dialog.rows[self.tweak.id]
        self.assertTrue(include.isChecked())
        control.setCurrentIndex(control.findData('true'))
        self.assertFalse(dialog.rows['future-setting'][1].isEnabled())
        dialog._save()
        self.assertEqual(dict(dialog.saved_profile.settings)[self.tweak.id], 'true')
        self.assertEqual(dict(dialog.saved_profile.settings)['future-setting'], 'custom')
        self.assertEqual(dict(self.source.settings)[self.tweak.id], 'false')
        add.assert_not_called()
        prepare.assert_not_called()
        dialog.close()

    def test_explicit_removal_and_validation_feedback(self):
        from ui.tweak_profile_editor import ProfileEditorDialog
        dialog = ProfileEditorDialog(self.source, (self.state,))
        dialog.rows['future-setting'][0].setChecked(False)
        dialog.name.setText('')
        dialog._save()
        self.assertIsNone(dialog.saved_profile)
        self.assertIn('Profile name', dialog.error.text())
        dialog.name.setText('New version')
        dialog._save()
        self.assertNotIn('future-setting', dict(dialog.saved_profile.settings))
        dialog.close()

    def test_unavailable_originals_are_included_and_absent_rows_disabled(self):
        from ui.tweak_profile_editor import ProfileEditorDialog
        absent = BY_ID['kde-focus-stealing-prevention']
        dialog = ProfileEditorDialog(self.source, (
            TweakState(self.tweak, 'unavailable', message='Missing tool'),
            TweakState(absent, 'unavailable', message='Missing tool'),
        ))
        self.assertTrue(dialog.rows[self.tweak.id][0].isChecked())
        self.assertTrue(dialog.rows[self.tweak.id][0].isEnabled())
        self.assertFalse(dialog.rows[self.tweak.id][1].isEnabled())
        self.assertFalse(dialog.rows[absent.id][0].isEnabled())
        dialog._save()
        self.assertEqual(dialog.saved_profile.settings, self.source.settings)
        dialog.close()


class ProfileEditorWorkerTests(unittest.TestCase):
    @patch('ui.tweak_profile_editor.ProfileEditorDialog')
    @patch('core.tasks.tweak_library.ProfileLibrary')
    def test_save_uses_existing_worker_and_reports_write_failure(self, library, dialog_type):
        from PyQt6.QtWidgets import QDialog
        from ui.tweak_profiles import TweakProfilesMixin

        edited = TweakProfile('Edited', 'kde', ())
        dialog_type.return_value.exec.return_value = QDialog.DialogCode.Accepted
        dialog_type.return_value.saved_profile = edited
        library.return_value.add.side_effect = OSError('Read-only directory')
        page = Mock()
        failed = Mock()
        finished = Mock()
        adapter = Mock(failed=failed, finished=finished)
        owner = SimpleNamespace(tr=lambda text: text, _profile_idle=lambda _page: True,
                                _new_utility_operation_adapter=Mock(return_value=adapter))
        TweakProfilesMixin._show_tweak_profile_editor(owner, page, TweakProfile('Original', 'kde', ()), ())
        owner._new_utility_operation_adapter.assert_called_once_with(phase='inspection')
        library.return_value.add.assert_not_called()
        operation = adapter.start.call_args.args[0]
        with self.assertRaisesRegex(OSError, 'Read-only'):
            operation()
        library.return_value.add.assert_called_once_with(edited)
        failed.connect.assert_called_once_with(page.set_error)

    @patch('ui.tweak_profiles.snapshot')
    def test_inspection_runs_on_worker_and_cancelled_results_do_not_open_editor(self, snapshot):
        from ui.tweak_profiles import TweakProfilesMixin

        callbacks = {}
        adapter = Mock(cancel_requested=False)
        for signal in ('finished', 'failed', 'cancelled', 'stopped'):
            getattr(adapter, signal).connect.side_effect = lambda callback, name=signal: callbacks.update({name: callback})
        page = Mock(profile=Mock())
        runtime = Mock()
        owner = SimpleNamespace(tr=lambda text: text, _profile_idle=lambda _page: True,
                                _profile_controller=lambda: SimpleNamespace(orchestrator=SimpleNamespace(runtime=runtime)),
                                _new_utility_operation_adapter=Mock(return_value=adapter),
                                _show_tweak_profile_editor=Mock())
        source = TweakProfile('Original', 'kde', ())
        self.assertTrue(TweakProfilesMixin._start_tweak_profile_editor(owner, page, source))
        snapshot.assert_not_called()
        adapter.start.call_args.args[0]()
        snapshot.assert_called_once()
        callbacks['finished'](())
        adapter.cancel_requested = True
        callbacks['stopped']()
        owner._show_tweak_profile_editor.assert_not_called()
        adapter.cancel_requested = False
        callbacks['stopped']()
        owner._show_tweak_profile_editor.assert_called_once_with(page, source, ())


if __name__ == '__main__':
    unittest.main()
