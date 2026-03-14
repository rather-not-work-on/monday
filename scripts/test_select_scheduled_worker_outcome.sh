#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

cd "$ROOT_DIR"

OUTCOME_ROOT="$TMP_DIR/runtime-artifacts/worker-outcome"
mkdir -p "$OUTCOME_ROOT"

cat > "$TMP_DIR/scheduled-report.json" <<'JSON'
{
  "run_id": "test-scheduled-selector-1",
  "dequeued_count": 1,
  "dequeued": [
    {
      "card_id": "queue-wave4-001",
      "issue_number": 324
    }
  ],
  "reason_code": "blocked_dependencies"
}
JSON

cat > "$OUTCOME_ROOT/matching-outcome.json" <<'JSON'
{
  "transition_id": "wave13-outcome-001",
  "queue_item_id": "queue-wave4-001",
  "goal_key": "uap-goal-driven-autonomy-wave4",
  "schedule_key": "local-tick-5m",
  "lease_owner": "monday-test-worker",
  "worker_run_id": "test-scheduled-selector-1",
  "state_from": "leased",
  "state_to": "completed",
  "transition_reason": "worker.completed",
  "occurred_at_utc": "2026-03-14T10:20:00Z",
  "attempt_count": 1,
  "retry_budget_remaining": 2,
  "completion_evidence_ref": "runtime-artifacts/worker-outcome/test-scheduled-selector-1.json"
}
JSON

cat > "$OUTCOME_ROOT/non-matching-outcome.json" <<'JSON'
{
  "transition_id": "wave13-outcome-002",
  "queue_item_id": "queue-wave4-001",
  "goal_key": "uap-goal-driven-autonomy-wave4",
  "schedule_key": "local-tick-5m",
  "lease_owner": "monday-test-worker",
  "worker_run_id": "test-scheduled-selector-other",
  "state_from": "leased",
  "state_to": "completed",
  "transition_reason": "worker.completed",
  "occurred_at_utc": "2026-03-14T10:21:00Z",
  "attempt_count": 1,
  "retry_budget_remaining": 2,
  "completion_evidence_ref": "runtime-artifacts/worker-outcome/test-scheduled-selector-other.json"
}
JSON

python3 scripts/select_scheduled_worker_outcome.py \
  --scheduled-report "$TMP_DIR/scheduled-report.json" \
  --queue fixtures/runtime-scheduler-queue.sample.json \
  --worker-outcome-root "$OUTCOME_ROOT" \
  --output "$TMP_DIR/selection-report.json"

python3 - "$TMP_DIR/selection-report.json" <<'PY'
import json
import sys
from pathlib import Path

report = json.loads(Path(sys.argv[1]).read_text())
expected = str((Path(sys.argv[1]).parent / "runtime-artifacts" / "worker-outcome" / "matching-outcome.json").resolve())
if report["verdict"] != "pass":
    raise SystemExit(f"expected verdict=pass, got {report['verdict']}")
if report["selected"] is not True:
    raise SystemExit(f"expected selected=true, got {report['selected']}")
if report["queue_item_id"] != "queue-wave4-001":
    raise SystemExit(f"unexpected queue_item_id: {report['queue_item_id']}")
if report["goal_key"] != "uap-goal-driven-autonomy-wave4":
    raise SystemExit(f"unexpected goal_key: {report['goal_key']}")
if report["schedule_key"] != "local-tick-5m":
    raise SystemExit(f"unexpected schedule_key: {report['schedule_key']}")
if report["source_worker_outcome_ref"] != expected:
    raise SystemExit(f"unexpected source_worker_outcome_ref: {report['source_worker_outcome_ref']} expected {expected}")
PY

echo "scheduled worker outcome selector test passed"
