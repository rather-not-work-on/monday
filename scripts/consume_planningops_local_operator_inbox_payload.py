#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import subprocess


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BRIDGE = REPO_ROOT / "../platform-planningops/planningops/artifacts/validation/monday-local-operator-inbox-payload.json"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "runtime-artifacts/integration/planningops-local-operator-inbox"
PLANNINGOPS_BRIDGE_CONTRACT_REF = "planningops/contracts/monday-local-operator-inbox-payload-bridge-contract.md"
CONSUMER_CONTRACT_REF = "contracts/planningops-local-operator-inbox-consumer-contract.md"


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def utc_timestamp_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


def require_dict(value: object, label: str) -> dict:
    if not isinstance(value, dict):
        raise SystemExit(f"{label} must be a JSON object")
    return value


def require_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SystemExit(f"{label} must be a non-empty string")
    return value.strip()


def require_bool(value: object, label: str) -> bool:
    if not isinstance(value, bool):
        raise SystemExit(f"{label} must be a boolean")
    return value


def require_int(value: object, label: str) -> int:
    if not isinstance(value, int):
        raise SystemExit(f"{label} must be an integer")
    return value


def normalize_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def resolve_existing_path(raw_path: object, label: str) -> Path:
    path = Path(require_string(raw_path, label))
    if not path.is_absolute():
        path = (REPO_ROOT / path).resolve()
    else:
        path = path.resolve()
    if not path.exists():
        raise SystemExit(f"{label} missing: {path}")
    return path


def resolve_optional_existing_path(raw_path: str | None, label: str) -> Path | None:
    if raw_path is None:
        return None
    path = Path(raw_path)
    if not path.is_absolute():
        path = (REPO_ROOT / path).resolve()
    else:
        path = path.resolve()
    if not path.exists():
        raise SystemExit(f"{label} missing: {path}")
    return path


def build_block_reasons(*, payload_status: str, needs_human_attention: bool, local_validation_action_lines: list[str]) -> list[str]:
    reasons: list[str] = []
    if payload_status != "ready":
        reasons.append(f"payload_status={payload_status}")
    if needs_human_attention:
        reasons.append("needs_human_attention")
    if local_validation_action_lines:
        reasons.append("local_validation_actions_present")
    return reasons


def build_runtime_command(
    *,
    planner_profile: str,
    mission_file_path: Path,
    run_id: str,
    runtime_report_path: Path,
    planner_runtime_config: Path | None,
    runtime_profile_file: Path | None,
) -> list[str]:
    command = [
        "python3",
        "scripts/run_local_runtime_smoke.py",
        "--profile",
        planner_profile,
        "--mission-file",
        str(mission_file_path.resolve()),
        "--run-id",
        run_id,
        "--output",
        str(runtime_report_path.resolve()),
    ]
    if planner_runtime_config is not None:
        command.extend(["--planner-runtime-config", str(planner_runtime_config.resolve())])
    if runtime_profile_file is not None:
        command.extend(["--runtime-profile-file", str(runtime_profile_file.resolve())])
    return command


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Consume the promoted PlanningOps local operator inbox payload and materialize a monday-native launch request."
    )
    parser.add_argument("--inbox-payload-file", default=str(DEFAULT_BRIDGE))
    parser.add_argument("--run-id", default=f"planningops-local-inbox-consumer-{utc_timestamp_slug()}")
    parser.add_argument("--mode", choices=("dry-run", "apply"), default="dry-run")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--planner-runtime-config", default=None)
    parser.add_argument("--runtime-profile-file", default=None)
    parser.add_argument("--output", default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    bridge_path = Path(args.inbox_payload_file)
    if not bridge_path.is_absolute():
        bridge_path = (REPO_ROOT / bridge_path).resolve()
    else:
        bridge_path = bridge_path.resolve()
    if not bridge_path.exists():
        raise SystemExit(f"inbox payload file missing: {bridge_path}")
    if not (REPO_ROOT / CONSUMER_CONTRACT_REF).exists():
        raise SystemExit(f"consumer contract missing: {CONSUMER_CONTRACT_REF}")

    output_root = Path(args.output_root)
    if not output_root.is_absolute():
        output_root = (REPO_ROOT / output_root).resolve()
    else:
        output_root = output_root.resolve()
    run_root = output_root / args.run_id
    launch_request_path = run_root / "launch-request.json"
    mission_file_path = run_root / "mission.json"
    runtime_report_path = run_root / "local-runtime-smoke.json"
    report_path = Path(args.output).resolve() if args.output else run_root / "consumer-report.json"
    planner_runtime_config_path = resolve_optional_existing_path(args.planner_runtime_config, "planner runtime config")
    runtime_profile_file_path = resolve_optional_existing_path(args.runtime_profile_file, "runtime profile file")

    bridge_doc = require_dict(load_json(bridge_path), "bridge payload")
    if require_string(bridge_doc.get("contract_ref"), "bridge contract ref") != PLANNINGOPS_BRIDGE_CONTRACT_REF:
        raise SystemExit("bridge contract ref does not match planningops inbox payload bridge contract")
    bridge_id = require_string(bridge_doc.get("bridge_id"), "bridge id")
    payload = require_dict(bridge_doc.get("payload"), "bridge payload.body")
    if require_string(payload.get("bridge_contract_ref"), "payload bridge contract ref") != PLANNINGOPS_BRIDGE_CONTRACT_REF:
        raise SystemExit("payload bridge contract ref does not match planningops inbox payload bridge contract")

    day_packet_path = resolve_existing_path(require_dict(payload.get("source_artifacts"), "payload source artifacts").get("day_packet_path"), "day packet path")
    mission_packet_path = resolve_existing_path(payload["source_artifacts"].get("mission_packet_path"), "mission packet path")
    handoff_report_path = resolve_existing_path(payload["source_artifacts"].get("handoff_report_path"), "handoff report path")
    local_operator_report_path = resolve_existing_path(payload["source_artifacts"].get("local_operator_report_path"), "local operator report path")

    day_packet_doc = require_dict(load_json(day_packet_path), "day packet")
    mission_packet_doc = require_dict(load_json(mission_packet_path), "mission packet")
    day_packet = require_dict(day_packet_doc.get("day_packet"), "day packet payload")
    mission_packet = require_dict(mission_packet_doc.get("mission_packet"), "mission packet payload")

    payload_status = require_string(payload.get("status"), "payload status")
    needs_human_attention = require_bool(payload.get("needs_human_attention"), "payload needs_human_attention")
    recommended_wait_minutes = require_int(payload.get("recommended_wait_minutes"), "payload recommended_wait_minutes")
    planner_profile = require_string(payload.get("planner_profile"), "payload planner_profile")
    launch_mode = require_string(payload.get("launch_mode"), "payload launch_mode")
    local_model_route = require_string(payload.get("local_model_route"), "payload local_model_route")
    first_action_command = require_string(payload.get("first_action_command"), "payload first_action_command")
    monday_runtime_entrypoint_command = require_string(
        payload.get("monday_runtime_entrypoint_command"),
        "payload monday_runtime_entrypoint_command",
    )
    rollback_command = require_string(payload.get("rollback_command"), "payload rollback_command")
    local_validation_snapshot_status = require_string(
        payload.get("local_validation_snapshot_status"),
        "payload local_validation_snapshot_status",
    )
    local_validation_summary_lines = normalize_string_list(payload.get("local_validation_summary_lines"))
    local_validation_action_lines = normalize_string_list(payload.get("local_validation_action_lines"))

    source_day_packet_id = require_string(day_packet_doc.get("day_packet_id"), "day packet id")
    source_mission_packet_id = require_string(mission_packet_doc.get("packet_id"), "mission packet id")
    mission_objective = require_string(mission_packet.get("mission_objective"), "mission objective")

    if payload.get("day_packet_id") and require_string(payload.get("day_packet_id"), "payload day_packet_id") != source_day_packet_id:
        raise SystemExit("payload day_packet_id mismatch with promoted day packet")
    if payload.get("mission_packet_id") and require_string(payload.get("mission_packet_id"), "payload mission_packet_id") != source_mission_packet_id:
        raise SystemExit("payload mission_packet_id mismatch with promoted mission packet")
    if planner_profile != require_string(mission_packet.get("planner_profile"), "mission planner profile"):
        raise SystemExit("planner_profile mismatch between payload and mission packet")
    if launch_mode != require_string(mission_packet.get("launch_mode"), "mission launch mode"):
        raise SystemExit("launch_mode mismatch between payload and mission packet")
    if local_model_route != require_string(mission_packet.get("local_model_route"), "mission local model route"):
        raise SystemExit("local_model_route mismatch between payload and mission packet")
    if rollback_command != require_string(mission_packet.get("rollback_command"), "mission rollback command"):
        raise SystemExit("rollback_command mismatch between payload and mission packet")
    if monday_runtime_entrypoint_command != require_string(
        mission_packet.get("monday_runtime_entrypoint_command"),
        "mission monday runtime entrypoint command",
    ):
        raise SystemExit("monday_runtime_entrypoint_command mismatch between payload and mission packet")

    mission_file = {
        "missionId": source_mission_packet_id,
        "objective": mission_objective,
    }
    write_json(mission_file_path, mission_file)

    block_reasons = build_block_reasons(
        payload_status=payload_status,
        needs_human_attention=needs_human_attention,
        local_validation_action_lines=local_validation_action_lines,
    )
    can_launch = not block_reasons
    runtime_command_args = build_runtime_command(
        planner_profile=planner_profile,
        mission_file_path=mission_file_path,
        run_id=bridge_id,
        runtime_report_path=runtime_report_path,
        planner_runtime_config=planner_runtime_config_path,
        runtime_profile_file=runtime_profile_file_path,
    )

    launch_request = {
        "source_bridge_id": bridge_id,
        "source_day_packet_id": source_day_packet_id,
        "source_mission_packet_id": source_mission_packet_id,
        "mission_objective": mission_objective,
        "planner_profile": planner_profile,
        "launch_mode": launch_mode,
        "local_model_route": local_model_route,
        "first_action_command": first_action_command,
        "monday_runtime_entrypoint_command": monday_runtime_entrypoint_command,
        "rollback_command": rollback_command,
        "recommended_wait_minutes": recommended_wait_minutes,
        "needs_human_attention": needs_human_attention,
        "local_validation_snapshot_status": local_validation_snapshot_status,
        "local_validation_summary_lines": local_validation_summary_lines,
        "local_validation_action_lines": local_validation_action_lines,
        "can_launch": can_launch,
        "block_reasons": block_reasons,
        "runtime_command_args": runtime_command_args,
        "source_artifacts": {
            "day_packet_path": str(day_packet_path.resolve()),
            "mission_packet_path": str(mission_packet_path.resolve()),
            "handoff_report_path": str(handoff_report_path.resolve()),
            "local_operator_report_path": str(local_operator_report_path.resolve()),
        },
    }
    if planner_runtime_config_path is not None or runtime_profile_file_path is not None:
        launch_request["runtime_input_overrides"] = {
            "planner_runtime_config": None
            if planner_runtime_config_path is None
            else str(planner_runtime_config_path.resolve()),
            "runtime_profile_file": None
            if runtime_profile_file_path is None
            else str(runtime_profile_file_path.resolve()),
        }
    write_json(launch_request_path, launch_request)

    report = {
        "generated_at_utc": now_utc(),
        "run_id": args.run_id,
        "consumer_contract_ref": CONSUMER_CONTRACT_REF,
        "source_bridge_path": str(bridge_path.resolve()),
        "bridge_id": bridge_id,
        "mode": args.mode,
        "verdict": "pass",
        "reason_code": "dry_run",
        "consumer_status": "ready_to_launch" if can_launch else "blocked",
        "artifact_paths": {
            "launch_request_path": str(launch_request_path.resolve()),
            "mission_file_path": str(mission_file_path.resolve()),
            "runtime_report_path": str(runtime_report_path.resolve()),
            "report_path": str(report_path.resolve()),
        },
        "launch_request": launch_request,
    }

    if args.mode == "apply":
        if not can_launch:
            report["verdict"] = "blocked"
            report["reason_code"] = "launch_blocked"
            report["execution"] = {
                "attempted": False,
                "command_args": runtime_command_args,
            }
        else:
            completed = subprocess.run(runtime_command_args, cwd=REPO_ROOT, capture_output=True, text=True)
            runtime_report = None
            if runtime_report_path.exists():
                runtime_report = require_dict(load_json(runtime_report_path), "runtime report")
            report["execution"] = {
                "attempted": True,
                "command_args": runtime_command_args,
                "exit_code": completed.returncode,
                "stdout": completed.stdout.strip(),
                "stderr": completed.stderr.strip(),
            }
            if completed.returncode != 0:
                report["verdict"] = "fail"
                report["reason_code"] = "runtime_launch_failed"
            elif runtime_report is None:
                report["verdict"] = "fail"
                report["reason_code"] = "runtime_report_missing"
            else:
                runtime_verdict = require_string(runtime_report.get("verdict"), "runtime report verdict")
                runtime_reason_code = require_string(runtime_report.get("reason_code"), "runtime report reason_code")
                report["runtime_report_summary"] = {
                    "verdict": runtime_verdict,
                    "reason_code": runtime_reason_code,
                    "report_path": str(runtime_report_path.resolve()),
                }
                if runtime_verdict in {"pass", "skip"}:
                    report["verdict"] = "pass"
                    report["reason_code"] = runtime_reason_code
                else:
                    report["verdict"] = "fail"
                    report["reason_code"] = runtime_reason_code

    write_json(report_path, report)
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0 if report["verdict"] in {"pass", "blocked"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
