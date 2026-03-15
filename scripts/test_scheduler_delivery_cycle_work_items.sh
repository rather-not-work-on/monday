#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

cd "$ROOT_DIR"

WORK_ITEM_ROOT="$ROOT_DIR/runtime-artifacts/messaging/scheduled-delivery-work-items"
mkdir -p "$WORK_ITEM_ROOT"
trap 'rm -rf "$TMP_DIR" "$WORK_ITEM_ROOT"' EXIT

cat > "$WORK_ITEM_ROOT/operator-message.json" <<'JSON'
{
  "queue_item_id": "queue-wave20-operator-001",
  "goal_key": "uap-goal-driven-autonomy-wave20",
  "delivery_work_item_kind": "operator_message_delivery",
  "message_class": "status_update",
  "source_artifact_ref": "planningops/artifacts/validation/reflection-action.json",
  "delivery_idempotency_key": "wave20:operator:001",
  "delivery_target": "local-slack-channel",
  "channel_kind": "slack_skill_cli",
  "thread_ref": "wave20-thread"
}
JSON

cat > "$WORK_ITEM_ROOT/goal-completion.json" <<'JSON'
{
  "queue_item_id": "queue-wave20-goal-001",
  "goal_key": "uap-goal-driven-autonomy-wave20",
  "delivery_work_item_kind": "goal_completion_delivery",
  "message_class": "goal_completed",
  "source_artifact_ref": "planningops/artifacts/validation/operator-report.json",
  "goal_transition_report_ref": "planningops/artifacts/validation/goal-transition.json",
  "delivery_idempotency_key": "wave20:goal:001",
  "delivery_target": "local-email-target",
  "channel_kind": "email_cli"
}
JSON

python3 - <<'PY'
import sys
from pathlib import Path

root = Path.cwd()
sys.path.insert(0, str(root / "scripts"))

from scheduler_delivery_cycle_work_items import load_delivery_work_item

operator_queue_item = {
    "queue_item_id": "queue-wave20-operator-001",
    "goal_key": "uap-goal-driven-autonomy-wave20",
    "work_payload_ref": "runtime-artifacts/messaging/scheduled-delivery-work-items/operator-message.json",
}
operator = load_delivery_work_item(operator_queue_item, root=root)
assert operator["handoff_contract_ref"] == "planningops/contracts/scheduled-delivery-cycle-handoff-contract.md", operator
assert operator["selected_delivery_entrypoint"] == "scripts/run_operator_message_delivery_cycle.py", operator
assert operator["delivery_work_item_kind"] == "operator_message_delivery", operator
assert operator["channel_kind"] == "slack_skill_cli", operator

goal_queue_item = {
    "queue_item_id": "queue-wave20-goal-001",
    "goal_key": "uap-goal-driven-autonomy-wave20",
    "work_payload_ref": "runtime-artifacts/messaging/scheduled-delivery-work-items/goal-completion.json",
}
goal = load_delivery_work_item(goal_queue_item, root=root)
assert goal["selected_delivery_entrypoint"] == "scripts/run_goal_completion_delivery_cycle.py", goal
assert goal["delivery_work_item_kind"] == "goal_completion_delivery", goal
assert goal["goal_transition_report_ref"] == "planningops/artifacts/validation/goal-transition.json", goal
PY

cat > "$WORK_ITEM_ROOT/invalid.json" <<'JSON'
{
  "queue_item_id": "queue-wave20-goal-001",
  "goal_key": "uap-goal-driven-autonomy-wave20",
  "delivery_work_item_kind": "operator_message_delivery",
  "message_class": "goal_completed",
  "source_artifact_ref": "planningops/artifacts/validation/operator-report.json",
  "delivery_idempotency_key": "wave20:invalid:001"
}
JSON

python3 - <<'PY'
import sys
from pathlib import Path

root = Path.cwd()
sys.path.insert(0, str(root / "scripts"))

from scheduler_delivery_cycle_work_items import load_delivery_work_item

queue_item = {
    "queue_item_id": "queue-wave20-goal-001",
    "goal_key": "uap-goal-driven-autonomy-wave20",
    "work_payload_ref": "runtime-artifacts/messaging/scheduled-delivery-work-items/invalid.json",
}
try:
    load_delivery_work_item(queue_item, root=root)
except SystemExit as exc:
    assert "operator_message_delivery message_class invalid" in str(exc), exc
else:
    raise SystemExit("expected invalid operator message class to fail")
PY

echo "scheduler delivery cycle work items test passed"
