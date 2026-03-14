#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

cd "$ROOT_DIR"

DB_PATH="$TMP_DIR/runtime-queue.sqlite3"

python3 scripts/runtime_queue_store.py init \
  --db "$DB_PATH" \
  --output "$TMP_DIR/init-report.json"

python3 scripts/runtime_queue_store.py seed \
  --db "$DB_PATH" \
  --queue fixtures/runtime-scheduler-queue.sample.json \
  --output "$TMP_DIR/seed-report.json"

cat > "$TMP_DIR/lease-transition.json" <<'JSON'
{
  "transition_id": "wave6-lease-001",
  "queue_item_id": "queue-wave4-001",
  "goal_key": "uap-goal-driven-autonomy-wave6",
  "schedule_key": "local-tick-5m",
  "lease_owner": "monday-local-worker",
  "lease_token": "lease-wave6-001",
  "state_from": "ready",
  "state_to": "leased",
  "transition_reason": "scheduler.dequeue",
  "occurred_at_utc": "2026-03-14T08:00:00Z",
  "lease_expires_at_utc": "2026-03-14T08:05:00Z",
  "heartbeat_at_utc": "2026-03-14T08:01:00Z",
  "attempt_count": 1,
  "retry_budget_remaining": 2,
  "worker_run_id": "wave6-run-001"
}
JSON

python3 scripts/runtime_queue_store.py record-transition \
  --db "$DB_PATH" \
  --transition-json "$TMP_DIR/lease-transition.json" \
  --output "$TMP_DIR/lease-transition-report.json"

python3 scripts/record_queue_worker_outcome.py \
  --db "$DB_PATH" \
  --outcome-json fixtures/runtime-queue-worker-outcome.completed.sample.json \
  --worker-outcome-schema ../platform-contracts/schemas/runtime-queue-worker-outcome.schema.json \
  --output "$TMP_DIR/worker-outcome-report.json"

python3 - "$TMP_DIR/worker-outcome-report.json" "$DB_PATH" <<'PY'
import json
import sqlite3
import sys
from pathlib import Path

report = json.loads(Path(sys.argv[1]).read_text())
if report["state_to"] != "completed":
    raise SystemExit(f"expected completed outcome, got {report['state_to']}")
if report["queue_item"]["state"] != "completed":
    raise SystemExit(f"expected queue item state completed, got {report['queue_item']['state']}")
if report["queue_item"]["completion_evidence_ref"] != "runtime-artifacts/worker-outcome/wave6-run-001.json":
    raise SystemExit("expected completion evidence ref to be stored")
if report["queue_item"]["lease_expires_at_utc"] is not None:
    raise SystemExit("expected lease expiry to be cleared after completion")

conn = sqlite3.connect(sys.argv[2])
conn.row_factory = sqlite3.Row
transition_count = conn.execute("SELECT COUNT(*) AS count FROM queue_transitions").fetchone()["count"]
conn.close()

if transition_count != 2:
    raise SystemExit(f"expected 2 queue transitions, got {transition_count}")
PY

echo "record queue worker outcome CLI test passed"
