"""Loofi Web API server (FastAPI + Uvicorn)."""

import logging
import math
import ipaddress
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import uvicorn
from api.routes import executor as executor_routes
from api.routes import profiles as profiles_routes
from api.routes import system as system_routes
from fastapi import Depends, FastAPI, Form, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from version import __version__

from utils.auth import AuthManager
from utils.rate_limiter import TokenBucketRateLimiter


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RouteRateLimitPolicy:
    """Rate-limit configuration for an API route policy bucket."""

    rate: float
    capacity: int
    retry_guidance: str


class RoutePolicyLimiter:
    """Track per-client token buckets for API route policy buckets."""

    def __init__(self, config: dict[str, RouteRateLimitPolicy]):
        self._config = config
        self._limiters: dict[tuple[str, str], TokenBucketRateLimiter] = {}
        self._lock = threading.Lock()

    def _get_limiter(self, bucket: str, client_key: str) -> TokenBucketRateLimiter:
        key = (bucket, client_key)
        with self._lock:
            limiter = self._limiters.get(key)
            if limiter is None:
                policy = self._config[bucket]
                limiter = TokenBucketRateLimiter(
                    rate=policy.rate,
                    capacity=policy.capacity,
                )
                self._limiters[key] = limiter
            return limiter

    def allow(self, bucket: str, client_key: str) -> tuple[bool, int]:
        limiter = self._get_limiter(bucket, client_key)
        if limiter.acquire():
            return True, 0

        policy = self._config[bucket]
        if policy.rate <= 0:
            retry_after = 60
        else:
            available_tokens = limiter.available_tokens
            retry_after = max(
                1,
                math.ceil(max(0.0, 1.0 - available_tokens) / policy.rate),
            )

        return False, retry_after


class APIServer:
    """FastAPI server wrapper to run in a background thread."""

    _AUTH_ROUTE_PATHS = frozenset({"/key", "/token"})
    _RATE_LIMIT_CONFIG: dict[str, RouteRateLimitPolicy] = {
        "auth": RouteRateLimitPolicy(
            rate=0.2,
            capacity=6,
            retry_guidance="Retry after the backoff window before attempting bootstrap or token issuance again.",
        ),
        "read": RouteRateLimitPolicy(
            rate=2.0,
            capacity=30,
            retry_guidance="Retry after the backoff window or reduce polling frequency for read-only endpoints.",
        ),
        "mutation": RouteRateLimitPolicy(
            rate=0.5,
            capacity=10,
            retry_guidance="Retry after the backoff window and avoid replaying repeated mutation requests in a tight loop.",
        ),
    }

    def __init__(self, host: str = "127.0.0.1", port: int = 8000, allow_expose: bool = False):
        self.host = host
        self.port = port
        self.allow_expose = allow_expose
        self._validate_bind_host()
        self._policy_limiter = RoutePolicyLimiter(self._RATE_LIMIT_CONFIG)
        self.app = self._create_app()
        self._thread: Optional[threading.Thread] = None

    def _normalize_policy_path(self, path: str) -> str:
        if path.startswith("/api"):
            normalized = path[4:]
            return normalized or "/"
        return path

    def _resolve_route_policy(self, method: str, path: str) -> str:
        normalized_path = self._normalize_policy_path(path)
        normalized_method = method.upper()

        if normalized_path in system_routes.PUBLIC_ROUTE_PATHS:
            return "public"

        if normalized_path in self._AUTH_ROUTE_PATHS:
            return "auth"

        if normalized_path in executor_routes.MUTATING_ROUTE_PATHS:
            return "mutation"

        if normalized_path in profiles_routes.MUTATING_ROUTE_PATHS:
            return "mutation"

        if normalized_path in system_routes.READ_ONLY_ROUTE_PATHS:
            return "read"

        if profiles_routes.is_read_only_route_path(normalized_path):
            return "read"

        if normalized_method == "GET":
            return "read"

        return "mutation"

    def _client_key(self, request: Request) -> str:
        if request.client and request.client.host:
            return request.client.host
        return "unknown"

    @staticmethod
    def _is_loopback_host(host: str) -> bool:
        """Return True when a host resolves to a local loopback address."""
        normalized_host = str(host).strip().lower()
        if normalized_host == "localhost":
            return True

        try:
            return ipaddress.ip_address(normalized_host).is_loopback
        except ValueError:
            return False

    @staticmethod
    def _build_origin(host: str, port: int) -> str:
        """Build a browser origin string for a host/port pair."""
        try:
            parsed = ipaddress.ip_address(host)
        except ValueError:
            parsed = None

        if parsed is not None and parsed.version == 6:
            return f"http://[{host}]:{port}"

        return f"http://{host}:{port}"

    def _default_allowed_origins(self) -> list[str]:
        """Return the safe default local origins for desktop API usage."""
        candidates = ["localhost", "127.0.0.1"]
        if self._is_loopback_host(self.host):
            candidates.insert(0, self.host)

        origins: list[str] = []
        for host in candidates:
            origin = self._build_origin(host, self.port)
            if origin not in origins:
                origins.append(origin)

        return origins

    def _is_allowed_origin(self, origin: str) -> bool:
        """Validate a configured CORS origin against the current exposure policy."""
        if origin == "*":
            return False

        parsed = urlparse(origin)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return False

        if "*" in parsed.hostname:
            return False

        if self.allow_expose:
            return True

        return self._is_loopback_host(parsed.hostname)

    def _allowed_cors_origins(self) -> list[str]:
        """Return validated CORS origins, falling back to safe local defaults."""
        configured_origins = os.getenv("LOOFI_CORS_ORIGINS", "").strip()
        if not configured_origins:
            return self._default_allowed_origins()

        allowed_origins: list[str] = []
        for origin in configured_origins.split(","):
            candidate = origin.strip().rstrip("/")
            if not candidate:
                continue
            if self._is_allowed_origin(candidate):
                if candidate not in allowed_origins:
                    allowed_origins.append(candidate)
            else:
                logger.warning("Ignoring unsafe CORS origin override: %s", candidate)

        return allowed_origins or self._default_allowed_origins()

    def _create_app(self) -> FastAPI:
        app = FastAPI(
            title="Loofi Web API",
            version=__version__,
            docs_url=None,
            redoc_url=None,
            openapi_url=None,
        )
        allowed_origins = self._allowed_cors_origins()
        app.add_middleware(CORSMiddleware, allow_origins=allowed_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

        @app.middleware("http")
        async def enforce_route_policy(request: Request, call_next):
            policy_bucket = self._resolve_route_policy(request.method, request.url.path)

            if policy_bucket != "public":
                allowed, retry_after = self._policy_limiter.allow(
                    policy_bucket,
                    self._client_key(request),
                )
                if not allowed:
                    guidance = self._RATE_LIMIT_CONFIG[policy_bucket].retry_guidance
                    return JSONResponse(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        content={
                            "detail": f"Too many {policy_bucket} requests. Retry after {retry_after} seconds. {guidance}",
                            "retry_after_seconds": retry_after,
                            "route_policy": policy_bucket,
                        },
                        headers={
                            "Retry-After": str(retry_after),
                            "X-Loofi-Route-Policy": policy_bucket,
                        },
                    )

            response = await call_next(request)
            response.headers.setdefault("X-Loofi-Route-Policy", policy_bucket)
            return response

        # API routes
        app.include_router(system_routes.router, prefix="/api")
        app.include_router(executor_routes.router, prefix="/api")
        app.include_router(profiles_routes.router, prefix="/api")

        def auth_storage_error_to_http(error: Exception) -> HTTPException:
            if isinstance(error, PermissionError):
                detail = "Stored API auth data has unsafe permissions"
            else:
                detail = "Stored API auth data is invalid"

            return HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=detail,
            )

        @app.post("/api/token")
        def issue_token(api_key: str = Form(...)):
            """Issue JWT token for valid API key (form-urlencoded)."""
            try:
                if AuthManager.bootstrap_pending():
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Bootstrap API key required before requesting tokens",
                    )

                token = AuthManager.issue_token(api_key)
                return {"access_token": token, "token_type": "bearer"}
            except HTTPException:
                raise
            except (RuntimeError, ValueError, OSError, PermissionError) as e:
                raise auth_storage_error_to_http(e)

        @app.post("/api/key")
        def generate_key(
            credentials: Optional[HTTPAuthorizationCredentials] = Depends(AuthManager.security),
        ):
            try:
                bootstrap_pending = AuthManager.bootstrap_pending()
            except (RuntimeError, ValueError, OSError, PermissionError) as e:
                raise auth_storage_error_to_http(e)

            if not bootstrap_pending:
                AuthManager.verify_bearer_token(credentials)

            try:
                api_key = AuthManager.generate_api_key()
            except (RuntimeError, ValueError, OSError, PermissionError) as e:
                raise auth_storage_error_to_http(e)

            return {"api_key": api_key}

        # Static file serving
        web_dir = Path(__file__).parent.parent / "web"
        if web_dir.exists():
            app.mount("/assets", StaticFiles(directory=str(web_dir / "assets")), name="assets")

            @app.get("/")
            def serve_index():
                return FileResponse(str(web_dir / "index.html"))

        return app

    def start(self) -> None:
        """Start the API server in a daemon thread."""
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        uvicorn.run(self.app, host=self.host, port=self.port, log_level="info")

    def _validate_bind_host(self) -> None:
        """Refuse non-loopback binds unless explicitly allowed."""
        normalized_host = str(self.host).strip().lower()

        if normalized_host == "localhost":
            return

        try:
            parsed_host = ipaddress.ip_address(normalized_host)
        except ValueError:
            parsed_host = None

        if parsed_host is not None and parsed_host.is_loopback:
            return

        if self.allow_expose:
            return

        raise ValueError(
            "Refusing to bind Loofi Web API to non-loopback host "
            f"'{self.host}' without --unsafe-expose."
        )
