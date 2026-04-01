#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

bridge_valid="$TMP_DIR/bridge-valid.json"
bridge_invalid="$TMP_DIR/bridge-invalid.json"
bridge_day="$TMP_DIR/day-packet.json"
bridge_mission="$TMP_DIR/mission-packet.json"
bridge_handoff="$TMP_DIR/handoff-report.json"
bridge_operator="$TMP_DIR/local-operator-report.json"
bridge_valid_report="$TMP_DIR/bridge-valid-report.json"
bridge_invalid_report="$TMP_DIR/bridge-invalid-report.json"

consumer_launch="$TMP_DIR/launch-request.json"
consumer_mission="$TMP_DIR/mission.json"
consumer_runtime="$TMP_DIR/runtime-report.json"
consumer_valid="$TMP_DIR/consumer-valid.json"
consumer_invalid="$TMP_DIR/consumer-invalid.json"
consumer_valid_report="$TMP_DIR/consumer-valid-report.json"
consumer_invalid_report="$TMP_DIR/consumer-invalid-report.json"

cat >"$bridge_day" <<'JSON'
{"day_packet_id":"day-1"}
JSON
cat >"$bridge_mission" <<'JSON'
{"packet_id":"mission-1"}
JSON
cat >"$bridge_handoff" <<'JSON'
{"record":{"headline":"Launch monday locally."}}
JSON
cat >"$bridge_operator" <<'JSON'
{"readiness":{"status":"ready"}}
JSON

cat >"$bridge_valid" <<JSON
{
  "generated_at_utc": "2026-04-01T10:10:00Z",
  "bridge_id": "monday-local-inbox-20260401T101000Z",
  "contract_ref": "planningops/contracts/monday-local-operator-inbox-payload-bridge-contract.md",
  "artifact_paths": {
    "latest_payload_path": "$bridge_valid",
    "stamped_payload_path": "$TMP_DIR/stamped-bridge.json",
    "output_path": null
  },
  "payload": {
    "title": "Monday local operator day packet",
    "status": "ready",
    "headline": "Monday local operator day packet",
    "priority_headline": "Monday local operator day packet",
    "operator_action": "launch_monday_local_runtime",
    "recommended_wait_minutes": 0,
    "retry_mode": "none",
    "needs_human_attention": false,
    "message_class_hint": "status_update",
    "planner_profile": "local_ollama",
    "launch_mode": "direct",
    "local_model_route": "direct_local_ollama",
    "day_packet_id": "day-1",
    "mission_packet_id": "mission-1",
    "mission_objective": "Resolve the next local monday runtime launch.",
    "first_action_command": "python3 planningops/scripts/run_monday_local_operator_stack.py --execution-mode direct",
    "monday_runtime_entrypoint_command": "python3 scripts/run_local_runtime_smoke.py --profile local_ollama",
    "rollback_command": "bash scripts/litellm_stack_launcher.sh --mode start",
    "local_validation_snapshot_status": "present",
    "local_validation_summary_lines": [
      "monday_local_operator_stack_report: freshness=fresh promotability=promotable"
    ],
    "local_validation_action_lines": [],
    "queue_lines": [],
    "target_lines": [
      "monday local runtime smoke"
    ],
    "immediate_actions": [
      "Run the monday local runtime smoke."
    ],
    "attachments": [
      "$bridge_valid",
      "$bridge_day"
    ],
    "body_markdown": "## Monday Local Operator Inbox Payload",
    "bridge_contract_ref": "planningops/contracts/monday-local-operator-inbox-payload-bridge-contract.md",
    "source_artifacts": {
      "day_packet_path": "$bridge_day",
      "mission_packet_path": "$bridge_mission",
      "handoff_report_path": "$bridge_handoff",
      "local_operator_report_path": "$bridge_operator"
    }
  }
}
JSON

python3 "$ROOT_DIR/scripts/validate_planningops_local_operator_inbox_artifacts.py" \
  --kind bridge \
  --artifact "$bridge_valid" \
  --output "$bridge_valid_report"

cp "$bridge_valid" "$bridge_invalid"
python3 - "$bridge_invalid" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
doc = json.loads(path.read_text(encoding="utf-8"))
doc["contract_ref"] = "planningops/contracts/wrong-contract.md"
doc["payload"]["source_artifacts"]["day_packet_path"] = str(path.parent / "missing-day-packet.json")
path.write_text(json.dumps(doc, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
PY

if python3 "$ROOT_DIR/scripts/validate_planningops_local_operator_inbox_artifacts.py" \
  --kind bridge \
  --artifact "$bridge_invalid" \
  --output "$bridge_invalid_report"; then
  echo "expected invalid bridge validation to fail"
  exit 1
fi

cat >"$consumer_launch" <<JSON
{
  "source_bridge_id": "monday-local-inbox-20260401T101000Z",
  "source_day_packet_id": "day-1",
  "source_mission_packet_id": "mission-1",
  "mission_objective": "Resolve the next local monday runtime launch.",
  "planner_profile": "local_ollama",
  "launch_mode": "direct",
  "local_model_route": "direct_local_ollama",
  "first_action_command": "python3 planningops/scripts/run_monday_local_operator_stack.py --execution-mode direct",
  "monday_runtime_entrypoint_command": "python3 scripts/run_local_runtime_smoke.py --profile local_ollama",
  "rollback_command": "bash scripts/litellm_stack_launcher.sh --mode start",
  "recommended_wait_minutes": 0,
  "needs_human_attention": false,
  "local_validation_snapshot_status": "present",
  "local_validation_summary_lines": [
    "monday_local_operator_stack_report: freshness=fresh promotability=promotable"
  ],
  "local_validation_action_lines": [],
  "can_launch": true,
  "block_reasons": [],
  "runtime_command_args": [
    "python3",
    "scripts/run_local_runtime_smoke.py",
    "--profile",
    "local_ollama"
  ],
  "runtime_input_overrides": {
    "planner_runtime_config": "$TMP_DIR/planner-runtime.json",
    "runtime_profile_file": "$TMP_DIR/runtime-profiles.json"
  },
  "source_artifacts": {
    "day_packet_path": "$bridge_day",
    "mission_packet_path": "$bridge_mission",
    "handoff_report_path": "$bridge_handoff",
    "local_operator_report_path": "$bridge_operator"
  }
}
JSON
cat >"$consumer_mission" <<'JSON'
{"missionId":"mission-1","objective":"Resolve the next local monday runtime launch."}
JSON
cat >"$consumer_runtime" <<'JSON'
{"verdict":"pass","reason_code":"ok"}
JSON
cat >"$TMP_DIR/planner-runtime.json" <<'JSON'
{"config_version":1}
JSON
cat >"$TMP_DIR/runtime-profiles.json" <<'JSON'
{"active_profile":"local"}
JSON

cat >"$consumer_valid" <<JSON
{
  "generated_at_utc": "2026-04-01T10:12:00Z",
  "run_id": "planningops-local-inbox-consumer-20260401T101200Z",
  "consumer_contract_ref": "contracts/planningops-local-operator-inbox-consumer-contract.md",
  "source_bridge_path": "$bridge_valid",
  "bridge_id": "monday-local-inbox-20260401T101000Z",
  "mode": "apply",
  "verdict": "pass",
  "reason_code": "ok",
  "consumer_status": "ready_to_launch",
  "artifact_paths": {
    "launch_request_path": "$consumer_launch",
    "mission_file_path": "$consumer_mission",
    "runtime_report_path": "$consumer_runtime",
    "report_path": "$consumer_valid"
  },
  "launch_request": $(cat "$consumer_launch"),
  "runtime_report_summary": {
    "verdict": "pass",
    "reason_code": "ok",
    "report_path": "$consumer_runtime"
  },
  "execution": {
    "attempted": true,
    "command_args": [
      "python3",
      "scripts/run_local_runtime_smoke.py",
      "--profile",
      "local_ollama"
    ],
    "exit_code": 0,
    "stdout": "ok",
    "stderr": ""
  }
}
JSON

python3 "$ROOT_DIR/scripts/validate_planningops_local_operator_inbox_artifacts.py" \
  --kind consumer-report \
  --artifact "$consumer_valid" \
  --output "$consumer_valid_report"

cp "$consumer_valid" "$consumer_invalid"
python3 - "$consumer_invalid" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
doc = json.loads(path.read_text(encoding="utf-8"))
doc["consumer_contract_ref"] = "contracts/wrong-consumer-contract.md"
doc["launch_request"]["source_bridge_id"] = "different-bridge-id"
doc["mode"] = "dry-run"
path.write_text(json.dumps(doc, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
PY

if python3 "$ROOT_DIR/scripts/validate_planningops_local_operator_inbox_artifacts.py" \
  --kind consumer-report \
  --artifact "$consumer_invalid" \
  --output "$consumer_invalid_report"; then
  echo "expected invalid consumer report validation to fail"
  exit 1
fi

python3 - "$bridge_valid_report" "$bridge_invalid_report" "$consumer_valid_report" "$consumer_invalid_report" <<'PY'
import json
import sys
from pathlib import Path

bridge_valid = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
bridge_invalid = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
consumer_valid = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))
consumer_invalid = json.loads(Path(sys.argv[4]).read_text(encoding="utf-8"))

assert bridge_valid["verdict"] == "pass", bridge_valid
assert bridge_valid["kind"] == "bridge", bridge_valid

assert bridge_invalid["verdict"] == "fail", bridge_invalid
bridge_errors = "\n".join(bridge_invalid["errors"])
assert "bridge contract ref" in bridge_errors or "missing" in bridge_errors, bridge_invalid

assert consumer_valid["verdict"] == "pass", consumer_valid
assert consumer_valid["kind"] == "consumer-report", consumer_valid

assert consumer_invalid["verdict"] == "fail", consumer_invalid
consumer_errors = "\n".join(consumer_invalid["errors"])
assert "consumer contract ref" in consumer_errors or "dry-run consumer report must not include execution" in consumer_errors, consumer_invalid
PY

echo "planningops local operator inbox artifact schema validation ok"
