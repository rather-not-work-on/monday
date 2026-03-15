#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_DIR="$(mktemp -d)"
TEST_OUTBOX_ROOT="runtime-artifacts/test-operator-delivery-cycle"
trap 'rm -rf "$TMP_DIR" "$ROOT_DIR/$TEST_OUTBOX_ROOT" "$ROOT_DIR/runtime-artifacts/messaging/delivery-reports" "$ROOT_DIR/runtime-artifacts/messaging/delivery-cycles" "$ROOT_DIR/runtime-artifacts/messaging/dispatch-packets" "$ROOT_DIR/runtime-artifacts/messaging/dispatch-acks" "$ROOT_DIR/runtime-artifacts/messaging/dispatch-execution-packets" "$ROOT_DIR/runtime-artifacts/messaging/dispatch-receipts"' EXIT

cd "$ROOT_DIR"

profiles_config="$TMP_DIR/local-operator-channel-profiles.json"
payload="$TMP_DIR/operator-message.json"
cycle_report_one="$ROOT_DIR/runtime-artifacts/messaging/delivery-cycles/operator-message-wave18.json"
cycle_report_two="$ROOT_DIR/runtime-artifacts/messaging/delivery-cycles/operator-message-wave18-repeat.json"
cycle_report_dry_run="$ROOT_DIR/runtime-artifacts/messaging/delivery-cycles/operator-message-wave19-dry-run.json"

cat >"$profiles_config" <<JSON
{
  "config_version": 1,
  "profiles": {
    "slack_skill_cli": {
      "channel_kind": "slack_skill_cli",
      "transport_kind": "local_outbox",
      "outbox_root": "$TEST_OUTBOX_ROOT/slack",
      "default_target_name": "monday-operator",
      "supports_threads": true
    }
  }
}
JSON

cat >"$payload" <<'JSON'
{
  "messageClass": "decision_request",
  "deliveryMode": "apply",
  "goalKey": "uap-goal-driven-autonomy-wave18",
  "body": "operator delivery cycle",
  "runId": "run-wave18-r20",
  "taskId": "queue-wave18-r20",
  "target": {
    "channelKind": "slack_skill_cli",
    "threadRef": "thread-wave18-r20"
  }
}
JSON

python3 "$ROOT_DIR/scripts/run_operator_message_delivery_cycle.py" \
  --payload-file "$payload" \
  --profiles-config "$profiles_config" \
  --output "$cycle_report_one"

python3 - <<'PY' "$cycle_report_one" "$payload"
import json
import sys
from pathlib import Path

doc = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
payload_path = str(Path(sys.argv[2]).resolve())
assert doc["verdict"] == "pass", doc
assert doc["entrypoint_script"] == "run_operator_message_delivery_cycle.py", doc
assert doc["source_payload_ref"] == payload_path, doc
assert doc["goal_key"] == "uap-goal-driven-autonomy-wave18", doc
assert doc["message_class"] == "decision_request", doc
assert doc["channel_kind"] == "slack_skill_cli", doc
assert doc["cycle_status"] == "recorded", doc
for key in ["delivery_report_ref", "dispatch_packet_ref", "execution_packet_ref", "ack_checkpoint_ref", "dispatch_receipt_ref", "step_cycle_report_ref"]:
    assert Path(doc[key]).exists(), (key, doc)
PY

python3 "$ROOT_DIR/scripts/run_operator_message_delivery_cycle.py" \
  --payload-file "$payload" \
  --profiles-config "$profiles_config" \
  --output "$cycle_report_two"

python3 - <<'PY' "$cycle_report_two"
import json
import sys
from pathlib import Path

doc = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert doc["verdict"] == "pass", doc
assert doc["cycle_status"] == "already_recorded", doc
assert doc["delivery_verdict"] == "delivered_local_outbox", doc
assert doc["dispatch_verdict"] == "already_acknowledged", doc
assert doc["dispatch_receipt_ref"].startswith("runtime-artifacts/messaging/dispatch-receipts/"), doc
PY

cat >"$TMP_DIR/reflection-action.json" <<'JSON'
{
  "handoff_contract_ref": "planningops/contracts/reflection-action-handoff-contract.md",
  "verdict": "pass",
  "active_goal_key": "uap-goal-driven-autonomy-wave19",
  "queue_item_id": "queue-wave19-s20",
  "worker_run_id": "run-wave19-s20",
  "reflection_decision": "replan_required",
  "decision_reason": "dead_letter_runtime_outcome",
  "control_plane_action": "replan_backlog",
  "action_kind": "trigger_replan_review",
  "delivery_required": true,
  "message_class_hint": "decision_request",
  "operator_channel_role": "primary_operator_channel",
  "operator_channel_kind": "slack_skill_cli",
  "operator_channel_execution_repo": "rather-not-work-on/monday",
  "operator_channel_adapter_contract_ref": "planningops/contracts/operator-channel-adapter-contract.md",
  "goal_transition_required": false,
  "requested_goal_status": "-",
  "goal_transition_report_path": "-",
  "handoff_summary": "Queue item queue-wave19-s20 requires replanning review.",
  "source_packet_ref": "planningops/artifacts/validation/packet.json",
  "reflection_evaluation_ref": "planningops/artifacts/validation/eval.json"
}
JSON

python3 "$ROOT_DIR/scripts/run_operator_message_delivery_cycle.py" \
  --reflection-action-file "$TMP_DIR/reflection-action.json" \
  --profiles-config "$profiles_config" \
  --mode dry-run \
  --output "$cycle_report_dry_run"

python3 - <<'PY' "$cycle_report_dry_run"
import json
import sys
from pathlib import Path

doc = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert doc["verdict"] == "pass", doc
assert doc["cycle_status"] == "dry_run", doc
assert doc["delivery_verdict"] == "dry_run", doc
assert doc["channel_kind"] == "slack_skill_cli", doc
assert doc["dispatch_packet_ref"] == "-", doc
PY
