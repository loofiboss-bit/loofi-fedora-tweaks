"""
Cloud Sync Manager - Handles private, user-owned Gist backup.

Migrated from utils/cloud_sync.py in v2.0.0 "Evolution".
"""

import json
import logging
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

from core.secrets import SecretStore
from core.state.atomic_io import atomic_write_text, durable_unlink

logger = logging.getLogger(__name__)


class CloudSyncManager:
    """Manage opt-in private Gist backup without public discovery."""

    # Gist API
    GIST_API = "https://api.github.com/gists"

    # Local storage
    CONFIG_DIR = Path.home() / ".config" / "loofi-fedora-tweaks"
    TOKEN_FILE = CONFIG_DIR / ".gist_token"
    TOKEN_ACCOUNT = "github-gist-token"
    GIST_ID_FILE = CONFIG_DIR / ".gist_id"
    CACHE_DIR = CONFIG_DIR / "cache"

    # ==================== TOKEN MANAGEMENT ====================

    @classmethod
    def ensure_dirs(cls):
        """Ensure config directories exist."""
        cls.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        cls.CACHE_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def get_gist_token(cls) -> Optional[str]:
        """Return the keyring/session token, migrating legacy plaintext once."""
        existing = SecretStore.get(cls.TOKEN_ACCOUNT)
        if existing:
            return existing
        SecretStore.migrate_plaintext(cls.TOKEN_ACCOUNT, cls.TOKEN_FILE)
        return SecretStore.get(cls.TOKEN_ACCOUNT)

    @classmethod
    def save_gist_token(cls, token: str) -> bool:
        """Save a token in Secret Service or session memory only."""
        return SecretStore.set(cls.TOKEN_ACCOUNT, token).success

    @classmethod
    def clear_gist_token(cls) -> bool:
        """Remove stored token."""
        try:
            deleted = SecretStore.delete(cls.TOKEN_ACCOUNT)
            durable_unlink(cls.TOKEN_FILE)
            durable_unlink(cls.GIST_ID_FILE)
            return deleted
        except OSError as e:
            logger.debug("Failed to clear gist token: %s", e)
            return False

    @classmethod
    def get_gist_id(cls) -> Optional[str]:
        """Get stored Gist ID for syncing."""
        try:
            with open(cls.GIST_ID_FILE, "r") as f:
                return f.read().strip()
        except FileNotFoundError:
            return None

    @classmethod
    def save_gist_id(cls, gist_id: str) -> bool:
        """Save Gist ID for future syncs."""
        cls.ensure_dirs()
        try:
            atomic_write_text(cls.GIST_ID_FILE, gist_id, mode=0o600)
            return True
        except OSError as e:
            logger.debug("Failed to save gist ID: %s", e)
            return False

    # ==================== GIST SYNC ====================

    @classmethod
    def sync_to_gist(cls, config: dict) -> tuple:
        """
        Sync configuration to GitHub Gist.

        Args:
            config: Configuration dictionary to sync.

        Returns:
            (success: bool, message: str)
        """
        token = cls.get_gist_token()
        if not token:
            return (False, "No GitHub token configured. Go to Settings to add your token.")

        gist_id = cls.get_gist_id()

        # Prepare gist content
        gist_content = {
            "description": "Loofi Fedora Tweaks - Config Backup",
            "public": False,
            "files": {"loofi-fedora-tweaks-config.json": {"content": json.dumps(config, indent=2)}},
        }

        try:
            data = json.dumps(gist_content).encode("utf-8")

            if gist_id:
                # Update existing gist
                url = f"{cls.GIST_API}/{gist_id}"
                request = urllib.request.Request(url, data=data, method="PATCH")
            else:
                # Create new gist
                url = cls.GIST_API
                request = urllib.request.Request(url, data=data, method="POST")

            request.add_header("Authorization", f"token {token}")
            request.add_header("Content-Type", "application/json")
            request.add_header("Accept", "application/vnd.github.v3+json")

            with urllib.request.urlopen(request, timeout=30) as response:
                result = json.loads(response.read().decode())
                new_gist_id = result.get("id")

                if new_gist_id and new_gist_id != gist_id:
                    cls.save_gist_id(new_gist_id)

                return (True, f"Config synced to Gist: {new_gist_id}")

        except urllib.error.HTTPError as e:
            if e.code == 401:
                return (False, "Invalid GitHub token. Please update your token in Settings.")
            elif e.code == 404 and gist_id:
                # Gist was deleted, create a new one
                cls.GIST_ID_FILE.unlink(missing_ok=True)
                return cls.sync_to_gist(config)  # Retry
            else:
                return (False, f"GitHub API error: {e.code}")
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
            return (False, f"Sync failed: {str(e)}")

    @classmethod
    def sync_from_gist(cls, gist_id: Optional[str] = None) -> tuple:
        """
        Download configuration from GitHub Gist.

        Args:
            gist_id: Optional Gist ID. Uses stored ID if not provided.

        Returns:
            (success: bool, config_or_message: dict|str)
        """
        gist_id = gist_id or cls.get_gist_id()
        if not gist_id:
            return (False, "No Gist ID configured. Sync your config first or enter a Gist ID.")

        token = cls.get_gist_token()

        try:
            url = f"{cls.GIST_API}/{gist_id}"
            request = urllib.request.Request(url)

            if token:
                request.add_header("Authorization", f"token {token}")
            request.add_header("Accept", "application/vnd.github.v3+json")

            with urllib.request.urlopen(request, timeout=30) as response:
                gist_data = json.loads(response.read().decode())

                files = gist_data.get("files", {})
                config_file = files.get("loofi-fedora-tweaks-config.json")

                if not config_file:
                    return (False, "Gist does not contain a valid config file.")

                config = json.loads(config_file["content"])
                return (True, config)

        except urllib.error.HTTPError as e:
            if e.code == 404:
                return (False, "Gist not found. Check the Gist ID.")
            else:
                return (False, f"GitHub API error: {e.code}")
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
            return (False, f"Download failed: {str(e)}")

    @classmethod
    def is_online(cls) -> bool:
        """Quick check if we have internet connectivity."""
        try:
            urllib.request.urlopen("https://github.com", timeout=5)
            return True
        except (urllib.error.URLError, OSError) as e:
            logger.debug("Online check failed: %s", e)
            return False
