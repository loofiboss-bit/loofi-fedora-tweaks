import argparse
import logging
import os
import sys

# Ensure we can import from local modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from version import __version__

# Set up file logging so crashes are visible even when launched from desktop
LOG_DIR = os.path.expanduser("~/.local/share/loofi-fedora-tweaks")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "startup.log")

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
_log = logging.getLogger("loofi.main")


def _notify_error(title: str, message: str):
    """Send a desktop notification when the GUI can't start."""
    import subprocess as _sp

    try:
        _sp.Popen(
            [
                "notify-send",
                "--app-name=Loofi Fedora Tweaks",
                "--icon=dialog-error",
                title,
                message,
            ],
            stdout=_sp.DEVNULL,
            stderr=_sp.DEVNULL,
        )
    except FileNotFoundError:
        pass  # notify-send not installed, nothing we can do


def _check_pyqt6():
    """Pre-flight check for PyQt6 availability with a helpful message."""
    try:
        from PyQt6.QtWidgets import QApplication  # noqa: F401

        return True
    except ImportError as exc:
        msg = str(exc)
        if "libGL" in msg:
            from utils.install_hints import build_install_hint

            hint = f"PyQt6 cannot load because libGL is missing.\nFix:  {build_install_hint('mesa-libGL mesa-libEGL')}"
        elif "No module named" in msg:
            from utils.install_hints import build_install_hint

            hint = f"PyQt6 is not installed.\nFix:  {build_install_hint('python3-pyqt6')}"
        else:
            hint = f"PyQt6 import failed: {msg}"

        _log.critical("PyQt6 check failed: %s", hint)
        print(f"ERROR: {hint}", file=sys.stderr)
        _notify_error("Loofi Fedora Tweaks — Cannot Start", hint)
        return False


def _startup_theme_name() -> str:
    """Return the saved or system theme name for GUI startup."""
    try:
        from utils.settings import SettingsManager

        settings = SettingsManager.instance()
        if settings.get("follow_system_theme", False):
            return "system"
        else:
            theme = settings.get("theme", "dark")
    except (ImportError, KeyError, RuntimeError, OSError, ValueError, TypeError) as exc:
        _log.debug("Theme preference lookup failed, using dark theme: %s", exc)
        theme = "dark"
    return theme if theme in {"dark", "light", "highcontrast"} else "dark"


def _theme_file_for(name: str) -> str | None:
    """Return the shared structural QSS filename for GUI theme startup."""
    return "base.qss"


def _forwarded_cli_help(arguments: list[str]) -> list[str] | None:
    """Return CLI arguments when help belongs to the ``--cli`` surface."""
    positions = [
        arguments.index(flag)
        for flag in ("--cli", "-c")
        if flag in arguments
    ]
    if not positions:
        return None
    position = min(positions)
    forwarded = arguments[position + 1 :]
    return forwarded if any(item in {"--help", "-h"} for item in forwarded) else None


def main(argv: list[str] | None = None):
    """Main entry point with argument parsing."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    cli_help = _forwarded_cli_help(arguments)
    if cli_help is not None:
        from cli.main import main as cli_main

        return cli_main(cli_help)

    parser = argparse.ArgumentParser(
        prog="loofi-fedora-tweaks",
        description="System tweaks and maintenance for Fedora",
    )
    parser.add_argument(
        "--daemon",
        "-d",
        action="store_true",
        help="Run as background daemon for scheduled tasks",
    )
    parser.add_argument(
        "--cli",
        "-c",
        action="store_true",
        help="Run in command-line mode (pass remaining args to CLI)",
    )
    parser.add_argument("--web", action="store_true", help="Run headless Loofi Web API server")
    parser.add_argument("--version", "-v", action="version", version=f"%(prog)s {__version__}")

    args, remaining = parser.parse_known_args(arguments)

    if args.daemon:
        # Run in daemon mode
        try:
            from daemon.runtime import run_daemon
        except ImportError as exc:
            print(
                "ERROR: Daemon dependencies are missing. Install loofi-fedora-tweaks-daemon and retry.",
                file=sys.stderr,
            )
            _log.critical("Daemon dependency import failed: %s", exc, exc_info=True)
            sys.exit(1)

        run_daemon()
    elif args.web:
        try:
            from utils.api_server import APIServer
        except ImportError as exc:
            print(
                "ERROR: Web API dependencies are missing. Install loofi-fedora-tweaks-api and retry.",
                file=sys.stderr,
            )
            _log.critical("Web API dependency import failed: %s", exc, exc_info=True)
            sys.exit(1)

        api_host = os.getenv("LOOFI_API_HOST", "127.0.0.1")
        try:
            api_port = int(os.getenv("LOOFI_API_PORT", "8000"))
        except ValueError:
            _log.warning("Invalid LOOFI_API_PORT; falling back to 8000")
            api_port = 8000
        try:
            server = APIServer(host=api_host, port=api_port)
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            _log.error("Web API configuration rejected: %s", exc)
            sys.exit(2)
        server.start()
        _log.info("Loofi Web API started on %s:%s", server.host, server.port)
        try:
            while True:
                __import__("time").sleep(1)
        except KeyboardInterrupt:
            _log.info("Loofi Web API shutting down")
    elif args.cli:
        # Run CLI mode
        from cli.main import main as cli_main

        sys.exit(cli_main(remaining))
    else:
        # Run GUI
        _log.info("Starting Loofi Fedora Tweaks v%s (GUI)", __version__)

        if not _check_pyqt6():
            sys.exit(1)

        try:
            from PyQt6.QtWidgets import QApplication, QMessageBox
            from core.application_runtime import ApplicationRuntime
            from ui.main_window import MainWindow
            from utils.event_bus import EventBus
        except ImportError as exc:
            _log.critical("Failed to import GUI modules: %s", exc, exc_info=True)
            _notify_error("Loofi — Import Error", str(exc))
            sys.exit(1)

        try:
            app = QApplication(sys.argv)
            runtime = ApplicationRuntime()
            event_bus = EventBus()
            runtime.register(
                "event-bus",
                lambda remaining: event_bus.shutdown(timeout=remaining),
            )
            app.aboutToQuit.connect(runtime.shutdown)

            # Install centralized error handler (v29.0)
            from utils.error_handler import install_error_handler

            install_error_handler()

            # Always load structural styling; ThemeManager only changes palette tokens.
            theme_name = _startup_theme_name()
            from ui.design import ThemeManager

            ThemeManager().apply(app, theme_name)

            window = MainWindow(runtime=runtime)
            window.show()
            _log.info("MainWindow shown successfully")
            sys.exit(app.exec())

        except (OSError, RuntimeError, ValueError, ImportError, TypeError, AttributeError) as exc:
            _log.critical("GUI startup crashed: %s", exc, exc_info=True)
            # Try to show a Qt error dialog if QApplication exists
            try:
                if QApplication.instance():
                    QMessageBox.critical(
                        None,
                        "Loofi Fedora Tweaks — Startup Error",
                        f"The application failed to start:\n\n{exc}\n\nCheck the log at:\n{LOG_FILE}",
                    )
            except (RuntimeError, OSError, ValueError, TypeError, AttributeError) as e:
                _log.debug("Failed to show Qt error dialog: %s", e)
            _notify_error("Loofi — Startup Crash", str(exc))
            print(f"FATAL: {exc}", file=sys.stderr)
            print(f"Log file: {LOG_FILE}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
