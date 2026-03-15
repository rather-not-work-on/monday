#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

from operator_channel_cli_common import now_utc
from supervisor_goal_completion_payloads import (
    build_payload,
    load_json,
    resolve_goal_transition_report_path,
)


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


def main():
    args = parse_args()
    operator_report = load_json(args.operator_report_file)
    operator_summary = Path(args.operator_summary_file).read_text(encoding="utf-8")
    transition_report_path = resolve_goal_transition_report_path(operator_report, args.goal_transition_report_file)
    transition_report = load_json(transition_report_path)
    payload = build_payload(
        operator_report=operator_report,
        operator_summary_body=operator_summary,
        transition_report=transition_report,
        mode=args.mode,
        delivery_target=args.delivery_target,
        channel_kind=args.channel_kind,
        goal_transition_report_path=transition_report_path,
    )
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
