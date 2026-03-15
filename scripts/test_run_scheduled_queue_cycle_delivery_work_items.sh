#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_DIR="$(mktemp -d)"
REPORT_PATH="$ROOT_DIR/runtime-artifacts/scheduler-cycle/test-wave20-delivery-report.json"
WORK_ITEM_ROOT="$ROOT_DIR/runtime-artifacts/messaging/scheduled-delivery-work-items"
PAYLOAD_PATH="$WORK_ITEM_ROOT/test-wave20-operator-payload.json"
WORK_ITEM_PATH="$WORK_ITEM_ROOT/test-wave20-operator-work-item.json"
QUEUE_PATH="$TMP_DIR/runtime-scheduler-queue.delivery.json"
IDEMPOTENCY_PATH="$TMP_DIR/idempotency.json"
TRANSITION_LOG="$TMP_DIR/transition.ndjson"
PROFILES_CONFIG="$TMP_DIR/local-operator-channel-profiles.json"

trap 'rm -rf "$TMP_DIR" "$REPORT_PATH" "$ROOT_DIR/runtime-artifacts/scheduler-cycle/test-wave20-delivery-report-delivery-cycle.json" "$PAYLOAD_PATH" "$WORK_ITEM_PATH"' EXIT

cd "$ROOT_DIR"
mkdir -p "$WORK_ITEM_ROOT" "$(dirname "$REPORT_PATH")"

cat > "$PROFILES_CONFIG" <<JSON
{
  "config_version": 1,
  "profiles": {
    "slack_skill_cli": {
      "channel_kind": "slack_skill_cli",
      "transport_kind": "local_outbox",
      "outbox_root": "runtime-artifacts/test-scheduled-delivery/slack",
      "default_target_name": "monday-operator",
      "supports_threads": true
    }
  }
}
JSON

cat > "$PAYLOAD_PATH" <<'JSON'
{
  "messageClass": "status_update",
  "deliveryMode": "dry-run",
  "goalKey": "uap-goal-driven-autonomy-wave20",
  "body": "scheduled operator delivery",
  "runId": "run-wave20-t30",
  "taskId": "queue-wave20-t30",
  "target": {
    "channelKind": "slack_skill_cli",
    "deliveryTarget": "monday-operator",
    "threadRef": "thread-wave20"
  }
}
JSON

cat > "$WORK_ITEM_PATH" <<'JSON'
{
  "queue_item_id": "queue-wave20-t30",
  "goal_key": "uap-goal-driven-autonomy-wave20",
  "delivery_work_item_kind": "operator_message_delivery",
  "message_class": "status_update",
  "source_artifact_ref": "runtime-artifacts/messaging/scheduled-delivery-work-items/test-wave20-operator-payload.json",
  "delivery_idempotency_key": "wave20:t30:operator"
}
JSON

cat > "$QUEUE_PATH" <<'JSON'
{
  "queue_items": [
    {
      "queue_item_id": "queue-wave20-t30",
      "goal_key": "uap-goal-driven-autonomy-wave20",
      "schedule_key": "local-tick-5m",
      "state": "ready",
      "idempotency_key": "wave20:queue-wave20-t30",
      "priority_class": "standard",
      "retry_budget": {
        "max_attempts": 3,
        "backoff_profile": "exponential"
      },
      "retry_budget_remaining": 3,
      "attempt_count": 0,
      "dependency_keys": [],
      "escalation_policy_ref": "planningops/contracts/escalation-gate-contract.md",
      "completion_policy_ref": "planningops/contracts/goal-completion-contract.md",
      "target_repo": "rather-not-work-on/monday",
      "work_payload_ref": "runtime-artifacts/messaging/scheduled-delivery-work-items/test-wave20-operator-work-item.json"
    }
  ],
  "completed_queue_item_ids": []
}
JSON

python3 scripts/run_scheduled_queue_cycle.py \
  --queue "$QUEUE_PATH" \
  --profiles-config "$PROFILES_CONFIG" \
  --run-id test-wave20-delivery-report \
  --idempotency "$IDEMPOTENCY_PATH" \
  --report "$REPORT_PATH" \
  --transition-log "$TRANSITION_LOG"

python3 scripts/validate_runtime_evidence.py \
  --kind scheduler \
  --report "$REPORT_PATH" \
  --output "$TMP_DIR/runtime-scheduler-delivery-validation.json"

python3 - "$REPORT_PATH" <<'PY'
import json
import sys
from pathlib import Path

doc = json.loads(Path(sys.argv[1]).read_text())
assert doc["verdict"] == "pass", doc
assert doc["reason_code"] == "ok", doc
assert doc["delivery_cycle_required"] is True, doc
assert doc["selected_delivery_entrypoint"] == "scripts/run_operator_message_delivery_cycle.py", doc
assert doc["delivery_cycle_report_ref"] == "runtime-artifacts/scheduler-cycle/test-wave20-delivery-report-delivery-cycle.json", doc
assert doc["handoff_required"] is False, doc
assert doc["worker_outcome_handoff_ref"] == "-", doc
assert doc["dequeued_count"] == 1, doc
PY

python3 - "$ROOT_DIR/runtime-artifacts/scheduler-cycle/test-wave20-delivery-report-delivery-cycle.json" <<'PY'
import json
import sys
from pathlib import Path

doc = json.loads(Path(sys.argv[1]).read_text())
assert doc["entrypoint_script"] == "run_operator_message_delivery_cycle.py", doc
assert doc["cycle_status"] == "dry_run", doc
assert doc["verdict"] == "pass", doc
PY

echo "scheduled queue cycle delivery work items test passed"
