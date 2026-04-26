#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOOLS_ROOT="$(cd "$REPO_ROOT/../agents/agents" && pwd)"
PYTHON_BIN="$REPO_ROOT/venv/bin/python"

if [ -f "$TOOLS_ROOT/.venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source "$TOOLS_ROOT/.venv/bin/activate"
fi

declare -a TARGETS
for target in "$@"; do
  if [[ "$target" = /* ]]; then
    TARGETS+=("$target")
  else
    TARGETS+=("$REPO_ROOT/$target")
  fi
done

declare -a PYTHON_TARGETS
for target in "${TARGETS[@]}"; do
  if [ -d "$target" ] || [[ "$target" == *.py ]]; then
    PYTHON_TARGETS+=("${target#$REPO_ROOT/}")
  fi
done

OVERALL_EXIT=0

if [ "${#PYTHON_TARGETS[@]}" -eq 0 ]; then
  ruff_output=""
else
  ruff_output=$(cd "$REPO_ROOT" && ruff check --output-format=concise "${PYTHON_TARGETS[@]}" 2>&1) || true
fi

if [ -n "$ruff_output" ]; then
  while IFS= read -r line; do
    [[ "$line" =~ ^[[:space:]]*$ ]] && continue
    [[ "$line" = "All checks passed!" ]] && continue
    echo "RUFF  $line"
    OVERALL_EXIT=1
  done <<< "$ruff_output"
fi

if [ "${#PYTHON_TARGETS[@]}" -eq 0 ]; then
  echo "PYRIGHT  SKIP (no python targets)"
else
  pyright_output=$(cd "$REPO_ROOT" && pyright --pythonpath "$PYTHON_BIN" "${PYTHON_TARGETS[@]}" 2>&1) || true
  while IFS= read -r line; do
    [[ "$line" =~ ^[[:space:]]*$ ]] && continue
    [[ "$line" =~ ^(pyright|Loading|Found|No\ configuration|Using|Searching) ]] && continue
    [[ "$line" =~ ^[0-9]+[[:space:]]+(error|errors|warning|warnings) ]] && continue
    echo "PYRIGHT  $line"
    OVERALL_EXIT=1
  done <<< "$pyright_output"
fi

if [ "$OVERALL_EXIT" -eq 0 ]; then
  echo "LINT OK"
fi

exit "$OVERALL_EXIT"
