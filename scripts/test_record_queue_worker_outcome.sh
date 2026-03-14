#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

cd "$ROOT_DIR"

bash scripts/test_record_queue_worker_outcome_cli.sh

setup_leased_queue() {
  local db_path="$1"
  local lease_transition="$2"

  python3 scripts/runtime_queue_store.py init --db "$db_path" >/dev/null
  python3 scripts/runtime_queue_store.py seed \
    --db "$db_path" \
    --queue fixtures/runtime-scheduler-queue.sample.json >/dev/null

  cat > "$lease_transition" <<'JSON'
{
  "transition_id": "wave6-lease-shared",
  "queue_item_id": "queue-wave4-001",
  "goal_key": "uap-goal-driven-autonomy-wave6",
  "schedule_key": "local-tick-5m",
  "lease_owner": "monday-local-worker",
  "lease_token": "lease-wave6-shared",
  "state_from": "ready",
  "state_to": "leased",
  "transition_reason": "scheduler.dequeue",
  "occurred_at_utc": "2026-03-14T08:00:00Z",
  "lease_expires_at_utc": "2026-03-14T08:05:00Z",
  "heartbeat_at_utc": "2026-03-14T08:01:00Z",
  "attempt_count": 1,
  "retry_budget_remaining": 2,
  "worker_run_id": "wave6-run-shared"
}
JSON

  python3 scripts/runtime_queue_store.py record-transition \
    --db "$db_path" \
    --transition-json "$lease_transition" >/dev/null
}

DB_RETRY="$TMP_DIR/runtime-queue-retry.sqlite3"
LEASE_RETRY="$TMP_DIR/lease-retry.json"
setup_leased_queue "$DB_RETRY" "$LEASE_RETRY"

python3 scripts/record_queue_worker_outcome.py \
  --db "$DB_RETRY" \
  --outcome-json fixtures/runtime-queue-worker-outcome.retry-wait.sample.json \
  --worker-outcome-schema ../platform-contracts/schemas/runtime-queue-worker-outcome.schema.json \
  --output "$TMP_DIR/retry-outcome-report.json" >/dev/null

python3 scripts/run_scheduled_queue_cycle.py \
  --queue fixtures/runtime-scheduler-queue.sample.json \
  --queue-db "$DB_RETRY" \
  --lease-schema ../platform-contracts/schemas/runtime-scheduler-lease-lifecycle.schema.json \
  --run-id test-worker-outcome-retry-wait \
  --idempotency "$TMP_DIR/retry-idempotency.json" \
  --report "$TMP_DIR/retry-cycle-report.json" \
  --transition-log "$TMP_DIR/retry-cycle.ndjson" >/dev/null

python3 - "$TMP_DIR/retry-outcome-report.json" "$TMP_DIR/retry-cycle-report.json" "$DB_RETRY" <<'PY'
import json
import sqlite3
import sys
from pathlib import Path

retry_report = json.loads(Path(sys.argv[1]).read_text())
cycle_report = json.loads(Path(sys.argv[2]).read_text())
conn = sqlite3.connect(sys.argv[3])
conn.row_factory = sqlite3.Row
row = conn.execute(
    "SELECT state, retry_after_utc FROM queue_items WHERE queue_item_id = 'queue-wave4-001'"
).fetchone()
conn.close()

if retry_report["state_to"] != "retry_wait":
    raise SystemExit(f"expected retry_wait outcome, got {retry_report['state_to']}")
if row["state"] != "retry_wait":
    raise SystemExit(f"expected queue item retry_wait, got {row['state']}")
if not row["retry_after_utc"]:
    raise SystemExit("expected retry_after_utc to be persisted")
if any(entry["card_id"] == "queue-wave4-001" for entry in cycle_report["dequeued"]):
    raise SystemExit("retry_wait item should not dequeue before retry_after_utc")
PY

DB_DEAD="$TMP_DIR/runtime-queue-dead.sqlite3"
LEASE_DEAD="$TMP_DIR/lease-dead.json"
setup_leased_queue "$DB_DEAD" "$LEASE_DEAD"

python3 scripts/record_queue_worker_outcome.py \
  --db "$DB_DEAD" \
  --outcome-json fixtures/runtime-queue-worker-outcome.dead-letter.sample.json \
  --worker-outcome-schema ../platform-contracts/schemas/runtime-queue-worker-outcome.schema.json \
  --output "$TMP_DIR/dead-letter-outcome-report.json" >/dev/null

python3 - "$TMP_DIR/dead-letter-outcome-report.json" "$DB_DEAD" <<'PY'
import json
import sqlite3
import sys
from pathlib import Path

report = json.loads(Path(sys.argv[1]).read_text())
conn = sqlite3.connect(sys.argv[2])
conn.row_factory = sqlite3.Row
row = conn.execute(
    "SELECT state, dead_letter_reason, retry_after_utc FROM queue_items WHERE queue_item_id = 'queue-wave4-001'"
).fetchone()
transition_count = conn.execute("SELECT COUNT(*) AS count FROM queue_transitions").fetchone()["count"]
conn.close()

if report["state_to"] != "dead_letter":
    raise SystemExit(f"expected dead_letter outcome, got {report['state_to']}")
if row["state"] != "dead_letter":
    raise SystemExit(f"expected queue item dead_letter, got {row['state']}")
if row["dead_letter_reason"] != "retry_budget_exhausted":
    raise SystemExit(f"expected dead_letter_reason=retry_budget_exhausted, got {row['dead_letter_reason']}")
if row["retry_after_utc"] is not None:
    raise SystemExit("expected retry_after_utc cleared for dead_letter state")
if transition_count != 2:
    raise SystemExit(f"expected 2 queue transitions for dead_letter path, got {transition_count}")
PY

echo "record queue worker outcome lifecycle test passed"
