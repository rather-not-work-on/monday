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

python3 scripts/runtime_queue_store.py list-ready \
  --db "$DB_PATH" \
  --output "$TMP_DIR/ready-before.json"

python3 - "$TMP_DIR/ready-before.json" <<'PY'
import json
import sys
from pathlib import Path

report = json.loads(Path(sys.argv[1]).read_text())
if report["ready_count"] != 2:
    raise SystemExit(f"expected 2 ready items before transition, got {report['ready_count']}")
PY

cat > "$TMP_DIR/transition.json" <<'JSON'
{
  "transition_id": "wave5-transition-001",
  "queue_item_id": "queue-wave4-001",
  "goal_key": "uap-goal-driven-autonomy-wave4",
  "schedule_key": "local-tick-5m",
  "lease_owner": "monday-local-worker-1",
  "lease_token": "lease-wave5-001",
  "state_from": "ready",
  "state_to": "leased",
  "transition_reason": "scheduler.dequeue",
  "occurred_at_utc": "2026-03-14T09:00:00Z",
  "lease_expires_at_utc": "2026-03-14T09:05:00Z",
  "heartbeat_at_utc": "2026-03-14T09:01:00Z",
  "attempt_count": 1,
  "retry_budget_remaining": 2,
  "worker_run_id": "wave5-run-001"
}
JSON

python3 scripts/runtime_queue_store.py record-transition \
  --db "$DB_PATH" \
  --transition-json "$TMP_DIR/transition.json" \
  --output "$TMP_DIR/transition-report.json"

python3 scripts/runtime_queue_store.py list-ready \
  --db "$DB_PATH" \
  --output "$TMP_DIR/ready-after.json"

python3 - "$TMP_DIR/transition-report.json" "$TMP_DIR/ready-after.json" <<'PY'
import json
import sys
from pathlib import Path

transition = json.loads(Path(sys.argv[1]).read_text())
ready = json.loads(Path(sys.argv[2]).read_text())

if transition["queue_item"]["state"] != "leased":
    raise SystemExit("expected transitioned queue item to be leased")
if ready["ready_count"] != 1:
    raise SystemExit(f"expected 1 ready item after lease, got {ready['ready_count']}")
if ready["queue_items"][0]["queue_item_id"] != "queue-wave4-002":
    raise SystemExit("expected only queue-wave4-002 to remain ready")
PY

echo "runtime queue store test passed"
