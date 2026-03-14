#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

cd "$ROOT_DIR"

DB_PATH="$TMP_DIR/runtime-queue.sqlite3"
REPORT_PATH="$TMP_DIR/run-report-store.json"
IDEMPOTENCY_PATH="$TMP_DIR/idempotency.json"
TRANSITION_LOG="$TMP_DIR/scheduled-cycle-store.ndjson"

python3 scripts/run_scheduled_queue_cycle.py \
  --queue fixtures/runtime-scheduler-queue.sample.json \
  --queue-db "$DB_PATH" \
  --lease-schema ../platform-contracts/schemas/runtime-scheduler-lease-lifecycle.schema.json \
  --lease-owner monday-test-worker \
  --lease-duration-seconds 180 \
  --db-seed-mode replace \
  --run-id test-scheduled-cycle-store-1 \
  --idempotency "$IDEMPOTENCY_PATH" \
  --report "$REPORT_PATH" \
  --transition-log "$TRANSITION_LOG"

python3 scripts/validate_runtime_evidence.py \
  --kind scheduler \
  --report "$REPORT_PATH" \
  --output "$TMP_DIR/runtime-scheduler-store-validation.json"

python3 - "$REPORT_PATH" "$DB_PATH" <<'PY'
import json
import sqlite3
import sys
from pathlib import Path

report = json.loads(Path(sys.argv[1]).read_text())
if report["reason_code"] != "blocked_dependencies":
    raise SystemExit(f"expected blocked_dependencies, got {report['reason_code']}")
if report["dequeued_count"] != 1:
    raise SystemExit(f"expected dequeued_count=1, got {report['dequeued_count']}")
if report["blocked_count"] != 1:
    raise SystemExit(f"expected blocked_count=1, got {report['blocked_count']}")

conn = sqlite3.connect(sys.argv[2])
conn.row_factory = sqlite3.Row
rows = {
    row["queue_item_id"]: dict(row)
    for row in conn.execute(
        """
        SELECT queue_item_id, state, lease_owner, lease_expires_at_utc,
               blocked_reason, attempt_count, retry_budget_remaining
        FROM queue_items
        ORDER BY queue_item_id
        """
    ).fetchall()
}
transition_count = conn.execute("SELECT COUNT(*) AS count FROM queue_transitions").fetchone()["count"]
conn.close()

first = rows["queue-wave4-001"]
second = rows["queue-wave4-002"]

if first["state"] != "leased":
    raise SystemExit(f"expected queue-wave4-001 leased, got {first['state']}")
if first["lease_owner"] != "monday-test-worker":
    raise SystemExit(f"expected queue-wave4-001 lease_owner=monday-test-worker, got {first['lease_owner']}")
if not first["lease_expires_at_utc"]:
    raise SystemExit("expected queue-wave4-001 lease_expiry to be populated")
if first["attempt_count"] != 1:
    raise SystemExit(f"expected queue-wave4-001 attempt_count=1, got {first['attempt_count']}")
if second["state"] != "blocked":
    raise SystemExit(f"expected queue-wave4-002 blocked, got {second['state']}")
if second["blocked_reason"] != "dependency.unresolved":
    raise SystemExit(
        f"expected queue-wave4-002 blocked_reason=dependency.unresolved, got {second['blocked_reason']}"
    )
if transition_count != 2:
    raise SystemExit(f"expected 2 lease transitions, got {transition_count}")
PY

echo "scheduled queue cycle store test passed"
