"""idf.py extension entrypoint for the flashless command."""

from __future__ import annotations

import sys
from pathlib import Path

try:
    import click
except Exception:  # pragma: no cover - click is available in ESP-IDF env
    click = None
try:
    from idf_py_actions.errors import FatalError
except Exception:  # pragma: no cover - fallback for local tests
    class FatalError(RuntimeError):
        """Compatibility wrapper when idf_py_actions is unavailable."""

_COMPONENT_DIR = Path(__file__).resolve().parent
_TOOLS_DIR = _COMPONENT_DIR / "tools"

if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

from flashless.command import FlashlessOptions, run_flashless  # noqa: E402


def _choice(values: list[str]):
    if click is None:
        return str
    return click.Choice(values, case_sensitive=False)


def action_extensions(base_actions, project_path):
    def flashless_callback(action, ctx, args, **kwargs):
        build_dir = getattr(args, "build_dir", "build")
        options = FlashlessOptions(
            manifest=kwargs.get("manifest"),
            port=kwargs.get("port", 8787),
            host=kwargs.get("host", "127.0.0.1"),
            open_browser=not kwargs.get("no_open", False),
            mode=kwargs.get("mode", "mock"),
            fixtures=kwargs.get("fixtures"),
            run_build=not kwargs.get("no_build", False),
            strict=kwargs.get("strict", False),
            auto=not kwargs.get("no_auto", False),
        )
        try:
            return run_flashless(project_path, build_dir, options)
        except Exception as exc:  # pragma: no cover - exercised in IDF runtime
            raise FatalError(str(exc)) from exc

    return {
        "global_options": [],
        "actions": {
            "flashless": {
                "callback": flashless_callback,
                "help": "Launch a no-flash browser preview for firmware web UI.",
                "options": [
                    {
                        "names": ["--manifest"],
                        "help": "Path to flashless manifest JSON.",
                        "type": str,
                    },
                    {
                        "names": ["--port"],
                        "help": "Preview server port.",
                        "type": int,
                        "default": 8787,
                    },
                    {
                        "names": ["--host"],
                        "help": "Preview server host bind address.",
                        "type": str,
                        "default": "127.0.0.1",
                    },
                    {
                        "names": ["--no-open"],
                        "help": "Do not open the browser automatically.",
                        "is_flag": True,
                        "default": False,
                    },
                    {
                        "names": ["--mode"],
                        "help": "API handling mode. v1 supports mock.",
                        "type": _choice(["mock", "proxy"]),
                        "default": "mock",
                    },
                    {
                        "names": ["--fixtures"],
                        "help": "Override fixtures directory.",
                        "type": str,
                    },
                    {
                        "names": ["--no-build"],
                        "help": "Skip preflight build step.",
                        "is_flag": True,
                        "default": False,
                    },
                    {
                        "names": ["--strict"],
                        "help": "Fail on parity mismatches (missing assets/fixtures/routes).",
                        "is_flag": True,
                        "default": False,
                    },
                    {
                        "names": ["--no-auto"],
                        "help": "Disable automatic manifest/fixture bootstrap when no manifest is present.",
                        "is_flag": True,
                        "default": False,
                    },
                ],
            }
        },
    }
