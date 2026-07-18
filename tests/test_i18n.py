"""
Tests for I18nManager — v31.0 Smart UX
"""
import unittest
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'loofi-fedora-tweaks'))

from utils.i18n import I18nManager


class TestI18nManager(unittest.TestCase):
    """Tests for I18nManager."""

    def test_default_locale(self):
        """Default locale is 'en'."""
        I18nManager._current_locale = "en"
        self.assertEqual(I18nManager.get_locale(), "en")

    def test_translations_dir_is_string(self):
        """translations_dir returns a string path."""
        result = I18nManager.translations_dir()
        self.assertIsInstance(result, str)
        self.assertIn("translations", result)

    def test_available_locales_is_english_only(self):
        self.assertEqual(I18nManager.available_locales(), ["en"])

    def test_set_locale_english(self):
        """Setting locale to 'en' always succeeds."""
        app = MagicMock()
        I18nManager._translator = MagicMock()
        result = I18nManager.set_locale(app, "en")
        self.assertTrue(result)
        self.assertEqual(I18nManager.get_locale(), "en")
        app.removeTranslator.assert_called_once()

    def test_set_locale_rejects_non_english(self):
        app = MagicMock()
        I18nManager._translator = None
        result = I18nManager.set_locale(app, "sv")
        self.assertFalse(result)
        self.assertEqual(I18nManager.get_locale(), "en")

    @patch('os.path.isfile', return_value=True)
    @patch('os.path.expanduser', return_value="/tmp/test_settings.json")
    def test_get_preferred_locale_default(self, mock_expand, mock_isfile):
        """Returns 'en' when no settings file exists."""
        mock_isfile.return_value = False
        locale = I18nManager.get_preferred_locale()
        self.assertEqual(locale, "en")

    def test_get_preferred_locale_ignores_stale_non_english_state(self):
        self.assertEqual(I18nManager.get_preferred_locale(), "en")

    @patch('builtins.open', side_effect=OSError("IO error"))
    @patch('os.path.isfile', return_value=True)
    @patch('os.path.expanduser', return_value="/tmp/settings.json")
    def test_get_preferred_locale_error(self, mock_expand, mock_isfile, mock_open):
        """Returns 'en' on file read error."""
        locale = I18nManager.get_preferred_locale()
        self.assertEqual(locale, "en")

    @patch('builtins.open', new_callable=unittest.mock.mock_open)
    @patch('os.path.isfile', return_value=False)
    @patch('os.makedirs')
    @patch('os.path.expanduser', return_value="/tmp/config/settings.json")
    def test_save_preferred_locale(self, mock_expand, mock_makedirs, mock_isfile, mock_open):
        """Normalizes a legacy locale request to English."""
        I18nManager.save_preferred_locale("sv")
        mock_open.assert_called()

    @patch('builtins.open', side_effect=OSError("IO error"))
    @patch('os.path.isfile', return_value=False)
    @patch('os.makedirs')
    @patch('os.path.expanduser', return_value="/tmp/config/settings.json")
    def test_save_preferred_locale_error(self, mock_expand, mock_makedirs, mock_isfile, mock_open):
        """Save locale handles errors gracefully."""
        # Should not raise
        I18nManager.save_preferred_locale("sv")


if __name__ == '__main__':
    unittest.main()
