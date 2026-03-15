#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

cd "$ROOT_DIR"

PLANNINGOPS_DIR="$TMP_DIR/platform-planningops"
QUEUE_DIR="$PLANNINGOPS_DIR/runtime-artifacts/scheduler"
DB_PATH="$TMP_DIR/runtime-queue.sqlite3"
PACKET_PATH="$TMP_DIR/admission-packet.json"
ADMISSION_REPORT="$TMP_DIR/admission-report.json"
REPORT_PATH="$TMP_DIR/run-report-store-only.json"
IDEMPOTENCY_PATH="$TMP_DIR/idempotency.json"
TRANSITION_LOG="$TMP_DIR/scheduled-cycle-store-only.ndjson"
HANDOFF_PATH="$TMP_DIR/worker-outcome-handoff.json"
SELECTION_PATH="$TMP_DIR/worker-outcome-selection.json"
OUTCOME_ROOT="$TMP_DIR/runtime-artifacts/worker-outcome"
OUTCOME_PATH="$OUTCOME_ROOT/test-scheduled-cycle-store-only-1.json"

mkdir -p "$QUEUE_DIR" "$OUTCOME_ROOT"
cp fixtures/runtime-scheduler-queue.sample.json "$QUEUE_DIR/queue-seed.json"

cat > "$PACKET_PATH" <<'JSON'
{
  "admission_version": 1,
  "generated_at_utc": "2026-03-15T00:00:00Z",
  "admission_contract_ref": "planningops/contracts/scheduled-queue-admission-handoff-contract.md",
  "source_repo": "rather-not-work-on/platform-planningops",
  "goal_key": "uap-goal-driven-autonomy-wave4",
  "schedule_key": "local-tick-5m",
  "queue_seed_ref": "runtime-artifacts/scheduler/queue-seed.json",
  "seed_format": "runtime_scheduler_queue_items_json",
  "seed_item_count": 2,
  "verdict": "pass"
}
JSON

cat > "$OUTCOME_PATH" <<'JSON'
{
  "transition_id": "wave14-outcome-001",
  "queue_item_id": "queue-wave4-001",
  "goal_key": "uap-goal-driven-autonomy-wave4",
  "schedule_key": "local-tick-5m",
  "lease_owner": "monday-test-worker",
  "worker_run_id": "test-scheduled-cycle-store-only-1",
  "state_from": "leased",
  "state_to": "completed",
  "transition_reason": "worker.completed",
  "occurred_at_utc": "2026-03-15T00:05:00Z",
  "attempt_count": 1,
  "retry_budget_remaining": 2,
  "completion_evidence_ref": "runtime-artifacts/worker-outcome/test-scheduled-cycle-store-only-1.json"
}
JSON

python3 scripts/admit_scheduled_queue_packet.py \
  --packet "$PACKET_PATH" \
  --planningops-repo-dir "$PLANNINGOPS_DIR" \
  --queue-db "$DB_PATH" \
  --replace-existing \
  --output "$ADMISSION_REPORT"

python3 scripts/run_scheduled_queue_cycle.py \
  --queue-db "$DB_PATH" \
  --worker-outcome-root "$OUTCOME_ROOT" \
  --worker-outcome-selection-output "$SELECTION_PATH" \
  --worker-outcome-handoff-output "$HANDOFF_PATH" \
  --lease-schema ../platform-contracts/schemas/runtime-scheduler-lease-lifecycle.schema.json \
  --lease-owner monday-test-worker \
  --lease-duration-seconds 180 \
  --run-id test-scheduled-cycle-store-only-1 \
  --idempotency "$IDEMPOTENCY_PATH" \
  --report "$REPORT_PATH" \
  --transition-log "$TRANSITION_LOG"

python3 scripts/validate_runtime_evidence.py \
  --kind scheduler \
  --report "$REPORT_PATH" \
  --output "$TMP_DIR/runtime-scheduler-store-only-validation.json"

python3 - "$REPORT_PATH" "$HANDOFF_PATH" "$SELECTION_PATH" <<'PY'
import json
import sys
from pathlib import Path

report = json.loads(Path(sys.argv[1]).read_text())
handoff = json.loads(Path(sys.argv[2]).read_text())
selection = json.loads(Path(sys.argv[3]).read_text())

if report["dequeued_count"] != 1:
    raise SystemExit(f"expected dequeued_count=1, got {report['dequeued_count']}")
if report["handoff_required"] is not True:
    raise SystemExit("expected handoff_required=true")
if report["worker_outcome_handoff_ref"] == "-":
    raise SystemExit("expected worker_outcome_handoff_ref to be populated")
if handoff["queue_item_id"] != "queue-wave4-001":
    raise SystemExit(f"unexpected handoff queue_item_id: {handoff['queue_item_id']}")
if selection["selected"] is not True:
    raise SystemExit("expected selected worker outcome")
PY

echo "scheduled queue cycle store-only test passed"
