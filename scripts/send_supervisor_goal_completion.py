#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

from operator_channel_cli_common import (
    EMAIL_CHANNEL_KINDS,
    ensure_channel_kind,
    now_utc,
)


HANDOFF_CONTRACT_REF = "planningops/contracts/supervisor-operator-handoff-contract.md"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Translate planningops supervisor goal-completion handoff artifacts into the monday goal-completion CLI baseline"
    )
    parser.add_argument("--operator-report-file", required=True)
    parser.add_argument("--operator-summary-file", required=True)
    parser.add_argument("--goal-transition-report-file", default=None)
    parser.add_argument("--delivery-target", default=None)
    parser.add_argument("--channel-kind", default=None)
    parser.add_argument("--profiles-config", default=None)
    parser.add_argument("--mode", choices=["dry-run", "apply"], default="dry-run")
    parser.add_argument("--output", default="runtime-artifacts/messaging/supervisor-goal-completion-report.json")
    return parser.parse_args()


def load_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def require_string(doc: dict, key: str) -> str:
    value = str(doc.get(key) or "").strip()
    if not value:
        raise SystemExit(f"missing required field: {key}")
    return value


def optional_string(doc: dict, key: str) -> str | None:
    value = str(doc.get(key) or "").strip()
    return value or None


def validate_operator_report(operator_report: dict) -> str:
    if require_string(operator_report, "handoff_contract_ref") != HANDOFF_CONTRACT_REF:
        raise SystemExit("handoff_contract_ref does not match supervisor operator handoff contract")
    if require_string(operator_report, "message_class_hint") != "goal_completed":
        raise SystemExit("message_class_hint must be goal_completed")
    return require_string(operator_report, "goal_key")


def resolve_goal_transition_report_path(args, operator_report: dict) -> str:
    explicit = str(args.goal_transition_report_file or "").strip()
    if explicit:
        return explicit
    return require_string(operator_report, "goal_transition_report_path")


def validate_transition_report(transition_report: dict, goal_key: str) -> str:
    transition_goal_key = require_string(transition_report, "goal_key")
    if transition_goal_key != goal_key:
        raise SystemExit("goal_key mismatch between operator report and goal transition report")
    if require_string(transition_report, "to_status") != "achieved":
        raise SystemExit("goal transition report must target achieved")
    return require_string(transition_report, "generated_at_utc")


def resolve_channel_kind(operator_report: dict, channel_kind_override: str | None) -> str:
    if channel_kind_override:
        return channel_kind_override.strip()
    terminal_channel = operator_report.get("terminal_notification_channel")
    if not isinstance(terminal_channel, dict):
        raise SystemExit("operator report missing terminal_notification_channel")
    value = str(terminal_channel.get("kind") or "").strip()
    if not value:
        raise SystemExit("terminal_notification_channel.kind missing")
    return value


def build_payload(args, operator_report: dict, operator_summary_body: str, transition_report: dict) -> dict:
    goal_key = validate_operator_report(operator_report)
    achieved_at_utc = validate_transition_report(transition_report, goal_key)
    payload = {
        "messageClass": "goal_completed",
        "deliveryMode": args.mode,
        "goalKey": goal_key,
        "body": operator_summary_body,
        "achievedAtUtc": achieved_at_utc,
        "target": {
            "channelKind": resolve_channel_kind(operator_report, args.channel_kind),
            "deliveryTarget": str(args.delivery_target or "").strip(),
        },
        "metadata": {
            "handoff_contract_ref": HANDOFF_CONTRACT_REF,
            "summary_path": require_string(operator_report, "summary_path"),
            "goal_transition_report_path": resolve_goal_transition_report_path(args, operator_report),
            "operator_action": optional_string(operator_report, "operator_action"),
            "headline": optional_string(operator_report, "headline"),
        },
    }
    ensure_channel_kind(payload, EMAIL_CHANNEL_KINDS)
    return payload


def main():
    args = parse_args()
    operator_report = load_json(args.operator_report_file)
    operator_summary = Path(args.operator_summary_file).read_text(encoding="utf-8")
    transition_report_path = resolve_goal_transition_report_path(args, operator_report)
    transition_report = load_json(transition_report_path)
    payload = build_payload(args, operator_report, operator_summary, transition_report)
    delegate_command = [
        sys.executable,
        str(Path(__file__).resolve().parent / "send_goal_completion_notification.py"),
        "--payload-json",
        json.dumps(payload, ensure_ascii=True),
        "--mode",
        args.mode,
        "--output",
        args.output,
    ]
    if args.profiles_config:
        delegate_command.extend(["--profiles-config", args.profiles_config])
    completed = subprocess.run(delegate_command, capture_output=True, text=True, cwd=Path(__file__).resolve().parent.parent)
    delegate_report = json.loads(Path(args.output).read_text(encoding="utf-8"))
    result = {
        "generated_at_utc": now_utc(),
        "script": str(Path(__file__).name),
        "operator_report_file": args.operator_report_file,
        "operator_summary_file": args.operator_summary_file,
        "goal_transition_report_file": transition_report_path,
        "payload": payload,
        "delegate_script": "scripts/send_goal_completion_notification.py",
        "delegate_report": delegate_report,
        "delivery_report": delegate_report.get("delivery_report"),
        "errors": list(delegate_report.get("errors") or []),
        "verdict": "pass" if completed.returncode == 0 else "fail",
    }
    Path(args.output).write_text(json.dumps(result, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    if completed.stdout.strip():
        result["delegate_stdout"] = completed.stdout.strip()
        Path(args.output).write_text(json.dumps(result, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    if completed.stderr.strip():
        result["delegate_stderr"] = completed.stderr.strip()
        Path(args.output).write_text(json.dumps(result, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    print(f"report written: {args.output}")
    print(
        "verdict="
        f"{result['verdict']} delivery_verdict="
        f"{(result.get('delivery_report') or {}).get('deliveryVerdict', '-')}"
    )
    return 0 if result["verdict"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
