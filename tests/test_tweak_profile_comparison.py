"""Saved profile comparison never reads or mutates computer settings."""
from __future__ import annotations

import argparse
import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from cli.commands.tweaks_commands import _handle_profile
from cli.parser_domains.tweaks import register_tweaks_command
from core.tasks.tweak_library import LibraryEntry, ProfileLibrary, compare_profiles
from core.tasks.tweak_profiles import TweakProfile
from core.tasks.tweaks import BY_ID


def entry(identifier, settings=(), desktop="kde"):
    return LibraryEntry(identifier, TweakProfile(identifier, desktop, tuple(settings)))


class ProfileComparisonTests(unittest.TestCase):
    @patch("core.tasks.tweak_profiles.snapshot")
    @patch("core.tasks.tweak_library.save_profile")
    def test_all_statuses_labels_and_exact_opaque_values(self, save, snapshot):
        left = entry("left", (("kde-single-click", "false"), ("future", "opaque 'value'"), ("old", "1"), ("same", "unchanged")))
        right = entry("right", (("kde-single-click", "true"), ("future", "opaque 'value'"), ("new", "2"), ("same", "unchanged")))
        rows = {row.id: row for row in compare_profiles(left, right).entries}
        self.assertEqual(rows["kde-single-click"].status, "changed")
        self.assertEqual(rows["kde-single-click"].title, BY_ID["kde-single-click"].title)
        self.assertEqual(rows["kde-single-click"].right_label, dict(BY_ID["kde-single-click"].choices)["true"])
        self.assertEqual(rows["future"].left_value, "opaque 'value'")
        self.assertEqual(rows["future"].left_label, "opaque 'value'")
        self.assertEqual(rows["future"].title, "future")
        self.assertEqual(rows["future"].status, "unchanged")
        self.assertEqual(rows["old"].status, "removed")
        self.assertIsNone(rows["old"].right_value)
        self.assertEqual(rows["new"].status, "added")
        reverse = {row.id: row for row in compare_profiles(right, left).entries}
        self.assertEqual(reverse["new"].status, "removed")
        self.assertEqual(reverse["old"].status, "added")
        self.assertEqual(reverse["kde-single-click"].left_value, "true")
        self.assertEqual(left.profile.to_dict()["schema"], "loofi.tweak-profile/v1")
        snapshot.assert_not_called()
        save.assert_not_called()

    def test_rejects_different_desktops(self):
        with self.assertRaisesRegex(ValueError, "same desktop"):
            compare_profiles(entry("left"), entry("right", desktop="gnome"))

    @patch("core.tasks.tweak_library.ProfileLibrary.list")
    def test_library_missing_id_and_read_only_lookup(self, listing):
        listing.return_value = (entry("left"), entry("right"))
        library = ProfileLibrary(Path("/test/profiles"))
        self.assertEqual(library.compare("left", "right", object()).right.id, "right")
        with self.assertRaisesRegex(ValueError, "not found: missing"):
            library.compare("left", "missing", object())

    def test_parser(self):
        parser = argparse.ArgumentParser()
        register_tweaks_command(parser.add_subparsers(dest="command"))
        args = parser.parse_args(["tweaks", "profile", "library", "compare", "left", "right", "--json"])
        self.assertEqual((args.library_action, args.left_id, args.right_id, args.json), ("compare", "left", "right", True))

    @patch("core.tasks.tweak_library.ProfileLibrary")
    def test_cli_json_and_text_do_not_inspect_runtime(self, library):
        comparison = compare_profiles(entry("left", (("future", "first"),)), entry("right", (("future", "second"),)))
        library.return_value.compare.return_value = comparison
        args = SimpleNamespace(profile_action="library", library_action="compare", left_id="left", right_id="right")
        output, printing, runtime = Mock(), Mock(), Mock()
        self.assertEqual(_handle_profile(args, True, output, printing, object(), runtime, dry_run=False), 0)
        self.assertEqual(output.call_args.args[0]["entries"][0]["left_value"], "first")
        self.assertEqual(_handle_profile(args, False, output, printing, object(), runtime, dry_run=False), 0)
        self.assertIn("[changed]", printing.call_args.args[0])
        self.assertEqual(runtime.mock_calls, [])
        library.return_value.add.assert_not_called()
        library.return_value.remove.assert_not_called()


class ProfileComparisonDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_selection_differences_and_explicit_followup(self):
        from ui.tweak_profile_comparison import ProfileComparisonDialog
        left, right = entry("left", (("future", "a"),)), entry("right", (("future", "b"),))
        dialog = ProfileComparisonDialog((left, right, entry("gnome", desktop="gnome")), left)
        self.assertEqual(dialog.rows.count(), 1)
        self.assertIn("a → b", dialog.rows.item(0).text())
        dialog.right.setCurrentIndex(2)
        self.assertIn("same desktop", dialog.error.text())
        self.assertTrue(all(not button.isEnabled() for button in dialog.action_buttons))
        dialog.right.setCurrentIndex(1)
        dialog._choose(dialog.right, "review")
        self.assertEqual(dialog.operation, "review")
        self.assertEqual(dialog.chosen_entry, right)
        dialog.close()

    def test_library_compare_requires_second_profile_for_same_desktop(self):
        from ui.tweak_profiles import ProfileLibraryDialog
        dialog = ProfileLibraryDialog((entry("left"), entry("gnome", desktop="gnome")))
        self.assertFalse(dialog.compare_button.isEnabled())
        dialog.close()
        dialog = ProfileLibraryDialog((entry("left"), entry("right")))
        self.assertTrue(dialog.compare_button.isEnabled())
        dialog._choose("compare")
        self.assertEqual(dialog.operation, "compare")
        dialog.close()


class ProfileComparisonRoutingTests(unittest.TestCase):
    @patch("ui.tweak_profile_comparison.ProfileComparisonDialog")
    @patch("ui.tweak_profiles.ProfileLibraryDialog")
    def test_review_routes_selected_side_to_fresh_review(self, library_dialog, comparison_dialog):
        from PyQt6.QtWidgets import QDialog
        from ui.tweak_profiles import TweakProfilesMixin

        left, right = entry("left"), entry("right")
        library_dialog.return_value.exec.return_value = QDialog.DialogCode.Accepted
        library_dialog.return_value.operation = "compare"
        library_dialog.return_value.selected_entry.return_value = left
        comparison_dialog.return_value.exec.return_value = QDialog.DialogCode.Accepted
        comparison_dialog.return_value.operation = "review"
        comparison_dialog.return_value.chosen_entry = right
        owner, page = Mock(), Mock()
        owner.tr.side_effect = lambda text: text
        TweakProfilesMixin._show_tweak_library(owner, page, (left, right))
        owner._review_library_profile.assert_called_once_with(page, right.profile, builtin=False)
        owner._start_tweak_profile_editor.assert_not_called()

    @patch("ui.tweak_profile_comparison.ProfileComparisonDialog")
    @patch("ui.tweak_profiles.ProfileLibraryDialog")
    def test_edit_routes_to_existing_copy_editor(self, library_dialog, comparison_dialog):
        from PyQt6.QtWidgets import QDialog
        from ui.tweak_profiles import TweakProfilesMixin

        left, right = entry("left"), entry("right")
        library_dialog.return_value.exec.return_value = QDialog.DialogCode.Accepted
        library_dialog.return_value.operation = "compare"
        library_dialog.return_value.selected_entry.return_value = left
        comparison_dialog.return_value.exec.return_value = QDialog.DialogCode.Accepted
        comparison_dialog.return_value.operation = "edit"
        comparison_dialog.return_value.chosen_entry = left
        owner, page = Mock(), Mock()
        owner.tr.side_effect = lambda text: text
        TweakProfilesMixin._show_tweak_library(owner, page, (left, right))
        owner._start_tweak_profile_editor.assert_called_once_with(page, left.profile)
        owner._review_library_profile.assert_not_called()

    @patch("ui.tweak_profile_comparison.ProfileComparisonDialog")
    @patch("ui.tweak_profiles.ProfileLibraryDialog")
    def test_closing_comparison_starts_no_inspection(self, library_dialog, comparison_dialog):
        from PyQt6.QtWidgets import QDialog
        from ui.tweak_profiles import TweakProfilesMixin

        left, right = entry("left"), entry("right")
        library_dialog.return_value.exec.return_value = QDialog.DialogCode.Accepted
        library_dialog.return_value.operation = "compare"
        library_dialog.return_value.selected_entry.return_value = left
        comparison_dialog.return_value.exec.return_value = QDialog.DialogCode.Rejected
        owner, page = Mock(), Mock()
        owner.tr.side_effect = lambda text: text
        TweakProfilesMixin._show_tweak_library(owner, page, (left, right))
        owner._review_library_profile.assert_not_called()
        owner._start_tweak_profile_editor.assert_not_called()
        owner._new_utility_operation_adapter.assert_not_called()
