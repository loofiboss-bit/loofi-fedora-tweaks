"""Loofi Web API server (FastAPI + Uvicorn)."""

import os
import ipaddress
import threading
import time
from collections import defaultdict, deque
from typing import Optional
from urllib.parse import urlparse

import uvicorn
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from utils.auth import AuthManager

TOKEN_ATTEMPTS_PER_MINUTE = 5


def _is_loopback_host(host: str) -> bool:
    normalized = str(host).strip().lower()
    if normalized == "localhost":
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def _is_loopback_origin(origin: str) -> bool:
    try:
        parsed = urlparse(origin)
    except ValueError:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.hostname) and _is_loopback_host(str(parsed.hostname))


def _origin_for(host: str, port: int) -> str:
    rendered_host = f"[{host}]" if ":" in host and not host.startswith("[") else host
    return f"http://{rendered_host}:{port}"


def _load_router(module_name: str):
    import importlib
    import sys

    try:
        mod = importlib.import_module(module_name)
    except (ImportError, AttributeError):
        mod = None

    r = getattr(mod, "router", None) if mod is not None else None
    if r is None or not getattr(r, "routes", None):
        for name, m in list(sys.modules.items()):
            if name.endswith(module_name) and getattr(m, "router", None) and getattr(m.router, "routes", None):
                r = m.router
                break

    if r is None and mod is not None:
        try:
            mod = importlib.reload(mod)
            r = getattr(mod, "router", None)
        except (ImportError, AttributeError):
            pass

    return r


class TokenRateLimiter:
    """Small in-memory throttle for the loopback token endpoint."""

    def __init__(self, limit: int = TOKEN_ATTEMPTS_PER_MINUTE, window_seconds: int = 60):
        self.limit = max(1, limit)
        self.window_seconds = max(1, window_seconds)
        self._attempts: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, identity: str, *, now: float | None = None) -> bool:
        timestamp = time.monotonic() if now is None else now
        with self._lock:
            attempts = self._attempts[identity]
            while attempts and timestamp - attempts[0] >= self.window_seconds:
                attempts.popleft()
            if len(attempts) >= self.limit:
                return False
            attempts.append(timestamp)
            return True


class APIServer:
    """FastAPI server wrapper to run in a background thread."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8000):
        if not _is_loopback_host(host):
            raise ValueError("Loofi Web API is loopback-only; use localhost, 127.0.0.1, or ::1.")
        self.host = host
        self.port = port
        self._token_limiter = TokenRateLimiter()
        self.app = self._create_app()
        self._thread: Optional[threading.Thread] = None

    def _create_app(self) -> FastAPI:
        from version import __version__

        app = FastAPI(title="Loofi Web API", version=__version__)
        configured_origins = os.getenv("LOOFI_CORS_ORIGINS", "").strip()
        default_origins = [
            _origin_for(self.host, self.port),
            "http://localhost:8000",
            "http://127.0.0.1:8000",
        ]
        requested_origins = [origin.strip() for origin in configured_origins.split(",") if origin.strip()]
        if any(not _is_loopback_origin(origin) for origin in requested_origins):
            raise ValueError("LOOFI_CORS_ORIGINS may contain loopback origins only.")
        allowed_origins = requested_origins or default_origins
        app.add_middleware(CORSMiddleware, allow_origins=allowed_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

        # API routes
        for mod_name in ("api.routes.system", "api.routes.profiles", "api.routes.action_center"):
            r = _load_router(mod_name)
            if r is not None:
                app.include_router(r)

        @app.post("/api/token")
        def issue_token(request: Request, api_key: str = Form(...)):
            """Issue JWT token for valid API key (form-urlencoded)."""
            identity = request.client.host if request.client else "loopback"
            if not self._token_limiter.allow(identity):
                raise HTTPException(status_code=429, detail="Too many token attempts. Try again later.")
            try:
                token = AuthManager.issue_token(api_key)
                return {"access_token": token, "token_type": "bearer"}
            except (RuntimeError, ValueError, OSError) as e:
                raise HTTPException(status_code=401, detail=str(e))

        return app

    def start(self) -> None:
        """Start the API server in a daemon thread."""
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        uvicorn.run(self.app, host=self.host, port=self.port, log_level="info")
