# Contributing

Thanks for contributing to `flashless`.

## Before You Start

- Search existing issues/PRs before opening a new one.
- Keep changes focused and small.
- For behavior changes, include tests or explain why tests are not needed.
- Prefer project-relative manifest paths; absolute roots require explicit `--allow-absolute-paths` opt-in.

## Development Setup

```bash
source ~/.espressif/versions/esp-idf/v5.5.2/export.sh
```

## Local Validation

Run these checks before opening a PR:

```bash
python -m py_compile idf_ext.py tools/flashless/*.py tests/*.py
python -m unittest discover -s tests -v
```

## Pull Request Guidelines

- Write clear commit messages.
- Describe what changed and why.
- Link related issues.
- Update docs when flags, behavior, or workflow changes.

## Reporting Issues

When filing a bug, include:

- ESP-IDF version
- Command used (`idf.py flashless ...`)
- Expected behavior
- Actual behavior and logs
