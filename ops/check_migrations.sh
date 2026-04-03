#!/usr/bin/env bash
# Migration chain validation script.
# Usage: bash ops/check_migrations.sh
#
# Checks:
#   1. alembic heads   — exactly one head (no divergent branches)
#   2. alembic upgrade head   — full chain applies cleanly
#   3. alembic downgrade base — full rollback succeeds
#   4. alembic upgrade head   — re-apply after rollback (idempotency)
#
# Requires: POSTGRES_* env vars set (or .env loaded).

set -euo pipefail

echo "=== Migration Check ==="

echo "[1/4] Checking for single head..."
HEADS=$(alembic heads 2>&1)
HEAD_COUNT=$(echo "$HEADS" | grep -c "(head)")
if [ "$HEAD_COUNT" -ne 1 ]; then
    echo "FAIL: Expected exactly 1 head, got $HEAD_COUNT"
    echo "$HEADS"
    exit 1
fi
echo "OK: Single head found"

echo "[2/4] Upgrading to head..."
alembic upgrade head
echo "OK: Upgrade to head succeeded"

echo "[3/4] Downgrading to base..."
alembic downgrade base
echo "OK: Downgrade to base succeeded"

echo "[4/4] Re-upgrading to head..."
alembic upgrade head
echo "OK: Re-upgrade succeeded"

echo ""
echo "=== All migration checks passed ==="
