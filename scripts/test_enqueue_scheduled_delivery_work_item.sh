#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

cd "$ROOT_DIR"

DB_PATH="$TMP_DIR/runtime-queue.sqlite3"
REFLECTION_ACTION="$TMP_DIR/reflection-action.json"
GOAL_TRANSITION="$TMP_DIR/goal-transition-report.json"
OPERATOR_REPORT="$TMP_DIR/operator-report.json"
OPERATOR_SUMMARY="$TMP_DIR/operator-summary.md"
OPERATOR_REPORT_OUT="$TMP_DIR/operator-admission-report.json"
GOAL_REPORT_OUT="$TMP_DIR/goal-admission-report.json"
DRY_RUN_OUT="$TMP_DIR/dry-run-report.json"

cat > "$REFLECTION_ACTION" <<'JSON'
{
  "handoff_contract_ref": "planningops/contracts/reflection-action-handoff-contract.md",
  "verdict": "pass",
  "active_goal_key": "uap-goal-driven-autonomy-wave21",
  "queue_item_id": "queue-reflection-001",
  "worker_run_id": "worker-wave21-u20",
  "reflection_decision": "deliver_operator_message",
  "action_kind": "request_decision",
  "message_class_hint": "decision_request",
  "operator_channel_role": "primary_operator_channel",
  "delivery_required": true,
  "operator_channel_kind": "slack_skill_cli",
  "operator_channel_execution_repo": "rather-not-work-on/monday",
  "operator_channel_adapter_contract_ref": "planningops/contracts/operator-channel-adapter-contract.md",
  "operator_handoff_validation_path": "/tmp/planningops/operator-handoff-validation.json",
  "operator_handoff_bundle_path": "/tmp/planningops/operator-handoff-bundle.json",
  "operator_handoff_bundle_validation_path": "/tmp/planningops/operator-handoff-bundle-validation.json",
  "operator_handoff_bundle_readiness_path": "/tmp/planningops/operator-handoff-bundle-readiness.json",
  "operator_handoff_bundle_readiness_validation_path": "/tmp/planningops/operator-handoff-bundle-readiness-validation.json",
  "handoff_summary": "Wave21 needs an operator decision.",
  "decision_reason": "scheduler_native_queue_admission",
  "control_plane_action": "queue_admission",
  "federated_ci_summary": {
    "primary_remediation_command": "python3 planningops/scripts/doctor_federated_ci_summary.py --require-pass",
    "remediation_commands": [
      "python3 planningops/scripts/doctor_federated_ci_summary.py --require-pass",
      "bash planningops/scripts/gate_federated_ci_summary.sh"
    ]
  },
  "source_packet_ref": "planningops/artifacts/validation/reflection-packet.json",
  "reflection_evaluation_ref": "planningops/artifacts/validation/reflection-eval.json",
  "goal_transition_report_path": "-"
}
JSON

python3 scripts/enqueue_scheduled_delivery_work_item.py \
  --reflection-action-file "$REFLECTION_ACTION" \
  --schedule-key recurring-delivery \
  --mode apply \
  --queue-db "$DB_PATH" \
  --output "$OPERATOR_REPORT_OUT"

cat > "$GOAL_TRANSITION" <<'JSON'
{
  "goal_key": "uap-goal-driven-autonomy-wave21",
  "to_status": "achieved",
  "generated_at_utc": "2026-03-15T00:00:00Z"
}
JSON

cat > "$OPERATOR_REPORT" <<JSON
{
  "handoff_contract_ref": "planningops/contracts/supervisor-operator-handoff-contract.md",
  "goal_key": "uap-goal-driven-autonomy-wave21",
  "message_class_hint": "goal_completed",
  "goal_transition_report_path": "$GOAL_TRANSITION",
  "federated_ci_summary": {
    "primary_remediation_command": "python3 planningops/scripts/doctor_federated_ci_summary.py --require-pass",
    "remediation_commands": [
      "python3 planningops/scripts/doctor_federated_ci_summary.py --require-pass",
      "bash planningops/scripts/gate_federated_ci_summary.sh"
    ]
  },
  "terminal_notification_channel": {
    "kind": "email_cli"
  },
  "summary_path": "$OPERATOR_SUMMARY",
  "operator_handoff_validation_path": "/tmp/planningops/operator-handoff-validation.json",
  "operator_handoff_bundle_path": "/tmp/planningops/operator-handoff-bundle.json",
  "operator_handoff_bundle_validation_path": "/tmp/planningops/operator-handoff-bundle-validation.json",
  "operator_handoff_bundle_readiness_path": "/tmp/planningops/operator-handoff-bundle-readiness.json",
  "operator_handoff_bundle_readiness_validation_path": "/tmp/planningops/operator-handoff-bundle-readiness-validation.json",
  "operator_action": "notify_goal_completed",
  "priority_headline": "Wave21 completed",
  "priority_cta_command": "bash planningops/scripts/gate_federated_ci_summary.sh"
}
JSON

cat > "$OPERATOR_SUMMARY" <<'EOF'
Wave21 completed and is ready for terminal notification.
EOF

python3 scripts/enqueue_scheduled_delivery_work_item.py \
  --operator-report-file "$OPERATOR_REPORT" \
  --operator-summary-file "$OPERATOR_SUMMARY" \
  --schedule-key recurring-delivery \
  --mode apply \
  --queue-db "$DB_PATH" \
  --output "$GOAL_REPORT_OUT"

python3 scripts/enqueue_scheduled_delivery_work_item.py \
  --reflection-action-file "$REFLECTION_ACTION" \
  --schedule-key recurring-delivery \
  --mode dry-run \
  --queue-db "$TMP_DIR/dry-run.sqlite3" \
  --output "$DRY_RUN_OUT"

python3 - "$DB_PATH" "$OPERATOR_REPORT_OUT" "$GOAL_REPORT_OUT" "$DRY_RUN_OUT" <<'PY'
import json
import sqlite3
import sys
from pathlib import Path

db_path, operator_report_path, goal_report_path, dry_run_report_path = sys.argv[1:]
operator_report = json.loads(Path(operator_report_path).read_text())
goal_report = json.loads(Path(goal_report_path).read_text())
dry_run_report = json.loads(Path(dry_run_report_path).read_text())

assert operator_report["verdict"] == "pass", operator_report
assert operator_report["delivery_work_item_kind"] == "operator_message_delivery", operator_report
assert operator_report["selected_delivery_entrypoint"] == "scripts/run_operator_message_delivery_cycle.py", operator_report
assert operator_report["admitted_count"] == 1, operator_report
assert operator_report["primary_remediation_command"] == "python3 planningops/scripts/doctor_federated_ci_summary.py --require-pass", operator_report
assert operator_report["first_action_command"] == "python3 planningops/scripts/doctor_federated_ci_summary.py --require-pass", operator_report
assert operator_report["priority_cta_command"] == "python3 planningops/scripts/doctor_federated_ci_summary.py --require-pass", operator_report
assert operator_report["operator_handoff_validation_path"] == "/tmp/planningops/operator-handoff-validation.json", operator_report
assert operator_report["operator_handoff_bundle_path"] == "/tmp/planningops/operator-handoff-bundle.json", operator_report
assert operator_report["operator_handoff_bundle_validation_path"] == "/tmp/planningops/operator-handoff-bundle-validation.json", operator_report
assert operator_report["operator_handoff_bundle_readiness_path"] == "/tmp/planningops/operator-handoff-bundle-readiness.json", operator_report
assert operator_report["operator_handoff_bundle_readiness_validation_path"] == "/tmp/planningops/operator-handoff-bundle-readiness-validation.json", operator_report
assert operator_report["remediation_commands"] == [
    "python3 planningops/scripts/doctor_federated_ci_summary.py --require-pass",
    "bash planningops/scripts/gate_federated_ci_summary.sh",
], operator_report

assert goal_report["verdict"] == "pass", goal_report
assert goal_report["delivery_work_item_kind"] == "goal_completion_delivery", goal_report
assert goal_report["selected_delivery_entrypoint"] == "scripts/run_goal_completion_delivery_cycle.py", goal_report
assert goal_report["admitted_count"] == 1, goal_report
assert goal_report["headline"] == "Wave21 completed", goal_report
assert goal_report["first_action_command"] == "bash planningops/scripts/gate_federated_ci_summary.sh", goal_report
assert goal_report["priority_headline"] == "Wave21 completed", goal_report
assert goal_report["priority_cta_command"] == "bash planningops/scripts/gate_federated_ci_summary.sh", goal_report
assert goal_report["operator_handoff_validation_path"] == "/tmp/planningops/operator-handoff-validation.json", goal_report
assert goal_report["operator_handoff_bundle_path"] == "/tmp/planningops/operator-handoff-bundle.json", goal_report
assert goal_report["operator_handoff_bundle_validation_path"] == "/tmp/planningops/operator-handoff-bundle-validation.json", goal_report
assert goal_report["operator_handoff_bundle_readiness_path"] == "/tmp/planningops/operator-handoff-bundle-readiness.json", goal_report
assert goal_report["operator_handoff_bundle_readiness_validation_path"] == "/tmp/planningops/operator-handoff-bundle-readiness-validation.json", goal_report

assert dry_run_report["verdict"] == "pass", dry_run_report
assert dry_run_report["admitted_count"] == 0, dry_run_report
assert dry_run_report["mode"] == "dry-run", dry_run_report

conn = sqlite3.connect(db_path)
rows = conn.execute("SELECT queue_item_id, work_payload_ref, goal_key, schedule_key FROM queue_items ORDER BY queue_item_id").fetchall()
conn.close()
assert len(rows) == 2, rows
assert rows[0][2] == "uap-goal-driven-autonomy-wave21", rows
assert rows[0][3] == "recurring-delivery", rows
assert rows[0][1].startswith("runtime-artifacts/messaging/scheduled-delivery-work-items/"), rows
operator_work_item = json.loads(Path(operator_report["scheduled_delivery_work_item_ref"]).read_text())
assert operator_work_item["primary_remediation_command"] == "python3 planningops/scripts/doctor_federated_ci_summary.py --require-pass", operator_work_item
assert operator_work_item["first_action_command"] == "python3 planningops/scripts/doctor_federated_ci_summary.py --require-pass", operator_work_item
assert operator_work_item["priority_cta_command"] == "python3 planningops/scripts/doctor_federated_ci_summary.py --require-pass", operator_work_item
assert operator_work_item["operator_handoff_validation_path"] == "/tmp/planningops/operator-handoff-validation.json", operator_work_item
assert operator_work_item["operator_handoff_bundle_path"] == "/tmp/planningops/operator-handoff-bundle.json", operator_work_item
assert operator_work_item["operator_handoff_bundle_validation_path"] == "/tmp/planningops/operator-handoff-bundle-validation.json", operator_work_item
assert operator_work_item["operator_handoff_bundle_readiness_path"] == "/tmp/planningops/operator-handoff-bundle-readiness.json", operator_work_item
assert operator_work_item["operator_handoff_bundle_readiness_validation_path"] == "/tmp/planningops/operator-handoff-bundle-readiness-validation.json", operator_work_item
assert operator_work_item["remediation_commands"] == [
    "python3 planningops/scripts/doctor_federated_ci_summary.py --require-pass",
    "bash planningops/scripts/gate_federated_ci_summary.sh",
], operator_work_item
goal_work_item = json.loads(Path(goal_report["scheduled_delivery_work_item_ref"]).read_text())
assert goal_work_item["headline"] == "Wave21 completed", goal_work_item
assert goal_work_item["first_action_command"] == "bash planningops/scripts/gate_federated_ci_summary.sh", goal_work_item
assert goal_work_item["priority_headline"] == "Wave21 completed", goal_work_item
assert goal_work_item["priority_cta_command"] == "bash planningops/scripts/gate_federated_ci_summary.sh", goal_work_item
assert "delivery_target" not in goal_work_item, goal_work_item
assert goal_work_item["operator_handoff_validation_path"] == "/tmp/planningops/operator-handoff-validation.json", goal_work_item
assert goal_work_item["operator_handoff_bundle_path"] == "/tmp/planningops/operator-handoff-bundle.json", goal_work_item
assert goal_work_item["operator_handoff_bundle_validation_path"] == "/tmp/planningops/operator-handoff-bundle-validation.json", goal_work_item
assert goal_work_item["operator_handoff_bundle_readiness_path"] == "/tmp/planningops/operator-handoff-bundle-readiness.json", goal_work_item
assert goal_work_item["operator_handoff_bundle_readiness_validation_path"] == "/tmp/planningops/operator-handoff-bundle-readiness-validation.json", goal_work_item
assert "Wave21 completed" in goal_work_item["priority_summary_markdown"], goal_work_item
assert "`bash planningops/scripts/gate_federated_ci_summary.sh`" in goal_work_item["priority_summary_markdown"], goal_work_item
goal_payload = json.loads(Path(goal_work_item["payload_ref"]).read_text())
assert goal_payload["metadata"]["priority_headline"] == "Wave21 completed", goal_payload
assert goal_payload["metadata"]["priority_cta_command"] == "bash planningops/scripts/gate_federated_ci_summary.sh", goal_payload
assert goal_payload["metadata"]["operator_handoff_validation_path"] == "/tmp/planningops/operator-handoff-validation.json", goal_payload
assert goal_payload["metadata"]["operator_handoff_bundle_path"] == "/tmp/planningops/operator-handoff-bundle.json", goal_payload
assert goal_payload["metadata"]["operator_handoff_bundle_validation_path"] == "/tmp/planningops/operator-handoff-bundle-validation.json", goal_payload
assert goal_payload["metadata"]["operator_handoff_bundle_readiness_path"] == "/tmp/planningops/operator-handoff-bundle-readiness.json", goal_payload
assert goal_payload["metadata"]["operator_handoff_bundle_readiness_validation_path"] == "/tmp/planningops/operator-handoff-bundle-readiness-validation.json", goal_payload
assert "## First Action" in goal_payload["body"], goal_payload
PY

echo "enqueue scheduled delivery work item test passed"
