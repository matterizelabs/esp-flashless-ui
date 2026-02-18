"""Standalone CLI entrypoint for flashless."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .command import FlashlessOptions, run_flashless
from .errors import FlashlessError

_TEMPLATE = {
    "version": "1",
    "ui": {
        "basePath": "/",
        "assetRoot": "web/dist",
        "entryFile": "index.html",
        "routes": ["/"],
        "spaFallback": True,
        "cachePolicy": {
            "maxAgeSeconds": 0,
            "etag": True,
            "gzip": False,
        },
    },
    "api": {
        "mode": "mock",
        "fixturesDir": "ui-fixtures",
        "map": [
            {
                "method": "GET",
                "path": "/api/health",
                "fixture": "health.json",
                "status": 200,
                "headers": {
                    "Content-Type": "application/json",
                },
            }
        ],
    },
    "validation": {
        "requiredFiles": ["index.html"],
        "disallowExtraRoutes": False,
    },
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="flashless local preview utility")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    run_parser = subparsers.add_parser("run", help="run the local preview server")
    run_parser.add_argument("--project-dir", required=True)
    run_parser.add_argument("--build-dir", default="build")
    run_parser.add_argument("--manifest")
    run_parser.add_argument("--bind-port", type=int, default=8787)
    run_parser.add_argument("--host", default="127.0.0.1")
    run_parser.add_argument(
        "--request-log", default="errors", choices=["all", "errors", "none"]
    )
    run_parser.add_argument("--no-open", action="store_true")
    run_parser.add_argument("--mode", default="mock", choices=["mock", "proxy"])
    run_parser.add_argument("--fixtures")
    run_parser.add_argument("--no-build", action="store_true")
    run_parser.add_argument("--strict", action="store_true")
    run_parser.add_argument("--no-auto", action="store_true")
    run_parser.add_argument("--allow-absolute-paths", action="store_true")
    run_parser.add_argument("--no-live-reload", action="store_true")

    init_parser = subparsers.add_parser(
        "init-manifest", help="write a manifest template"
    )
    init_parser.add_argument("--output", default="flashless.manifest.json")
    init_parser.add_argument("--force", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.subcommand == "run":
            options = FlashlessOptions(
                manifest=args.manifest,
                port=args.bind_port,
                host=args.host,
                request_log=args.request_log,
                open_browser=not args.no_open,
                mode=args.mode,
                fixtures=args.fixtures,
                run_build=not args.no_build,
                strict=args.strict,
                auto=not args.no_auto,
                allow_absolute_paths=args.allow_absolute_paths,
                live_reload=not args.no_live_reload,
            )
            return run_flashless(args.project_dir, args.build_dir, options)

        if args.subcommand == "init-manifest":
            output = Path(args.output)
            if output.exists() and not args.force:
                raise FlashlessError(
                    f"File exists: {output}. Use '--force' to overwrite or choose another '--output'."
                )
            output.write_text(json.dumps(_TEMPLATE, indent=2), encoding="utf-8")
            print(f"Wrote manifest template: {output}")
            return 0

        raise FlashlessError(f"Unsupported subcommand: {args.subcommand}")
    except FlashlessError as exc:
        print(f"flashless error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
