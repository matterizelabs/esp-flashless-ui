# flashless (ESP-IDF)

`flashless` adds a no-flash browser preview workflow for ESP-IDF web UIs.

## Goals

- Use `idf.py` workflow.
- Preview frontend assets and routes before flashing.
- Keep parity with firmware-shipped frontend behavior via manifest validation.

## Install

Add as a managed component from GitHub:

```bash
idf.py add-dependency --git https://github.com/matterizelabs/esp-flashless-ui.git --git-ref v1.0.0 flashless
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
idf.py flashless --manifest flashless.manifest.json --bind-port 8787 --host 127.0.0.1 --strict
```

Flags:

- `--bind-port <port>`
- `--no-open`
- `--mode mock`
- `--fixtures <path>`
- `--no-build`
- `--strict`
- `--no-auto`

## Help

Use the integrated ESP-IDF action help:

```bash
idf.py flashless --help
```

Use standalone component CLI help:

```bash
PYTHONPATH=tools python -m flashless.cli --help
PYTHONPATH=tools python -m flashless.cli run --help
```

## Manifest

Start from:

- `examples/flashless.manifest.json`
- `python -m flashless.cli init-manifest`

Schema file:

- `schema/flashless.schema.json`

## Compatibility

- ESP-IDF v6+: command is exposed via component `idf_ext.py` extension.
- ESP-IDF v5.2+: on first `idf.py reconfigure`, flashless auto-generates `${PROJECT_DIR}/idf_ext.py` (only if missing) to auto-load managed component actions, so `idf.py flashless --no-build` and other flags work without manual `IDF_EXTRA_ACTIONS_PATH`.
- If your project already has a custom `${PROJECT_DIR}/idf_ext.py`, flashless will not overwrite it. In that case, keep your file and load managed component extensions there.

## Generated report

Each run writes:

- `build/flashless/report.json`

## Project Policies

- Contributing guide: `CONTRIBUTING.md`
- Code of Conduct: `CODE_OF_CONDUCT.md`
- License: `LICENSE` (MIT)
