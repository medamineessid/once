#!/usr/bin/env bash
set -e

EXIT_CODE=0

run_check() {
    local name="$1"
    shift
    echo "=== $name ==="
    if "$@"; then
        echo "PASS: $name"
        return 0
    else
        echo "FAIL: $name"
        EXIT_CODE=1
        return 1
    fi
}

export QT_QPA_PLATFORM=offscreen
PYTHON="./.venv/Scripts/python.exe"
RUFF="./.venv/Scripts/ruff.exe"

if [ ! -f "$PYTHON" ]; then
    echo "FAIL: Virtual environment not found at $PYTHON"
    exit 1
fi

run_check "git branch --show-current" git branch --show-current || true
run_check "git status --short" git status --short || true
run_check "pytest" $PYTHON -m pytest -q || true
run_check "ruff check" $RUFF check . || true
run_check "ruff format --check" $RUFF format --check . || true
run_check "app.py --smoke-test" $PYTHON app.py --smoke-test || true
run_check "log numstat check" bash -c 'NUMSTAT=$(git diff --numstat origin/main...HEAD -- docs/ai_engineering_log.md 2>&1); echo "$NUMSTAT"; if echo "$NUMSTAT" | grep -q $'"'"'\t'"'"'; then PARTS=(${NUMSTAT//$'"'"'\t'"'"'/ }); if [ "${PARTS[0]}" != "0" ]; then exit 1; fi; fi' || true

echo ""
echo "=== SUMMARY ==="
if [ $EXIT_CODE -eq 0 ]; then
    echo "ALL CHECKS PASSED"
else
    echo "SOME CHECKS FAILED"
fi
exit $EXIT_CODE
