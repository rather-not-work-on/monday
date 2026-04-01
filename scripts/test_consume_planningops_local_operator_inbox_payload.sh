#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

cd "$ROOT_DIR"

planningops_validation="$TMP_DIR/platform-planningops/planningops/artifacts/validation"
mkdir -p "$planningops_validation"

day_packet_path="$planningops_validation/monday-local-operator-day-packet.json"
mission_packet_path="$planningops_validation/monday-local-mission-packet.json"
handoff_report_path="$planningops_validation/operator-handoff-report.json"
local_operator_report_path="$planningops_validation/monday-local-operator-stack-report.json"
ready_bridge_path="$planningops_validation/monday-local-operator-inbox-payload-ready.json"
blocked_bridge_path="$planningops_validation/monday-local-operator-inbox-payload-blocked.json"
output_root="$TMP_DIR/runtime-artifacts/integration/planningops-local-operator-inbox"
dry_report="$TMP_DIR/consumer-dry-run.json"
apply_ready_report="$TMP_DIR/consumer-apply-ready.json"
blocked_report="$TMP_DIR/consumer-apply-blocked.json"
runtime_profile_file="$TMP_DIR/runtime-profiles.json"
planner_runtime_file="$TMP_DIR/planner-runtime.json"
ready_bridge_validation="$TMP_DIR/ready-bridge-validation.json"
blocked_bridge_validation="$TMP_DIR/blocked-bridge-validation.json"
dry_report_validation="$TMP_DIR/dry-report-validation.json"
apply_report_validation="$TMP_DIR/apply-report-validation.json"
blocked_report_validation="$TMP_DIR/blocked-report-validation.json"

cat >"$mission_packet_path" <<'JSON'
{
  "generated_at_utc": "2026-04-01T10:00:00Z",
  "packet_id": "monday-local-mission-20260401T100000Z",
  "contract_ref": "planningops/contracts/monday-local-mission-packet-contract.md",
  "artifact_paths": {
    "latest_packet_path": "/tmp/latest-mission.json",
    "stamped_packet_path": "/tmp/stamped-mission.json",
    "output_path": null
  },
  "mission_packet": {
    "version": "v1",
    "packet_id": "monday-local-mission-20260401T100000Z",
    "mission_objective": "Resolve the next local monday runtime launch.",
    "mission_prompt": "Launch monday locally through the deterministic packet path.",
    "planner_profile": "local_ollama",
    "launch_mode": "direct",
    "local_model_route": "direct_local_ollama",
    "source_kind": "latest",
    "primary_action": "Launch the local monday runtime.",
    "preflight_command": "python3 planningops/scripts/run_monday_local_operator_stack.py --execution-mode direct --direct-profile local_ollama --probe-endpoints on --run-id monday-local-mission-20260401T100000Z",
    "monday_runtime_entrypoint_command": "cd ../monday && python3 scripts/run_local_runtime_smoke.py --profile local_ollama --run-id monday-local-mission-20260401T100000Z",
    "rollback_command": "cd ../platform-provider-gateway && bash scripts/litellm_stack_launcher.sh --mode start",
    "expected_evidence_outputs": [],
    "immediate_actions": [
      "Run the monday local runtime smoke."
    ],
    "target_lines": [
      "monday local runtime smoke"
    ],
    "local_validation_snapshot_status": "present",
    "local_validation_records": [],
    "local_validation_summary_lines": [
      "monday_local_operator_stack_report: freshness=fresh promotability=promotable"
    ],
    "local_validation_action_lines": [],
    "source_artifacts": {
      "handoff_report_path": "/tmp/handoff.json",
      "local_operator_report_path": "/tmp/operator.json"
    }
  }
}
JSON

cat >"$day_packet_path" <<JSON
{
  "generated_at_utc": "2026-04-01T10:05:00Z",
  "day_packet_id": "monday-local-day-20260401T100500Z",
  "contract_ref": "planningops/contracts/monday-local-operator-day-packet-contract.md",
  "artifact_paths": {
    "latest_packet_path": "$day_packet_path",
    "stamped_packet_path": "$TMP_DIR/stamped-day.json",
    "output_path": null
  },
  "day_packet": {
    "version": "v1",
    "day_packet_id": "monday-local-day-20260401T100500Z",
    "mission_packet_id": "monday-local-mission-20260401T100000Z",
    "headline": "Monday local operator day packet: Resolve the next local monday runtime launch.",
    "mission_objective": "Resolve the next local monday runtime launch.",
    "mission_prompt": "Launch monday locally through the deterministic packet path.",
    "planner_profile": "local_ollama",
    "launch_mode": "direct",
    "local_model_route": "direct_local_ollama",
    "first_action_command": "python3 planningops/scripts/run_monday_local_operator_stack.py --execution-mode direct --direct-profile local_ollama --probe-endpoints on --run-id monday-local-mission-20260401T100000Z",
    "monday_runtime_entrypoint_command": "cd ../monday && python3 scripts/run_local_runtime_smoke.py --profile local_ollama --run-id monday-local-mission-20260401T100000Z",
    "rollback_command": "cd ../platform-provider-gateway && bash scripts/litellm_stack_launcher.sh --mode start",
    "queue_lines": [],
    "target_lines": [
      "monday local runtime smoke"
    ],
    "immediate_actions": [
      "Run the monday local runtime smoke."
    ],
    "local_validation_snapshot_status": "present",
    "local_validation_records": [],
    "local_validation_summary_lines": [
      "monday_local_operator_stack_report: freshness=fresh promotability=promotable"
    ],
    "local_validation_action_lines": [],
    "attachments": [
      "$day_packet_path"
    ],
    "body_markdown": "## Monday Local Operator Day Packet",
    "source_artifacts": {
      "mission_packet_path": "$mission_packet_path",
      "handoff_report_path": "$handoff_report_path",
      "local_operator_report_path": "$local_operator_report_path"
    }
  }
}
JSON

cat >"$handoff_report_path" <<'JSON'
{
  "record": {
    "headline": "Launch monday locally.",
    "source_kind": "latest",
    "target_lines": [
      "monday local runtime smoke"
    ],
    "immediate_action_lines": [
      "Run the monday local runtime smoke."
    ]
  }
}
JSON

cat >"$local_operator_report_path" <<'JSON'
{
  "readiness": {
    "status": "ready"
  },
  "direct_profile": "local_ollama"
}
JSON

cat >"$ready_bridge_path" <<JSON
{
  "generated_at_utc": "2026-04-01T10:10:00Z",
  "bridge_id": "monday-local-inbox-20260401T101000Z",
  "contract_ref": "planningops/contracts/monday-local-operator-inbox-payload-bridge-contract.md",
  "artifact_paths": {
    "latest_payload_path": "$ready_bridge_path",
    "stamped_payload_path": "$TMP_DIR/stamped-ready-bridge.json",
    "output_path": null
  },
  "payload": {
    "title": "Monday local operator day packet: Resolve the next local monday runtime launch.",
    "status": "ready",
    "headline": "Monday local operator day packet: Resolve the next local monday runtime launch.",
    "priority_headline": "Monday local operator day packet: Resolve the next local monday runtime launch.",
    "operator_action": "launch_monday_local_runtime",
    "recommended_wait_minutes": 0,
    "retry_mode": "none",
    "needs_human_attention": false,
    "message_class_hint": "status_update",
    "planner_profile": "local_ollama",
    "launch_mode": "direct",
    "local_model_route": "direct_local_ollama",
    "day_packet_id": "monday-local-day-20260401T100500Z",
    "mission_packet_id": "monday-local-mission-20260401T100000Z",
    "mission_objective": "Resolve the next local monday runtime launch.",
    "first_action_command": "python3 planningops/scripts/run_monday_local_operator_stack.py --execution-mode direct --direct-profile local_ollama --probe-endpoints on --run-id monday-local-mission-20260401T100000Z",
    "monday_runtime_entrypoint_command": "cd ../monday && python3 scripts/run_local_runtime_smoke.py --profile local_ollama --run-id monday-local-mission-20260401T100000Z",
    "rollback_command": "cd ../platform-provider-gateway && bash scripts/litellm_stack_launcher.sh --mode start",
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
      "$ready_bridge_path",
      "$day_packet_path"
    ],
    "body_markdown": "## Monday Local Operator Inbox Payload",
    "bridge_contract_ref": "planningops/contracts/monday-local-operator-inbox-payload-bridge-contract.md",
    "source_artifacts": {
      "day_packet_path": "$day_packet_path",
      "mission_packet_path": "$mission_packet_path",
      "handoff_report_path": "$handoff_report_path",
      "local_operator_report_path": "$local_operator_report_path"
    }
  }
}
JSON

cat >"$blocked_bridge_path" <<JSON
{
  "generated_at_utc": "2026-04-01T10:15:00Z",
  "bridge_id": "monday-local-inbox-20260401T101500Z",
  "contract_ref": "planningops/contracts/monday-local-operator-inbox-payload-bridge-contract.md",
  "artifact_paths": {
    "latest_payload_path": "$blocked_bridge_path",
    "stamped_payload_path": "$TMP_DIR/stamped-blocked-bridge.json",
    "output_path": null
  },
  "payload": {
    "title": "Monday local operator day packet: Resolve the next local monday runtime launch.",
    "status": "blocked",
    "headline": "Monday local operator day packet: Resolve the next local monday runtime launch.",
    "priority_headline": "Monday local operator day packet: Resolve the next local monday runtime launch.",
    "operator_action": "launch_monday_local_runtime",
    "recommended_wait_minutes": 5,
    "retry_mode": "manual_recheck",
    "needs_human_attention": true,
    "message_class_hint": "decision_request",
    "planner_profile": "local_ollama",
    "launch_mode": "direct",
    "local_model_route": "direct_local_ollama",
    "day_packet_id": "monday-local-day-20260401T100500Z",
    "mission_packet_id": "monday-local-mission-20260401T100000Z",
    "mission_objective": "Resolve the next local monday runtime launch.",
    "first_action_command": "python3 planningops/scripts/run_monday_local_operator_stack.py --execution-mode direct --direct-profile local_ollama --probe-endpoints on --run-id monday-local-mission-20260401T100000Z",
    "monday_runtime_entrypoint_command": "cd ../monday && python3 scripts/run_local_runtime_smoke.py --profile local_ollama --run-id monday-local-mission-20260401T100000Z",
    "rollback_command": "cd ../platform-provider-gateway && bash scripts/litellm_stack_launcher.sh --mode start",
    "local_validation_snapshot_status": "present",
    "local_validation_summary_lines": [
      "monday_local_operator_stack_report: freshness=stale promotability=blocked"
    ],
    "local_validation_action_lines": [
      "refresh the promoted local operator stack report first"
    ],
    "queue_lines": [],
    "target_lines": [
      "monday local runtime smoke"
    ],
    "immediate_actions": [
      "Run the monday local runtime smoke."
    ],
    "attachments": [
      "$blocked_bridge_path",
      "$day_packet_path"
    ],
    "body_markdown": "## Monday Local Operator Inbox Payload",
    "bridge_contract_ref": "planningops/contracts/monday-local-operator-inbox-payload-bridge-contract.md",
    "source_artifacts": {
      "day_packet_path": "$day_packet_path",
      "mission_packet_path": "$mission_packet_path",
      "handoff_report_path": "$handoff_report_path",
      "local_operator_report_path": "$local_operator_report_path"
    }
  }
}
JSON

python3 "$ROOT_DIR/scripts/consume_planningops_local_operator_inbox_payload.py" \
  --inbox-payload-file "$ready_bridge_path" \
  --run-id "test-planningops-local-inbox-consumer" \
  --output-root "$output_root" \
  --output "$dry_report"

python3 "$ROOT_DIR/scripts/validate_planningops_local_operator_inbox_artifacts.py" \
  --kind bridge \
  --artifact "$ready_bridge_path" \
  --output "$ready_bridge_validation"

python3 "$ROOT_DIR/scripts/validate_planningops_local_operator_inbox_artifacts.py" \
  --kind consumer-report \
  --artifact "$dry_report" \
  --output "$dry_report_validation"

python3 - <<'PY' "$dry_report" "$output_root"
import json
import sys
from pathlib import Path

report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
output_root = Path(sys.argv[2])
launch_request_path = output_root / "test-planningops-local-inbox-consumer" / "launch-request.json"
mission_file_path = output_root / "test-planningops-local-inbox-consumer" / "mission.json"

assert report["verdict"] == "pass", report
assert report["reason_code"] == "dry_run", report
assert report["consumer_status"] == "ready_to_launch", report
assert report["bridge_id"] == "monday-local-inbox-20260401T101000Z", report
assert report["launch_request"]["can_launch"] is True, report
assert report["launch_request"]["block_reasons"] == [], report
assert report["launch_request"]["planner_profile"] == "local_ollama", report
assert report["launch_request"]["launch_mode"] == "direct", report
assert report["launch_request"]["local_model_route"] == "direct_local_ollama", report
assert report["launch_request"]["source_day_packet_id"] == "monday-local-day-20260401T100500Z", report
assert report["launch_request"]["source_mission_packet_id"] == "monday-local-mission-20260401T100000Z", report
assert report["launch_request"]["runtime_command_args"] == [
    "python3",
    "scripts/run_local_runtime_smoke.py",
    "--profile",
    "local_ollama",
    "--mission-file",
    str(mission_file_path.resolve()),
    "--run-id",
    "monday-local-inbox-20260401T101000Z",
    "--output",
    str((output_root / "test-planningops-local-inbox-consumer" / "local-runtime-smoke.json").resolve()),
], report
assert launch_request_path.exists(), launch_request_path
mission_file = json.loads(mission_file_path.read_text(encoding="utf-8"))
assert mission_file == {
    "missionId": "monday-local-mission-20260401T100000Z",
    "objective": "Resolve the next local monday runtime launch.",
}, mission_file
contract_text = Path("contracts/planningops-local-operator-inbox-consumer-contract.md").read_text(encoding="utf-8")
assert "launch_request" in contract_text, contract_text
assert "runtime_command_args" in contract_text, contract_text
PY

python3 - <<'PY' "$ready_bridge_validation" "$dry_report_validation"
import json
import sys
from pathlib import Path

ready_bridge_validation = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
dry_report_validation = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))

assert ready_bridge_validation["verdict"] == "pass", ready_bridge_validation
assert dry_report_validation["verdict"] == "pass", dry_report_validation
PY

cat >"$runtime_profile_file" <<'JSON'
{
  "active_profile": "local",
  "profiles": {
    "local": {
      "execution_mode": "local",
      "litellm_base_url": "http://127.0.0.1:4000",
      "langfuse_host": "http://127.0.0.1:3001"
    }
  }
}
JSON

cat >"$planner_runtime_file" <<'JSON'
{
  "config_version": 1,
  "active_profile": "local",
  "profiles": {
    "local": {
      "planner_engine": "legacy"
    }
  }
}
JSON

python3 - <<'PY' "$mission_packet_path" "$day_packet_path" "$ready_bridge_path"
import json
import sys
from pathlib import Path

mission_path = Path(sys.argv[1])
day_path = Path(sys.argv[2])
bridge_path = Path(sys.argv[3])

mission_doc = json.loads(mission_path.read_text(encoding="utf-8"))
mission_doc["mission_packet"]["planner_profile"] = "local"
mission_doc["mission_packet"]["launch_mode"] = "stack"
mission_doc["mission_packet"]["local_model_route"] = "gateway_first_local"
mission_doc["mission_packet"]["preflight_command"] = "python3 planningops/scripts/run_monday_local_operator_stack.py --execution-mode stack --probe-endpoints on --run-id monday-local-mission-20260401T100000Z"
mission_doc["mission_packet"]["monday_runtime_entrypoint_command"] = "cd ../monday && python3 scripts/run_local_runtime_smoke.py --profile local --run-id monday-local-mission-20260401T100000Z"
mission_path.write_text(json.dumps(mission_doc, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

day_doc = json.loads(day_path.read_text(encoding="utf-8"))
day_doc["day_packet"]["planner_profile"] = "local"
day_doc["day_packet"]["launch_mode"] = "stack"
day_doc["day_packet"]["local_model_route"] = "gateway_first_local"
day_doc["day_packet"]["first_action_command"] = "python3 planningops/scripts/run_monday_local_operator_stack.py --execution-mode stack --probe-endpoints on --run-id monday-local-mission-20260401T100000Z"
day_doc["day_packet"]["monday_runtime_entrypoint_command"] = "cd ../monday && python3 scripts/run_local_runtime_smoke.py --profile local --run-id monday-local-mission-20260401T100000Z"
day_path.write_text(json.dumps(day_doc, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

bridge_doc = json.loads(bridge_path.read_text(encoding="utf-8"))
bridge_doc["payload"]["planner_profile"] = "local"
bridge_doc["payload"]["launch_mode"] = "stack"
bridge_doc["payload"]["local_model_route"] = "gateway_first_local"
bridge_doc["payload"]["monday_runtime_entrypoint_command"] = "cd ../monday && python3 scripts/run_local_runtime_smoke.py --profile local --run-id monday-local-mission-20260401T100000Z"
bridge_path.write_text(json.dumps(bridge_doc, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
PY

python3 "$ROOT_DIR/scripts/consume_planningops_local_operator_inbox_payload.py" \
  --inbox-payload-file "$ready_bridge_path" \
  --run-id "test-planningops-local-inbox-consumer-apply" \
  --mode apply \
  --planner-runtime-config "$planner_runtime_file" \
  --runtime-profile-file "$runtime_profile_file" \
  --output-root "$output_root" \
  --output "$apply_ready_report"

python3 "$ROOT_DIR/scripts/validate_planningops_local_operator_inbox_artifacts.py" \
  --kind consumer-report \
  --artifact "$apply_ready_report" \
  --output "$apply_report_validation"

python3 - <<'PY' "$apply_ready_report" "$output_root" "$planner_runtime_file" "$runtime_profile_file"
import json
import sys
from pathlib import Path

report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
output_root = Path(sys.argv[2])
planner_runtime_file = Path(sys.argv[3]).resolve()
runtime_profile_file = Path(sys.argv[4]).resolve()
mission_file_path = output_root / "test-planningops-local-inbox-consumer-apply" / "mission.json"
runtime_report_path = output_root / "test-planningops-local-inbox-consumer-apply" / "local-runtime-smoke.json"

assert report["verdict"] == "pass", report
assert report["reason_code"] in {"ok", "tsx_fetch_unavailable_offline"}, report
assert report["consumer_status"] == "ready_to_launch", report
assert report["execution"]["attempted"] is True, report
assert report["execution"]["exit_code"] == 0, report
assert report["launch_request"]["can_launch"] is True, report
assert report["launch_request"]["planner_profile"] == "local", report
assert report["launch_request"]["launch_mode"] == "stack", report
assert report["launch_request"]["local_model_route"] == "gateway_first_local", report
assert report["launch_request"]["runtime_input_overrides"] == {
    "planner_runtime_config": str(planner_runtime_file),
    "runtime_profile_file": str(runtime_profile_file),
}, report
assert report["launch_request"]["runtime_command_args"] == [
    "python3",
    "scripts/run_local_runtime_smoke.py",
    "--profile",
    "local",
    "--mission-file",
    str(mission_file_path.resolve()),
    "--run-id",
    "monday-local-inbox-20260401T101000Z",
    "--output",
    str(runtime_report_path.resolve()),
    "--planner-runtime-config",
    str(planner_runtime_file),
    "--runtime-profile-file",
    str(runtime_profile_file),
], report
assert report["runtime_report_summary"]["report_path"] == str(runtime_report_path.resolve()), report
assert report["runtime_report_summary"]["verdict"] in {"pass", "skip"}, report
assert report["runtime_report_summary"]["reason_code"] in {"ok", "tsx_fetch_unavailable_offline"}, report
PY

python3 - <<'PY' "$apply_report_validation"
import json
import sys
from pathlib import Path

apply_report_validation = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert apply_report_validation["verdict"] == "pass", apply_report_validation
PY

python3 - <<'PY' "$blocked_bridge_path"
import json
import sys
from pathlib import Path

bridge_path = Path(sys.argv[1])
bridge_doc = json.loads(bridge_path.read_text(encoding="utf-8"))
bridge_doc["payload"]["planner_profile"] = "local"
bridge_doc["payload"]["launch_mode"] = "stack"
bridge_doc["payload"]["local_model_route"] = "gateway_first_local"
bridge_doc["payload"]["monday_runtime_entrypoint_command"] = "cd ../monday && python3 scripts/run_local_runtime_smoke.py --profile local --run-id monday-local-mission-20260401T100000Z"
bridge_path.write_text(json.dumps(bridge_doc, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
PY

python3 "$ROOT_DIR/scripts/consume_planningops_local_operator_inbox_payload.py" \
  --inbox-payload-file "$blocked_bridge_path" \
  --run-id "test-planningops-local-inbox-consumer-blocked" \
  --mode apply \
  --output-root "$output_root" \
  --output "$blocked_report"

python3 "$ROOT_DIR/scripts/validate_planningops_local_operator_inbox_artifacts.py" \
  --kind bridge \
  --artifact "$blocked_bridge_path" \
  --output "$blocked_bridge_validation"

python3 "$ROOT_DIR/scripts/validate_planningops_local_operator_inbox_artifacts.py" \
  --kind consumer-report \
  --artifact "$blocked_report" \
  --output "$blocked_report_validation"

python3 - <<'PY' "$blocked_report"
import json
import sys
from pathlib import Path

report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))

assert report["verdict"] == "blocked", report
assert report["reason_code"] == "launch_blocked", report
assert report["consumer_status"] == "blocked", report
assert report["launch_request"]["can_launch"] is False, report
assert report["launch_request"]["block_reasons"] == [
    "payload_status=blocked",
    "needs_human_attention",
    "local_validation_actions_present",
], report
assert report["execution"]["attempted"] is False, report
PY

python3 - <<'PY' "$blocked_bridge_validation" "$blocked_report_validation"
import json
import sys
from pathlib import Path

blocked_bridge_validation = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
blocked_report_validation = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))

assert blocked_bridge_validation["verdict"] == "pass", blocked_bridge_validation
assert blocked_report_validation["verdict"] == "pass", blocked_report_validation
PY

echo "planningops local operator inbox consumer contract ok"
