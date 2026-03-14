#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

cd "$ROOT_DIR"

cat >"$TMP_DIR/continue-action.json" <<'JSON'
{
  "handoff_contract_ref": "planningops/contracts/reflection-action-handoff-contract.md",
  "verdict": "pass",
  "active_goal_key": "uap-goal-driven-autonomy-wave8",
  "queue_item_id": "queue-wave8-001",
  "worker_run_id": "wave8-run-001",
  "reflection_decision": "continue",
  "decision_reason": "retry_wait_runtime_outcome",
  "control_plane_action": "none",
  "action_kind": "record_continue",
  "delivery_required": false,
  "message_class_hint": "status_update",
  "operator_channel_role": "none",
  "operator_channel_kind": "-",
  "operator_channel_execution_repo": "-",
  "operator_channel_adapter_contract_ref": "-",
  "goal_transition_required": false,
  "requested_goal_status": "-",
  "goal_transition_report_path": "-",
  "handoff_summary": "Queue item queue-wave8-001 remains in the supervisor flow after reflection decision continue (record_continue).",
  "source_packet_ref": "planningops/artifacts/validation/retry-packet.json",
  "reflection_evaluation_ref": "planningops/artifacts/validation/retry-eval.json"
}
JSON

cat >"$TMP_DIR/replan-action.json" <<'JSON'
{
  "handoff_contract_ref": "planningops/contracts/reflection-action-handoff-contract.md",
  "verdict": "pass",
  "active_goal_key": "uap-goal-driven-autonomy-wave8",
  "queue_item_id": "queue-wave8-002",
  "worker_run_id": "wave8-run-002",
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
  "handoff_summary": "Queue item queue-wave8-002 exhausted runtime recovery and requires replanning review for goal uap-goal-driven-autonomy-wave8.",
  "source_packet_ref": "planningops/artifacts/validation/dead-letter-packet.json",
  "reflection_evaluation_ref": "planningops/artifacts/validation/dead-letter-eval.json"
}
JSON

cat >"$TMP_DIR/operator-notify-action.json" <<'JSON'
{
  "handoff_contract_ref": "planningops/contracts/reflection-action-handoff-contract.md",
  "verdict": "pass",
  "active_goal_key": "uap-goal-driven-autonomy-wave8",
  "queue_item_id": "queue-wave8-003",
  "worker_run_id": "wave8-run-003",
  "reflection_decision": "operator_notify",
  "decision_reason": "packet_goal_mismatch_active_goal",
  "control_plane_action": "notify_operator",
  "action_kind": "escalate_operator_attention",
  "delivery_required": true,
  "message_class_hint": "blocked_report",
  "operator_channel_role": "primary_operator_channel",
  "operator_channel_kind": "slack_skill_cli",
  "operator_channel_execution_repo": "rather-not-work-on/monday",
  "operator_channel_adapter_contract_ref": "planningops/contracts/operator-channel-adapter-contract.md",
  "goal_transition_required": false,
  "requested_goal_status": "-",
  "goal_transition_report_path": "-",
  "handoff_summary": "Queue item queue-wave8-003 requires operator attention for goal uap-goal-driven-autonomy-wave8 after reflection decision operator_notify.",
  "source_packet_ref": "planningops/artifacts/validation/goal-mismatch-packet.json",
  "reflection_evaluation_ref": "planningops/artifacts/validation/goal-mismatch-eval.json"
}
JSON

cat >"$TMP_DIR/goal-transition-report.json" <<'JSON'
{
  "generated_at_utc": "2026-03-14T08:00:00Z",
  "goal_key": "uap-goal-driven-autonomy-wave8",
  "to_status": "achieved",
  "verdict": "pass"
}
JSON

cat >"$TMP_DIR/goal-completed-action.json" <<JSON
{
  "handoff_contract_ref": "planningops/contracts/reflection-action-handoff-contract.md",
  "verdict": "pass",
  "active_goal_key": "uap-goal-driven-autonomy-wave8",
  "queue_item_id": "queue-wave8-004",
  "worker_run_id": "wave8-run-004",
  "reflection_decision": "goal_achieved",
  "decision_reason": "completed_runtime_outcome",
  "control_plane_action": "evaluate_goal_completion",
  "action_kind": "prepare_goal_completion",
  "delivery_required": true,
  "message_class_hint": "goal_completed",
  "operator_channel_role": "terminal_notification_channel",
  "operator_channel_kind": "email_cli",
  "operator_channel_execution_repo": "rather-not-work-on/monday",
  "operator_channel_adapter_contract_ref": "planningops/contracts/operator-channel-adapter-contract.md",
  "goal_transition_required": true,
  "requested_goal_status": "achieved",
  "goal_transition_report_path": "$TMP_DIR/goal-transition-report.json",
  "handoff_summary": "Queue item queue-wave8-004 completed successfully and qualifies goal uap-goal-driven-autonomy-wave8 for goal-completion handling.",
  "source_packet_ref": "planningops/artifacts/validation/completed-packet.json",
  "reflection_evaluation_ref": "planningops/artifacts/validation/completed-eval.json"
}
JSON

python3 "$ROOT_DIR/scripts/send_reflection_decision_update.py" \
  --action-file "$TMP_DIR/continue-action.json" \
  --output "$TMP_DIR/continue-report.json"

python3 - <<'PY' "$TMP_DIR/continue-report.json"
import json
import sys
from pathlib import Path

doc = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert doc["verdict"] == "pass", doc
assert doc["delivery_required"] is False, doc
assert doc["delivery_skipped"] is True, doc
assert doc["skip_reason"] == "delivery_not_required", doc
PY

python3 "$ROOT_DIR/scripts/send_reflection_decision_update.py" \
  --action-file "$TMP_DIR/replan-action.json" \
  --delivery-target "slack://monday/thread-wave8" \
  --thread-ref "thread-wave8" \
  --output "$TMP_DIR/replan-report.json"

python3 - <<'PY' "$TMP_DIR/replan-report.json"
import json
import sys
from pathlib import Path

doc = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert doc["verdict"] == "pass", doc
assert doc["delegate_script"] == "scripts/send_operator_message.py", doc
assert doc["delegate_report"]["delivery_report"]["deliveryVerdict"] == "dry_run", doc
assert doc["payload"]["messageClass"] == "decision_request", doc
assert doc["payload"]["target"]["threadRef"] == "thread-wave8", doc
PY

python3 "$ROOT_DIR/scripts/send_reflection_decision_update.py" \
  --action-file "$TMP_DIR/operator-notify-action.json" \
  --delivery-target "slack://monday/thread-wave8" \
  --output "$TMP_DIR/operator-notify-report.json"

python3 - <<'PY' "$TMP_DIR/operator-notify-report.json"
import json
import sys
from pathlib import Path

doc = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert doc["verdict"] == "pass", doc
assert doc["payload"]["messageClass"] == "blocked_report", doc
assert doc["delegate_report"]["delivery_report"]["deliveryVerdict"] == "dry_run", doc
PY

python3 "$ROOT_DIR/scripts/send_reflection_decision_update.py" \
  --action-file "$TMP_DIR/goal-completed-action.json" \
  --delivery-target "mailto:operator@example.com" \
  --output "$TMP_DIR/goal-completed-report.json"

python3 - <<'PY' "$TMP_DIR/goal-completed-report.json"
import json
import sys
from pathlib import Path

doc = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert doc["verdict"] == "pass", doc
assert doc["delegate_script"] == "scripts/send_goal_completion_notification.py", doc
assert doc["payload"]["messageClass"] == "goal_completed", doc
assert doc["payload"]["achievedAtUtc"] == "2026-03-14T08:00:00Z", doc
assert doc["delegate_report"]["delivery_report"]["deliveryVerdict"] == "dry_run", doc
PY

if python3 "$ROOT_DIR/scripts/send_reflection_decision_update.py" \
  --action-file "$TMP_DIR/replan-action.json" \
  --delivery-target "slack://monday/thread-wave8" \
  --mode apply \
  --output "$TMP_DIR/replan-apply-report.json"; then
  echo "expected replan apply to fail without transport"
  exit 1
fi

python3 - <<'PY' "$TMP_DIR/replan-apply-report.json"
import json
import sys
from pathlib import Path

doc = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert doc["verdict"] == "fail", doc
assert doc["delegate_report"]["delivery_report"]["deliveryVerdict"] == "blocked", doc
assert doc["errors"] == ["operator_transport_not_configured"], doc
PY

if python3 "$ROOT_DIR/scripts/send_reflection_decision_update.py" \
  --action-file "$TMP_DIR/goal-completed-action.json" \
  --delivery-target "mailto:operator@example.com" \
  --mode apply \
  --output "$TMP_DIR/goal-completed-apply-report.json"; then
  echo "expected goal completion apply to fail without transport"
  exit 1
fi

python3 - <<'PY' "$TMP_DIR/goal-completed-apply-report.json"
import json
import sys
from pathlib import Path

doc = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert doc["verdict"] == "fail", doc
assert doc["delegate_report"]["delivery_report"]["deliveryVerdict"] == "blocked", doc
assert doc["errors"] == ["goal_completion_transport_not_configured"], doc
PY

echo "reflection decision update cli contract ok"
