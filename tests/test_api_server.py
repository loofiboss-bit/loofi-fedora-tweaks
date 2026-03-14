"""Comprehensive security tests for API server."""

from unittest.mock import MagicMock, patch

import pytest

try:
    from fastapi.testclient import TestClient
    _HAS_FASTAPI = True
except ImportError:
    _HAS_FASTAPI = False

pytestmark = pytest.mark.skipif(not _HAS_FASTAPI, reason="fastapi not installed")

if _HAS_FASTAPI:
    from core.executor.action_result import ActionResult
    from utils.config_manager import ConfigManager
    from utils.api_server import APIServer, RouteRateLimitPolicy
    from utils.auth import AuthManager
else:
    class RouteRateLimitPolicy:  # type: ignore[no-redef]
        def __init__(self, rate=0.0, capacity=0, retry_guidance=""):
            self.rate = rate
            self.capacity = capacity
            self.retry_guidance = retry_guidance

    class APIServer:  # type: ignore[no-redef]
        _RATE_LIMIT_CONFIG = {}


@pytest.fixture
def isolated_config_dir(tmp_path):
    """Redirect config storage to a temporary directory for API tests."""
    original_dir = ConfigManager.CONFIG_DIR
    original_file = ConfigManager.CONFIG_FILE
    original_presets = ConfigManager.PRESETS_DIR

    ConfigManager.CONFIG_DIR = tmp_path / "config"
    ConfigManager.CONFIG_FILE = ConfigManager.CONFIG_DIR / "config.json"
    ConfigManager.PRESETS_DIR = ConfigManager.CONFIG_DIR / "presets"

    try:
        yield ConfigManager.CONFIG_DIR
    finally:
        ConfigManager.CONFIG_DIR = original_dir
        ConfigManager.CONFIG_FILE = original_file
        ConfigManager.PRESETS_DIR = original_presets


@pytest.fixture
def test_client(isolated_config_dir):
    """Provide a FastAPI test client for the API server."""
    server = APIServer()
    return TestClient(server.app)


@pytest.fixture
def valid_api_key(isolated_config_dir):
    """Generate and return a valid API key."""
    del isolated_config_dir
    return AuthManager.generate_api_key()


@pytest.fixture
def valid_token(test_client, valid_api_key):
    """Generate and return a valid JWT token."""
    response = test_client.post("/api/token", data={"api_key": valid_api_key})
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture
def mock_action_executor():
    """Mock ActionExecutor.run to prevent actual system execution."""
    with patch("core.executor.action_executor.ActionExecutor.run") as mock_run:
        mock_run.return_value = ActionResult(
            success=True,
            message="Mock execution successful",
            exit_code=0,
            stdout="mock output",
            stderr="",
            preview=True,
            action_id="test-action",
        )
        yield mock_run


# ============================================================================
# Basic Functionality Tests
# ============================================================================


def test_health_endpoint(test_client):
    """Health endpoint should work without authentication (no version leak)."""
    response = test_client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    # Hardened: /health no longer exposes version or codename
    assert "version" not in payload
    assert "codename" not in payload


def test_health_endpoint_uses_public_route_policy(test_client):
    """Public health checks should advertise the public route policy bucket."""
    response = test_client.get("/api/health")

    assert response.status_code == 200
    assert response.headers["X-Loofi-Route-Policy"] == "public"


def test_token_flow(test_client, valid_api_key, mock_action_executor):
    """Test complete token generation and execution flow."""
    token_resp = test_client.post("/api/token", data={"api_key": valid_api_key})
    assert token_resp.status_code == 200
    token = token_resp.json()["access_token"]

    # Use allowlisted command (echo is not in COMMAND_ALLOWLIST)
    exec_resp = test_client.post(
        "/api/execute",
        json={"command": "uname", "args": ["-r"], "preview": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert exec_resp.status_code == 200
    data = exec_resp.json()
    assert data["preview"]["preview"] is True


def test_api_key_bootstrap_allowed_without_auth(test_client):
    """Initial API key bootstrap should remain available without bearer auth."""
    response = test_client.post("/api/key")

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload["api_key"], str)
    assert payload["api_key"]


def test_api_key_rotation_requires_auth_after_bootstrap(test_client):
    """Unauthenticated key rotation should be rejected after bootstrap completes."""
    first_response = test_client.post("/api/key")
    assert first_response.status_code == 200

    second_response = test_client.post("/api/key")

    assert second_response.status_code == 401
    assert "Missing bearer token" in second_response.json()["detail"]


def test_api_key_rotation_allows_authenticated_caller(test_client):
    """Authenticated callers should be able to rotate the stored API key."""
    first_key = test_client.post("/api/key").json()["api_key"]
    token_response = test_client.post("/api/token", data={"api_key": first_key})
    assert token_response.status_code == 200
    token = token_response.json()["access_token"]

    rotate_response = test_client.post(
        "/api/key",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert rotate_response.status_code == 200
    assert rotate_response.json()["api_key"] != first_key


def test_token_generation_requires_bootstrap_key(test_client):
    """Token requests should fail clearly until bootstrap has provisioned an API key."""
    response = test_client.post("/api/token", data={"api_key": "missing-key"})

    assert response.status_code == 409
    assert "Bootstrap API key required" in response.json()["detail"]


@patch("utils.api_server.AuthManager.bootstrap_pending", side_effect=PermissionError("unsafe perms"))
def test_api_key_rejects_unsafe_auth_storage(mock_bootstrap_pending, test_client):
    """Bootstrap should fail closed when auth storage permissions are unsafe."""
    response = test_client.post("/api/key")

    assert response.status_code == 503
    assert "unsafe permissions" in response.json()["detail"]


@patch("utils.api_server.AuthManager.issue_token", side_effect=ValueError("bad auth blob"))
@patch("utils.api_server.AuthManager.bootstrap_pending", return_value=False)
def test_api_token_rejects_invalid_auth_storage(mock_bootstrap_pending, mock_issue_token, test_client):
    """Token issuance should fail closed when persisted auth storage is invalid."""
    response = test_client.post("/api/token", data={"api_key": "candidate-key"})

    assert response.status_code == 503
    assert "invalid" in response.json()["detail"].lower()


@patch.object(
    APIServer,
    "_RATE_LIMIT_CONFIG",
    new={
        "auth": RouteRateLimitPolicy(
            rate=0.0,
            capacity=2,
            retry_guidance="Wait before retrying auth endpoints.",
        ),
        "read": RouteRateLimitPolicy(
            rate=10.0,
            capacity=50,
            retry_guidance="Slow read polling.",
        ),
        "mutation": RouteRateLimitPolicy(
            rate=10.0,
            capacity=50,
            retry_guidance="Slow mutation retries.",
        ),
    },
)
def test_auth_routes_rate_limited_with_retry_guidance(isolated_config_dir):
    """Auth/bootstrap routes should emit explicit 429 retry guidance when throttled."""
    del isolated_config_dir

    server = APIServer()
    client = TestClient(server.app)

    api_key = client.post("/api/key").json()["api_key"]
    ok_response = client.post("/api/token", data={"api_key": api_key})
    limited_response = client.post("/api/token", data={"api_key": api_key})

    assert ok_response.status_code == 200
    assert limited_response.status_code == 429
    assert limited_response.headers["X-Loofi-Route-Policy"] == "auth"
    assert int(limited_response.headers["Retry-After"]) >= 1

    payload = limited_response.json()
    assert payload["route_policy"] == "auth"
    assert payload["retry_after_seconds"] >= 1
    assert "Retry after" in payload["detail"]


def test_api_server_rejects_non_loopback_bind_without_allow_expose():
    """APIServer should refuse unsafe binds unless explicitly overridden."""
    with pytest.raises(ValueError, match="--unsafe-expose"):
        APIServer(host="0.0.0.0", port=8000)


def test_api_server_allows_non_loopback_bind_with_unsafe_expose():
    """APIServer should permit non-loopback binds when explicitly opted in."""
    server = APIServer(host="0.0.0.0", port=8000, allow_expose=True)
    assert server.host == "0.0.0.0"
    assert server.allow_expose is True


def test_api_server_allows_ipv6_loopback_without_unsafe_expose():
    """Loopback IPv6 should remain a safe default bind target."""
    server = APIServer(host="::1", port=8000)
    assert server.host == "::1"


def test_api_server_allows_localhost_without_unsafe_expose():
    """The localhost hostname should remain an allowed default bind target."""
    server = APIServer(host="localhost", port=8000)
    assert server.host == "localhost"


@patch.object(
    APIServer,
    "_RATE_LIMIT_CONFIG",
    new={
        "auth": RouteRateLimitPolicy(
            rate=10.0,
            capacity=50,
            retry_guidance="Wait before retrying auth endpoints.",
        ),
        "read": RouteRateLimitPolicy(
            rate=0.0,
            capacity=1,
            retry_guidance="Reduce read polling before retrying.",
        ),
        "mutation": RouteRateLimitPolicy(
            rate=10.0,
            capacity=50,
            retry_guidance="Slow mutation retries.",
        ),
    },
)
@patch("utils.monitor.SystemMonitor.get_system_health")
def test_read_only_routes_rate_limited_with_guidance(mock_health, isolated_config_dir):
    """Authenticated read-only routes should throttle independently from mutations."""
    del isolated_config_dir

    mock_health.return_value = MagicMock(
        hostname="test-host",
        uptime=12345,
        memory=MagicMock(used_human="1GB", total_human="8GB", percent_used=12.5),
        cpu=MagicMock(load_1min=0.5, load_5min=0.6, load_15min=0.7, core_count=4, load_percent=15.0),
        memory_status="good",
        cpu_status="good",
    )

    client = TestClient(APIServer().app)
    api_key = client.post("/api/key").json()["api_key"]
    token = client.post("/api/token", data={"api_key": api_key}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    ok_response = client.get("/api/info", headers=headers)
    limited_response = client.get("/api/info", headers=headers)

    assert ok_response.status_code == 200
    assert ok_response.headers["X-Loofi-Route-Policy"] == "read"
    assert limited_response.status_code == 429
    assert limited_response.headers["X-Loofi-Route-Policy"] == "read"
    assert int(limited_response.headers["Retry-After"]) >= 1
    payload = limited_response.json()
    assert payload["route_policy"] == "read"
    assert "Retry after" in payload["detail"]

# ============================================================================
# Authentication Security Tests
# ============================================================================


class TestAuthenticationSecurity:
    """Tests for authentication security mechanisms."""

    def test_execute_without_bearer_token(self, test_client):
        """Accessing /api/execute without Bearer token should return 401."""
        response = test_client.post(
            "/api/execute",
            json={"command": "echo", "args": ["test"], "preview": True},
        )
        assert response.status_code == 401
        assert "Missing bearer token" in response.json()["detail"]

    def test_execute_with_invalid_token_format(self, test_client):
        """Accessing /api/execute with invalid token format should return 401."""
        response = test_client.post(
            "/api/execute",
            json={"command": "echo", "args": ["test"], "preview": True},
            headers={"Authorization": "Bearer invalid-token-format"},
        )
        assert response.status_code == 401
        assert "Invalid token" in response.json()["detail"]

    def test_execute_with_malformed_bearer_header(self, test_client):
        """Malformed Authorization header should return 401."""
        response = test_client.post(
            "/api/execute",
            json={"command": "echo", "args": ["test"], "preview": True},
            headers={"Authorization": "NotBearer some-token"},
        )
        assert response.status_code == 401

    def test_execute_with_expired_token(self, test_client, valid_api_key):
        """Expired token should return 401."""
        # Mock jwt.encode to create an expired token
        with patch("utils.auth.jwt.encode") as mock_encode:
            # Create a token that expired 1 hour ago
            mock_encode.return_value = "expired.token.here"

            # Mock jwt.decode to raise exception for expired token
            with patch("utils.auth.jwt.decode") as mock_decode:
                import jwt
                mock_decode.side_effect = jwt.ExpiredSignatureError("Token expired")

                response = test_client.post(
                    "/api/execute",
                    json={"command": "echo", "args": ["test"], "preview": True},
                    headers={"Authorization": "Bearer expired.token.here"},
                )
                assert response.status_code == 401

    def test_token_generation_with_wrong_api_key(self, test_client):
        """Token generation with invalid API key should return 401."""
        assert test_client.post("/api/key").status_code == 200

        response = test_client.post(
            "/api/token",
            data={"api_key": "wrong-api-key-12345"},
        )
        assert response.status_code == 401
        assert "Invalid API key" in response.json()["detail"]

    def test_token_generation_without_api_key(self, test_client):
        """Token generation without API key should return 422 validation error."""
        assert test_client.post("/api/key").status_code == 200

        response = test_client.post("/api/token", data={})
        assert response.status_code == 422  # FastAPI validation error for missing required field


# ============================================================================
# Input Validation Tests
# ============================================================================


class TestInputValidation:
    """Tests for input validation and sanitization."""

    def test_command_injection_attempt(self, test_client, valid_token, mock_action_executor):
        """Command injection attempts should be blocked by allowlist."""
        response = test_client.post(
            "/api/execute",
            json={
                "command": "; rm -rf /",
                "args": ["test"],
                "preview": True,
            },
            headers={"Authorization": f"Bearer {valid_token}"},
        )
        # Hardened: command not in COMMAND_ALLOWLIST → 403
        assert response.status_code == 403
        mock_action_executor.assert_not_called()

    def test_path_traversal_in_args(self, test_client, valid_token, mock_action_executor):
        """Path traversal attempts in args pass through to executor (command must be allowlisted)."""
        response = test_client.post(
            "/api/execute",
            json={
                "command": "uname",
                "args": ["../../etc/passwd"],
                "preview": True,
            },
            headers={"Authorization": f"Bearer {valid_token}"},
        )
        assert response.status_code == 200
        # Verify args were passed through
        mock_action_executor.assert_called()
        call_args = mock_action_executor.call_args[0]
        assert "../../etc/passwd" in call_args[1]

    def test_non_allowlisted_command_rejected(self, test_client, valid_token, mock_action_executor):
        """Commands not in COMMAND_ALLOWLIST should be rejected with 403."""
        response = test_client.post(
            "/api/execute",
            json={
                "command": "cat",
                "args": ["/etc/passwd"],
                "preview": True,
            },
            headers={"Authorization": f"Bearer {valid_token}"},
        )
        assert response.status_code == 403
        mock_action_executor.assert_not_called()

    def test_malformed_json_payload(self, test_client, valid_token):
        """Malformed JSON should return 422."""
        response = test_client.post(
            "/api/execute",
            content=b"not-valid-json{{{",
            headers={
                "Authorization": f"Bearer {valid_token}",
                "Content-Type": "application/json",
            },
        )
        assert response.status_code == 422

    def test_missing_required_field_command(self, test_client, valid_token):
        """Missing required 'command' field should return 422."""
        response = test_client.post(
            "/api/execute",
            json={"args": ["test"], "preview": True},
            headers={"Authorization": f"Bearer {valid_token}"},
        )
        assert response.status_code == 422

    def test_extremely_long_command(self, test_client, valid_token, mock_action_executor):
        """Extremely long command should be rejected by allowlist."""
        long_command = "a" * 10000
        response = test_client.post(
            "/api/execute",
            json={
                "command": long_command,
                "args": ["test"],
                "preview": True,
            },
            headers={"Authorization": f"Bearer {valid_token}"},
        )
        # Hardened: not in COMMAND_ALLOWLIST → 403
        assert response.status_code == 403
        mock_action_executor.assert_not_called()

    def test_extremely_long_args(self, test_client, valid_token, mock_action_executor):
        """Extremely long args array should be handled for allowlisted commands."""
        long_args = ["arg" + str(i) for i in range(1000)]
        response = test_client.post(
            "/api/execute",
            json={
                "command": "uname",
                "args": long_args,
                "preview": True,
            },
            headers={"Authorization": f"Bearer {valid_token}"},
        )
        assert response.status_code == 200

    def test_null_values_in_payload(self, test_client, valid_token):
        """Null values in optional fields should be handled."""
        response = test_client.post(
            "/api/execute",
            json={
                "command": "echo",
                "args": None,  # Should default to empty list
                "preview": True,
            },
            headers={"Authorization": f"Bearer {valid_token}"},
        )
        # Pydantic validation should handle this
        assert response.status_code in [200, 422]


# ============================================================================
# Authorization Tests
# ============================================================================


class TestAuthorization:
    """Tests for authorization and access control."""

    def test_pkexec_requires_auth(self, test_client, valid_token, mock_action_executor):
        """pkexec=true requires valid authentication."""
        response = test_client.post(
            "/api/execute",
            json={
                "command": "dnf",
                "args": ["clean", "all"],
                "pkexec": True,
                "preview": True,
            },
            headers={"Authorization": f"Bearer {valid_token}"},
        )
        assert response.status_code == 200
        # Verify pkexec flag was passed to executor
        call_kwargs = mock_action_executor.call_args[1]
        assert call_kwargs.get("pkexec") is True

    def test_pkexec_without_auth_fails(self, test_client):
        """pkexec=true without auth should return 401."""
        response = test_client.post(
            "/api/execute",
            json={
                "command": "dnf",
                "args": ["clean", "all"],
                "pkexec": True,
                "preview": True,
            },
        )
        assert response.status_code == 401

    def test_preview_mode_requires_auth(self, test_client):
        """Preview mode requires authentication."""
        response = test_client.post(
            "/api/execute",
            json={
                "command": "echo",
                "args": ["test"],
                "preview": True,
            },
        )
        assert response.status_code == 401

    def test_execute_mode_requires_auth(self, test_client):
        """Execute mode (preview=false) requires authentication."""
        response = test_client.post(
            "/api/execute",
            json={
                "command": "echo",
                "args": ["test"],
                "preview": False,
            },
        )
        assert response.status_code == 401

    def test_info_endpoint_without_auth(self, test_client):
        """Read-only /api/info now requires Bearer JWT (hardened)."""
        response = test_client.get("/api/info")
        # Hardened: /info requires authentication
        assert response.status_code in [401, 403]

    def test_info_endpoint_with_auth(self, test_client, valid_token):
        """Authenticated /api/info should return system data."""
        with patch("utils.monitor.SystemMonitor.get_system_health") as mock_health:
            mock_health.return_value = MagicMock(
                hostname="test-host",
                uptime=12345,
                memory=MagicMock(used_human="1GB", total_human="8GB", percent_used=12.5),
                cpu=MagicMock(load_1min=0.5, load_5min=0.6, load_15min=0.7, core_count=4, load_percent=15.0),
                memory_status="good",
                cpu_status="good",
            )

            response = test_client.get(
                "/api/info",
                headers={"Authorization": f"Bearer {valid_token}"},
            )
            assert response.status_code == 200
            data = response.json()
            assert "version" in data
            assert "system_type" in data


# ============================================================================
# Error Handling Tests
# ============================================================================


class TestErrorHandling:
    """Tests for error handling and response serialization."""

    def test_invalid_command_execution(self, test_client, valid_token):
        """Non-allowlisted commands should be rejected with 403."""
        response = test_client.post(
            "/api/execute",
            json={
                "command": "invalid-command-xyz",
                "args": [],
                "preview": True,
            },
            headers={"Authorization": f"Bearer {valid_token}"},
        )
        # Hardened: command not in allowlist → 403
        assert response.status_code == 403

    def test_allowlisted_command_failure(self, test_client, valid_token):
        """ActionExecutor should handle allowlisted command failure gracefully."""
        with patch("core.executor.action_executor.ActionExecutor.run") as mock_run:
            mock_run.return_value = ActionResult(
                success=False,
                message="Command failed",
                exit_code=127,
                stdout="",
                stderr="command not found",
                preview=True,
            )

            response = test_client.post(
                "/api/execute",
                json={
                    "command": "uname",
                    "args": [],
                    "preview": True,
                },
                headers={"Authorization": f"Bearer {valid_token}"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["preview"]["success"] is False

    def test_executor_exception_handling(self, test_client, valid_token):
        """ActionExecutor exceptions should propagate as 500 errors."""
        with patch("core.executor.action_executor.ActionExecutor.run") as mock_run:
            mock_run.side_effect = Exception("Unexpected executor error")

            # Use allowlisted command to pass the allowlist check
            with pytest.raises(Exception):
                test_client.post(
                    "/api/execute",
                    json={
                        "command": "uname",
                        "args": ["-r"],
                        "preview": True,
                    },
                    headers={"Authorization": f"Bearer {valid_token}"},
                )

    def test_action_result_serialization(self, test_client, valid_token):
        """ActionResult should serialize correctly with all fields."""
        with patch("core.executor.action_executor.ActionExecutor.run") as mock_run:
            mock_run.return_value = ActionResult(
                success=True,
                message="Test action completed",
                exit_code=0,
                stdout="test output",
                stderr="test warning",
                preview=True,
                needs_reboot=True,
                action_id="test-123",
            )

            # Use allowlisted command
            response = test_client.post(
                "/api/execute",
                json={
                    "command": "uname",
                    "args": [],
                    "preview": True,
                },
                headers={"Authorization": f"Bearer {valid_token}"},
            )
            assert response.status_code == 200
            data = response.json()
            assert "result" in data
            assert "preview" in data
            assert data["preview"]["success"] is True
            assert data["preview"]["needs_reboot"] is True
            assert data["preview"]["action_id"] == "test-123"

    def test_network_timeout_simulation(self, test_client, valid_token):
        """Simulate network timeout during execution."""
        with patch("core.executor.action_executor.ActionExecutor.run") as mock_run:
            import subprocess
            mock_run.side_effect = subprocess.TimeoutExpired("test", 120)

            # Use allowlisted command to pass the allowlist check
            with pytest.raises(subprocess.TimeoutExpired):
                test_client.post(
                    "/api/execute",
                    json={
                        "command": "uname",
                        "args": ["-a"],
                        "preview": True,
                    },
                    headers={"Authorization": f"Bearer {valid_token}"},
                )


# ============================================================================
# Additional Security Tests
# ============================================================================


class TestAdditionalSecurity:
    """Additional security edge cases."""

    def test_empty_command(self, test_client, valid_token):
        """Empty command string should be rejected by allowlist."""
        response = test_client.post(
            "/api/execute",
            json={
                "command": "",
                "args": ["test"],
                "preview": True,
            },
            headers={"Authorization": f"Bearer {valid_token}"},
        )
        # Empty string not in allowlist → 403
        assert response.status_code in [403, 422]

    def test_special_characters_in_command(self, test_client, valid_token, mock_action_executor):
        """Special characters in command should be blocked by allowlist."""
        response = test_client.post(
            "/api/execute",
            json={
                "command": "test & echo",
                "args": ["$(whoami)"],
                "preview": True,
            },
            headers={"Authorization": f"Bearer {valid_token}"},
        )
        # Hardened: not in COMMAND_ALLOWLIST → 403
        assert response.status_code == 403
        mock_action_executor.assert_not_called()

    def test_unicode_in_payload(self, test_client, valid_token, mock_action_executor):
        """Unicode characters should be handled correctly for allowlisted commands."""
        response = test_client.post(
            "/api/execute",
            json={
                "command": "uname",
                "args": ["你好", "мир", "🚀"],
                "preview": True,
            },
            headers={"Authorization": f"Bearer {valid_token}"},
        )
        assert response.status_code == 200

    def test_action_id_validation(self, test_client, valid_token, mock_action_executor):
        """Action ID should be passed through correctly for allowlisted commands."""
        response = test_client.post(
            "/api/execute",
            json={
                "command": "uname",
                "args": ["-r"],
                "preview": True,
                "action_id": "custom-action-123",
            },
            headers={"Authorization": f"Bearer {valid_token}"},
        )
        assert response.status_code == 200
        # Verify action_id was passed to executor
        call_kwargs = mock_action_executor.call_args[1]
        assert call_kwargs.get("action_id") == "custom-action-123"
