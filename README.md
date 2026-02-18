# idf.py flashless

## The Pain

If your firmware serves a web UI, the usual loop is slow:

1. Build and flash.
2. Establish network connection.
3. Open the device UI.
4. Click around.
5. Change frontend code.
6. Repeat.

Most time is spent waiting for flash + reboot instead of validating UI behavior.

## The Solution

`flashless` adds `idf.py flashless` so you can preview the same frontend routes/assets without flashing.
It keeps parity checks via a manifest and optional strict validation.

## Install

From registry:

```bash
idf.py add-dependency "matterizelabs/flashless^1.0.5"
idf.py reconfigure
```

From Git:

```bash
idf.py add-dependency --git https://github.com/matterizelabs/esp-flashless-ui.git --git-ref v1.0.5 flashless
idf.py reconfigure
```

## Run

```bash
idf.py flashless
```

Default behavior:

1. Runs preflight `idf.py build`.
2. Loads `flashless.manifest.json` (or `web/flashless.manifest.json`).
3. If no manifest exists, tries auto-manifest generation.
4. Starts preview server on `http://127.0.0.1:8787/`.
5. Enables live reload for HTML pages when assets/fixtures change.
6. Opens browser automatically.

Stop with `Ctrl+C`.

## Demo

![idf.py flashless demo](docs/demo/esp-idf-frontend-without-flashing.gif)

## Example Manifest + Run + Report

`flashless.manifest.json`

```json
{
  "version": "1",
  "ui": {
    "basePath": "/",
    "assetRoot": "main",
    "entryFile": "index.html",
    "routes": ["/", "/settings", "/api-docs"],
    "spaFallback": true,
    "cachePolicy": {
      "maxAgeSeconds": 0,
      "etag": true,
      "gzip": false
    }
  },
  "api": {
    "mode": "mock",
    "fixturesDir": "ui-fixtures",
    "map": [
      {
        "method": "GET",
        "path": "/api/status",
        "fixture": "status.json",
        "status": 200,
        "headers": {
          "Content-Type": "application/json"
        }
      }
    ]
  },
  "validation": {
    "requiredFiles": ["index.html", "app.js", "styles.css"],
    "disallowExtraRoutes": false
  }
}
```

Run:

```bash
idf.py flashless --manifest flashless.manifest.json --no-open --request-log errors
```

Typical output:

```text
Executing action: flashless
[flashless] Manifest: /path/to/project/flashless.manifest.json
[flashless] Report:   /path/to/project/build/flashless/report.json
[flashless] Preview running at http://127.0.0.1:8787/
[flashless] Press Ctrl+C to stop.
```

Example `build/flashless/report.json`:

```json
{
  "manifest": {
    "path": "/path/to/project/flashless.manifest.json",
    "sha256": "<manifest_sha256>",
    "version": "1"
  },
  "server": {
    "host": "127.0.0.1",
    "port": 8787,
    "mode": "mock",
    "basePath": "/",
    "assetRoot": "/path/to/project/main"
  },
  "validation": {
    "missingRequiredFiles": [],
    "missingFixtures": [],
    "unresolvedRoutes": [],
    "hasErrors": false
  },
  "routes": ["/", "/settings", "/api-docs"],
  "api": {
    "mode": "mock",
    "fixturesDir": "/path/to/project/ui-fixtures",
    "mappingCount": 1
  }
}
```

## Flags

```bash
idf.py flashless --help
```

Common options:

- `--manifest <path>`
- `--bind-port <port>`
- `--host <addr>`
- `--request-log <all|errors|none>`
- `--no-open`
- `--mode mock`
- `--fixtures <path>`
- `--no-build`
- `--strict`
- `--no-auto`
- `--allow-absolute-paths`
- `--no-live-reload`

## Notes

- Auto-manifest works best when frontend assets are discoverable from embedded files and include an `index.html` entry.
- If auto mode cannot infer your UI, pass an explicit manifest with `--manifest`.
- For safety, manifest `ui.assetRoot` and `api.fixturesDir` must be project-relative by default; use `--allow-absolute-paths` only when you trust the manifest and intentionally need absolute roots.
- Live reload is enabled by default. Use `--no-live-reload` to disable browser auto-refresh.
