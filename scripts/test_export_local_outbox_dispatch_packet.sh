#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_DIR="$(mktemp -d)"
TEST_OUTBOX_ROOT="runtime-artifacts/test-local-outbox-dispatch"
trap 'rm -rf "$TMP_DIR" "$ROOT_DIR/$TEST_OUTBOX_ROOT" "$ROOT_DIR/runtime-artifacts/messaging/dispatch-packets" "$ROOT_DIR/runtime-artifacts/messaging/dispatch-acks"' EXIT

cd "$ROOT_DIR"

profiles_config="$TMP_DIR/local-operator-channel-profiles.json"
operator_payload="$TMP_DIR/operator-message.json"
operator_report="$TMP_DIR/operator-message-report.json"
dispatch_packet="$ROOT_DIR/runtime-artifacts/messaging/dispatch-packets/wave16-dispatch.json"

rm -rf "$ROOT_DIR/runtime-artifacts/messaging/dispatch-packets" \
       "$ROOT_DIR/runtime-artifacts/messaging/dispatch-acks"

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
  "messageClass": "decision_request",
  "deliveryMode": "apply",
  "goalKey": "uap-goal-driven-autonomy-wave16",
  "body": "dispatch this local outbox message",
  "runId": "run-wave16-001",
  "taskId": "queue-wave16-001",
  "target": {
    "channelKind": "slack_skill_cli",
    "threadRef": "thread-wave16"
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

python3 - <<'PY' "$dispatch_packet"
import json
import sys
from pathlib import Path

doc = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert doc["dispatch_packet_version"] == 1, doc
assert doc["dispatch_contract_ref"] == "planningops/contracts/local-outbox-dispatch-handoff-contract.md", doc
assert doc["goal_key"] == "uap-goal-driven-autonomy-wave16", doc
assert doc["message_class"] == "decision_request", doc
assert doc["channel_kind"] == "slack_skill_cli", doc
assert doc["target_resolution_mode"] == "local_profile", doc
assert doc["transport_kind"] == "local_outbox", doc
assert doc["dispatch_verdict"] == "ready_for_dispatch", doc
assert doc["source_outbox_message_ref"].startswith("runtime-artifacts/test-local-outbox-dispatch/"), doc
assert doc["dispatch_ack_checkpoint_ref"] == "-", doc
PY

python3 - <<'PY' "$dispatch_packet"
import sys
from pathlib import Path

root = Path.cwd()
sys.path.insert(0, str(root / "scripts"))

import json
from local_outbox_dispatch_common import default_ack_checkpoint_path

packet = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
ack_path = default_ack_checkpoint_path(packet["delivery_idempotency_key"], root=root)
ack_path.parent.mkdir(parents=True, exist_ok=True)
ack_path.write_text('{"ack_status":"recorded"}\n', encoding="utf-8")
print(ack_path)
PY

python3 "$ROOT_DIR/scripts/export_local_outbox_dispatch_packet.py" \
  --delivery-report-file "$operator_report" \
  --output "$ROOT_DIR/runtime-artifacts/messaging/dispatch-packets/wave16-dispatch-with-ack.json"

python3 - <<'PY' "$ROOT_DIR/runtime-artifacts/messaging/dispatch-packets/wave16-dispatch-with-ack.json"
import json
import sys
from pathlib import Path

doc = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert doc["dispatch_verdict"] == "already_acknowledged", doc
assert doc["dispatch_ack_checkpoint_ref"].startswith("runtime-artifacts/messaging/dispatch-acks/"), doc
PY
