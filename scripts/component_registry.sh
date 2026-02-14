#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  scripts/component_registry.sh <check|pack|dry-run|upload> --name <component_name> [options]

Options:
  --name <name>                 Component name (required)
  --namespace <namespace>       Registry namespace (used for dry-run/upload)
  --version <version>           Override version (or use "git" when tagged)
  --project-dir <dir>           Component root (default: repo root)
  --dest-dir <dir>              Archive output directory
  --profile <profile>           Component-manager profile (default: default)
  --repository <url>            Override repository URL for registry metadata
  --repository-path <path>      Path to component inside repository
  --commit-sha <sha>            Override commit SHA metadata
  -h | --help                   Show this help

Examples:
  scripts/component_registry.sh check --name flashless
  scripts/component_registry.sh pack --name flashless --dest-dir dist
  scripts/component_registry.sh dry-run --name flashless --namespace myns
  scripts/component_registry.sh upload --name flashless --namespace myns
USAGE
}

if [[ $# -lt 1 ]]; then
  usage
  exit 2
fi

ACTION="$1"
shift

NAME=""
NAMESPACE=""
VERSION=""
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST_DIR=""
PROFILE="default"
REPOSITORY=""
REPOSITORY_PATH=""
COMMIT_SHA=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --name)
      NAME="$2"
      shift 2
      ;;
    --namespace)
      NAMESPACE="$2"
      shift 2
      ;;
    --version)
      VERSION="$2"
      shift 2
      ;;
    --project-dir)
      PROJECT_DIR="$2"
      shift 2
      ;;
    --dest-dir)
      DEST_DIR="$2"
      shift 2
      ;;
    --profile)
      PROFILE="$2"
      shift 2
      ;;
    --repository)
      REPOSITORY="$2"
      shift 2
      ;;
    --repository-path)
      REPOSITORY_PATH="$2"
      shift 2
      ;;
    --commit-sha)
      COMMIT_SHA="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 2
      ;;
  esac
done

if [[ -z "$NAME" ]]; then
  echo "--name is required" >&2
  exit 2
fi

if ! command -v compote >/dev/null 2>&1; then
  echo "compote not found. Source ESP-IDF export first, e.g.:" >&2
  echo "  source \$IDF_PATH/export.sh" >&2
  exit 127
fi

COMMON_ARGS=(
  --project-dir "$PROJECT_DIR"
  --name "$NAME"
)

if [[ -n "$VERSION" ]]; then
  COMMON_ARGS+=(--version "$VERSION")
fi
if [[ -n "$DEST_DIR" ]]; then
  COMMON_ARGS+=(--dest-dir "$DEST_DIR")
fi
if [[ -n "$REPOSITORY" ]]; then
  COMMON_ARGS+=(--repository "$REPOSITORY")
fi
if [[ -n "$REPOSITORY_PATH" ]]; then
  COMMON_ARGS+=(--repository-path "$REPOSITORY_PATH")
fi
if [[ -n "$COMMIT_SHA" ]]; then
  COMMON_ARGS+=(--commit-sha "$COMMIT_SHA")
fi

UPLOAD_ARGS=(--profile "$PROFILE")
if [[ -n "$NAMESPACE" ]]; then
  UPLOAD_ARGS+=(--namespace "$NAMESPACE")
fi

case "$ACTION" in
  check)
    echo "[registry] Running local checks..."
    (cd "$PROJECT_DIR" && python -m py_compile idf_ext.py tools/flashless/*.py tests/*.py)
    (cd "$PROJECT_DIR" && python -m unittest discover -s tests -v)
    echo "[registry] Packing component archive..."
    compote component pack "${COMMON_ARGS[@]}"
    ;;
  pack)
    compote component pack "${COMMON_ARGS[@]}"
    ;;
  dry-run)
    compote component upload "${COMMON_ARGS[@]}" "${UPLOAD_ARGS[@]}" --dry-run
    ;;
  upload)
    compote component upload "${COMMON_ARGS[@]}" "${UPLOAD_ARGS[@]}"
    ;;
  *)
    echo "Unknown action: $ACTION" >&2
    usage
    exit 2
    ;;
esac
