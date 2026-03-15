#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_DIR="$(mktemp -d)"
TEST_OUTBOX_ROOT="runtime-artifacts/test-local-dispatch-execution"
trap 'rm -rf "$TMP_DIR" "$ROOT_DIR/$TEST_OUTBOX_ROOT" "$ROOT_DIR/runtime-artifacts/messaging/dispatch-packets" "$ROOT_DIR/runtime-artifacts/messaging/dispatch-acks" "$ROOT_DIR/runtime-artifacts/messaging/dispatch-receipts"' EXIT

cd "$ROOT_DIR"

profiles_config="$TMP_DIR/local-operator-channel-profiles.json"
operator_payload="$TMP_DIR/operator-message.json"
operator_report="$TMP_DIR/operator-message-report.json"
dispatch_packet="$ROOT_DIR/runtime-artifacts/messaging/dispatch-packets/wave17-execution.json"
execution_packet="$ROOT_DIR/runtime-artifacts/messaging/dispatch-execution-packets/wave17-execution.json"

rm -rf "$ROOT_DIR/runtime-artifacts/messaging/dispatch-packets" \
       "$ROOT_DIR/runtime-artifacts/messaging/dispatch-execution-packets" \
       "$ROOT_DIR/runtime-artifacts/messaging/dispatch-acks" \
       "$ROOT_DIR/runtime-artifacts/messaging/dispatch-receipts"

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

cat >"$operator_payload" <<'JSON'
{
  "messageClass": "status_update",
  "deliveryMode": "apply",
  "goalKey": "uap-goal-driven-autonomy-wave17",
  "body": "export this dispatch execution packet",
  "runId": "run-wave17-q20",
  "taskId": "queue-wave17-q20",
  "target": {
    "channelKind": "slack_skill_cli",
    "threadRef": "thread-wave17-q20"
  }
}
JSON

python3 "$ROOT_DIR/scripts/send_operator_message.py" \
  --payload-file "$operator_payload" \
  --profiles-config "$profiles_config" \
  --mode apply \
  --output "$operator_report"

python3 "$ROOT_DIR/scripts/export_local_outbox_dispatch_packet.py" \
  --delivery-report-file "$operator_report" \
  --output "$dispatch_packet"

python3 "$ROOT_DIR/scripts/export_local_dispatch_execution_packet.py" \
  --dispatch-packet-file "$dispatch_packet" \
  --output "$execution_packet"

python3 - <<'PY' "$execution_packet"
import json
import sys
from pathlib import Path

doc = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert doc["execution_packet_version"] == 1, doc
assert doc["dispatch_cycle_contract_ref"] == "planningops/contracts/local-dispatch-cycle-handoff-contract.md", doc
assert doc["goal_key"] == "uap-goal-driven-autonomy-wave17", doc
assert doc["message_class"] == "status_update", doc
assert doc["channel_kind"] == "slack_skill_cli", doc
assert doc["transport_kind"] == "local_outbox", doc
assert doc["bridge_adapter_kind"] == "monday_local_operator_bridge", doc
assert doc["execution_verdict"] == "ready_for_local_bridge", doc
assert doc["thread_ref"] == "thread-wave17-q20", doc
assert doc["dispatch_receipt_ref"] == "-", doc
assert doc["payload_body"] == "export this dispatch execution packet", doc
PY

python3 - <<'PY' "$dispatch_packet"
import sys
from pathlib import Path

root = Path.cwd()
sys.path.insert(0, str(root / "scripts"))

import json
from local_outbox_dispatch_common import default_dispatch_receipt_path

packet = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
receipt_path = default_dispatch_receipt_path(packet["delivery_idempotency_key"], root=root)
receipt_path.parent.mkdir(parents=True, exist_ok=True)
receipt_path.write_text('{"receipt_status":"recorded"}\n', encoding="utf-8")
print(receipt_path)
PY

python3 "$ROOT_DIR/scripts/export_local_dispatch_execution_packet.py" \
  --dispatch-packet-file "$dispatch_packet" \
  --output "$ROOT_DIR/runtime-artifacts/messaging/dispatch-execution-packets/wave17-execution-with-receipt.json"

python3 - <<'PY' "$ROOT_DIR/runtime-artifacts/messaging/dispatch-execution-packets/wave17-execution-with-receipt.json"
import json
import sys
from pathlib import Path

doc = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert doc["execution_verdict"] == "already_dispatched", doc
assert doc["dispatch_receipt_ref"].startswith("runtime-artifacts/messaging/dispatch-receipts/"), doc
PY
