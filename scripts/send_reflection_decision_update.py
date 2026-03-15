#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from reflection_action_delivery_payloads import (
    HANDOFF_CONTRACT_REF,
    build_status_payload,
    load_json,
    require_string,
    validate_action,
)


def now_utc() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def parse_args():
    parser = argparse.ArgumentParser(
        description="Translate planningops reflection action artifacts into monday operator-channel delivery CLIs"
    )
    parser.add_argument("--action-file", required=True)
    parser.add_argument("--delivery-target", default=None)
    parser.add_argument("--channel-kind", default=None)
    parser.add_argument("--thread-ref", default=None)
    parser.add_argument("--profiles-config", default=None)
    parser.add_argument("--mode", choices=["dry-run", "apply"], default="dry-run")
    parser.add_argument("--output", default="runtime-artifacts/messaging/reflection-decision-update-report.json")
    return parser.parse_args()


def build_completion_payload(action: dict, args) -> dict:
    if require_string(action, "message_class_hint") != "goal_completed":
        raise SystemExit("goal-completion delivery requires message_class_hint=goal_completed")
    transition_report_path = require_string(action, "goal_transition_report_path")
    if transition_report_path == "-":
        raise SystemExit("goal-completion delivery requires goal_transition_report_path")
    transition_report = load_json(transition_report_path)
    payload = {
        "messageClass": "goal_completed",
        "deliveryMode": args.mode,
        "goalKey": require_string(action, "active_goal_key"),
        "body": require_string(action, "handoff_summary"),
        "achievedAtUtc": require_string(transition_report, "generated_at_utc"),
        "target": {
            "channelKind": (args.channel_kind or require_string(action, "operator_channel_kind")).strip(),
            "deliveryTarget": str(args.delivery_target or "").strip(),
        },
        "metadata": {
            "handoffContractRef": HANDOFF_CONTRACT_REF,
            "actionKind": require_string(action, "action_kind"),
            "reflectionDecision": require_string(action, "reflection_decision"),
            "decisionReason": require_string(action, "decision_reason"),
            "controlPlaneAction": require_string(action, "control_plane_action"),
            "sourcePacketRef": require_string(action, "source_packet_ref"),
            "reflectionEvaluationRef": require_string(action, "reflection_evaluation_ref"),
            "goalTransitionReportPath": transition_report_path,
        },
    }
    return payload


def invoke_delegate(script_name: str, payload: dict, output_path: Path, profiles_config: str | None) -> tuple[int, dict]:
    command = [
        sys.executable,
        str(Path(__file__).resolve().parent / script_name),
        "--payload-json",
        json.dumps(payload, ensure_ascii=True),
        "--output",
        str(output_path),
    ]
    if profiles_config:
        command.extend(["--profiles-config", profiles_config])
    result = subprocess.run(command, capture_output=True, text=True, cwd=Path(__file__).resolve().parent.parent)
    report = load_json(str(output_path))
    if result.stdout.strip():
        report["delegate_stdout"] = result.stdout.strip()
    if result.stderr.strip():
        report["delegate_stderr"] = result.stderr.strip()
    return result.returncode, report


def write_report(path: str, payload: dict) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


def main():
    args = parse_args()
    action = load_json(args.action_file)
    validate_action(action)

    if not action["delivery_required"]:
        result = {
            "generated_at_utc": now_utc(),
            "script": str(Path(__file__).name),
            "action_file": args.action_file,
            "delivery_required": False,
            "delivery_skipped": True,
            "skip_reason": "delivery_not_required",
            "payload": None,
            "delegate_script": None,
            "delegate_report": None,
            "errors": [],
            "verdict": "pass",
        }
        write_report(args.output, result)
        print(f"report written: {args.output}")
        print("verdict=pass delivery_skipped=true")
        return 0

    with tempfile.TemporaryDirectory() as td:
        delegate_output = Path(td) / "delegate-report.json"
        if action["message_class_hint"] == "goal_completed":
            payload = build_completion_payload(action, args)
            delegate_script = "send_goal_completion_notification.py"
        else:
            payload = build_status_payload(
                action,
                mode=args.mode,
                delivery_target=args.delivery_target,
                channel_kind=args.channel_kind,
                thread_ref=args.thread_ref,
            )
            delegate_script = "send_operator_message.py"

        rc, delegate_report = invoke_delegate(delegate_script, payload, delegate_output, args.profiles_config)
        result = {
            "generated_at_utc": now_utc(),
            "script": str(Path(__file__).name),
            "action_file": args.action_file,
            "delivery_required": True,
            "delivery_skipped": False,
            "payload": payload,
            "delegate_script": f"scripts/{delegate_script}",
            "delegate_report": delegate_report,
            "errors": list(delegate_report.get("errors") or []),
            "verdict": "pass" if rc == 0 else "fail",
        }
        write_report(args.output, result)
        print(f"report written: {args.output}")
        print(
            "verdict="
            f"{result['verdict']} delivery_verdict="
            f"{delegate_report.get('delivery_report', {}).get('deliveryVerdict', '-')}"
        )
        return 0 if rc == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
