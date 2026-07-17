"""
Tests for FavoritesManager — v31.0 Smart UX
"""
import unittest
import sys
import os
from unittest.mock import patch, mock_open

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'loofi-fedora-tweaks'))

from utils.favorites import FavoritesManager


class TestFavoritesManager(unittest.TestCase):
    """Tests for FavoritesManager."""

    @patch('utils.favorites.os.path.isfile', return_value=False)
    def test_get_favorites_no_file(self, mock_isfile):
        """Returns empty list when no favorites file exists."""
        result = FavoritesManager.get_favorites()
        self.assertEqual(result, [])

    @patch('builtins.open', mock_open(read_data='["dashboard", "system_info"]'))
    @patch('utils.favorites.os.path.isfile', return_value=True)
    def test_get_favorites_with_file(self, mock_isfile):
        """Compatibility favorites collapse onto their maintained route."""
        result = FavoritesManager.get_favorites()
        self.assertEqual(result, ["system_info"])

    @patch('builtins.open', mock_open(read_data='invalid json'))
    @patch('utils.favorites.os.path.isfile', return_value=True)
    def test_get_favorites_invalid_json(self, mock_isfile):
        """Returns empty list on invalid JSON."""
        result = FavoritesManager.get_favorites()
        self.assertEqual(result, [])

    @patch('builtins.open', mock_open(read_data='{"not": "a list"}'))
    @patch('utils.favorites.os.path.isfile', return_value=True)
    def test_get_favorites_non_list(self, mock_isfile):
        """Returns empty list if JSON is not a list."""
        result = FavoritesManager.get_favorites()
        self.assertEqual(result, [])

    @patch('builtins.open', mock_open(read_data='{"version": 2, "favorites": ["maintenance:updates", "software:apps"]}'))
    @patch('utils.favorites.os.path.isfile', return_value=True)
    def test_get_favorites_v2(self, mock_isfile):
        """Favorites v2 returns stable route IDs."""
        result = FavoritesManager.get_favorites()
        self.assertEqual(result, ["maintenance:updates", "software:apps"])

    @patch.object(FavoritesManager, '_save')
    @patch('builtins.open', mock_open(read_data='["Updates", "Cleanup", "stale legacy"]'))
    @patch('utils.favorites.os.path.isfile', return_value=True)
    def test_get_favorites_migrates_legacy_labels(self, mock_isfile, mock_save):
        """Legacy labels migrate while unknown values remain recoverable."""
        result = FavoritesManager.get_favorites()
        self.assertEqual(result, ["maintenance:updates", "maintenance:cleanup", "stale legacy"])
        mock_save.assert_called_once_with(["maintenance:updates", "maintenance:cleanup", "stale legacy"])

    @patch.object(FavoritesManager, '_save')
    @patch.object(FavoritesManager, '_load', return_value=[])
    def test_add_favorite(self, mock_load, mock_save):
        """add_favorite adds to the list."""
        FavoritesManager.add_favorite("Updates")
        mock_save.assert_called_once_with(["maintenance:updates"])

    @patch.object(FavoritesManager, '_save')
    @patch.object(FavoritesManager, '_load', return_value=["system_info"])
    def test_add_favorite_no_duplicate(self, mock_load, mock_save):
        """add_favorite does not add duplicates."""
        FavoritesManager.add_favorite("dashboard")
        mock_save.assert_not_called()

    @patch.object(FavoritesManager, '_save')
    @patch.object(FavoritesManager, '_load', return_value=["system_info"])
    def test_remove_favorite(self, mock_load, mock_save):
        """remove_favorite removes from the list."""
        FavoritesManager.remove_favorite("dashboard")
        mock_save.assert_called_once_with([])

    @patch.object(FavoritesManager, '_save')
    @patch.object(FavoritesManager, '_load', return_value=["maintenance:updates", "system_info"])
    def test_remove_favorite_accepts_legacy_alias(self, mock_load, mock_save):
        """remove_favorite resolves legacy aliases before removal."""
        FavoritesManager.remove_favorite("Updates")
        mock_save.assert_called_once_with(["system_info"])

    @patch.object(FavoritesManager, '_save')
    @patch.object(FavoritesManager, '_load', return_value=["dashboard"])
    def test_remove_favorite_not_present(self, mock_load, mock_save):
        """remove_favorite does nothing if not in list."""
        FavoritesManager.remove_favorite("nonexistent")
        mock_save.assert_not_called()

    @patch.object(FavoritesManager, '_load', return_value=["system_info", "gaming"])
    def test_is_favorite_true(self, mock_load):
        """is_favorite returns True for existing favorite."""
        self.assertTrue(FavoritesManager.is_favorite("dashboard"))

    @patch.object(FavoritesManager, '_load', return_value=["system_info"])
    def test_is_favorite_false(self, mock_load):
        """is_favorite returns False for non-favorite."""
        self.assertFalse(FavoritesManager.is_favorite("gaming"))

    @patch.object(FavoritesManager, '_load', return_value=["maintenance:updates"])
    def test_is_favorite_accepts_legacy_alias(self, mock_load):
        """is_favorite resolves legacy aliases."""
        self.assertTrue(FavoritesManager.is_favorite("Updates"))

    @patch.object(FavoritesManager, '_save')
    @patch.object(FavoritesManager, '_load', return_value=[])
    def test_toggle_favorite_add(self, mock_load, mock_save):
        """toggle_favorite adds and returns True."""
        result = FavoritesManager.toggle_favorite("dashboard")
        self.assertTrue(result)
        mock_save.assert_called_once()

    @patch.object(FavoritesManager, '_save')
    @patch.object(FavoritesManager, '_load', return_value=["system_info"])
    def test_toggle_favorite_remove(self, mock_load, mock_save):
        """toggle_favorite removes and returns False."""
        result = FavoritesManager.toggle_favorite("dashboard")
        self.assertFalse(result)
        mock_save.assert_called_once()

    @patch('builtins.open', new_callable=mock_open)
    @patch('utils.favorites.os.makedirs')
    def test_save_writes_json(self, mock_makedirs, mock_file):
        """_save writes JSON to file."""
        FavoritesManager._save(["dashboard", "gaming"])
        mock_file.assert_called_once()
        mock_makedirs.assert_called_once()
        handle = mock_file()
        written = "".join(call.args[0] for call in handle.write.call_args_list)
        self.assertIn('"version": 3', written)
        self.assertIn('"favorites"', written)

    @patch('builtins.open', side_effect=OSError("Permission denied"))
    @patch('utils.favorites.os.makedirs')
    def test_save_handles_error(self, mock_makedirs, mock_file):
        """_save handles write errors gracefully."""
        # Should not raise
        FavoritesManager._save(["dashboard"])


if __name__ == '__main__':
    unittest.main()
