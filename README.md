# flashless (ESP-IDF)

`flashless` adds a no-flash browser preview workflow for ESP-IDF web UIs.

## Goals

- Use `idf.py` workflow.
- Preview frontend assets and routes before flashing.
- Keep parity with firmware-shipped frontend behavior via manifest validation.

## Install

Add as a managed component:

```bash
idf.py add-dependency "acme/flashless^1.0.0"
idf.py reconfigure
```

## Run

```bash
idf.py flashless
```

Default behavior:

1. Runs preflight `idf.py build`.
2. Loads `flashless.manifest.json` (or `web/flashless.manifest.json`).
3. If no manifest exists, auto-generates one in `build/flashless/auto/` by inspecting embedded assets and HTTP URI handlers.
4. Starts preview server at `http://127.0.0.1:8787/`.
5. Opens browser automatically.

Stop with `Ctrl+C`.

## Options

```bash
idf.py flashless --manifest flashless.manifest.json --port 8787 --host 127.0.0.1 --strict
```

Flags:

- `--no-open`
- `--mode mock`
- `--fixtures <path>`
- `--no-build`
- `--strict`
- `--no-auto`

## Manifest

Start from:

- `examples/flashless.manifest.json`
- `python -m flashless.cli init-manifest`

Schema file:

- `schema/flashless.schema.json`

## Compatibility

- ESP-IDF v6+: command is exposed via component `idf_ext.py` extension.
- ESP-IDF v5.2+: fallback `flashless` CMake target exists, so `idf.py flashless` still works even where component extension auto-loading is unavailable.

## Generated report

Each run writes:

- `build/flashless/report.json`
