#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from operator_channel_cli_common import (
    SLACK_CHANNEL_KINDS,
    build_delivery_report,
    build_operator_idempotency_key,
    ensure_channel_kind,
    now_utc,
    write_report,
)


HANDOFF_CONTRACT_REF = "planningops/contracts/supervisor-operator-handoff-contract.md"
VALID_STATUS_MESSAGE_CLASSES = {"status_update", "decision_request", "blocked_report"}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Translate planningops supervisor status handoff artifacts into the monday operator-message CLI baseline"
    )
    parser.add_argument("--operator-report-file", required=True)
    parser.add_argument("--inbox-payload-file", required=True)
    parser.add_argument("--delivery-target", required=True)
    parser.add_argument("--channel-kind", default=None)
    parser.add_argument("--thread-ref", default=None)
    parser.add_argument("--mode", choices=["dry-run", "apply"], default="dry-run")
    parser.add_argument("--output", default="runtime-artifacts/messaging/supervisor-status-update-report.json")
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


def validate_handoff_contract(operator_report: dict, inbox_payload: dict) -> None:
    operator_ref = require_string(operator_report, "handoff_contract_ref")
    inbox_ref = require_string(inbox_payload, "handoff_contract_ref")
    if operator_ref != HANDOFF_CONTRACT_REF or inbox_ref != HANDOFF_CONTRACT_REF:
        raise SystemExit("handoff_contract_ref does not match supervisor operator handoff contract")
    if operator_ref != inbox_ref:
        raise SystemExit("handoff contract refs must match between operator report and inbox payload")


def validate_goal_key(operator_report: dict, inbox_payload: dict) -> str:
    operator_goal_key = require_string(operator_report, "goal_key")
    inbox_goal_key = require_string(inbox_payload, "goal_key")
    if operator_goal_key != inbox_goal_key:
        raise SystemExit("goal_key mismatch between operator report and inbox payload")
    return operator_goal_key


def validate_message_class(operator_report: dict, inbox_payload: dict) -> str:
    operator_hint = require_string(operator_report, "message_class_hint")
    inbox_hint = require_string(inbox_payload, "message_class_hint")
    if operator_hint != inbox_hint:
        raise SystemExit("message_class_hint mismatch between operator report and inbox payload")
    if operator_hint not in VALID_STATUS_MESSAGE_CLASSES:
        raise SystemExit(f"message_class_hint invalid for status delivery: {operator_hint}")
    return operator_hint


def resolve_channel_kind(operator_report: dict, channel_kind_override: str | None) -> str:
    if channel_kind_override:
        return channel_kind_override.strip()
    primary = operator_report.get("primary_operator_channel")
    if not isinstance(primary, dict):
        raise SystemExit("operator report missing primary_operator_channel")
    value = str(primary.get("kind") or "").strip()
    if not value:
        raise SystemExit("primary_operator_channel.kind missing")
    return value


def build_payload(args, operator_report: dict, inbox_payload: dict) -> dict:
    goal_key = validate_goal_key(operator_report, inbox_payload)
    message_class = validate_message_class(operator_report, inbox_payload)
    payload = {
        "messageClass": message_class,
        "deliveryMode": args.mode,
        "goalKey": goal_key,
        "body": require_string(inbox_payload, "body_markdown"),
        "runId": require_string(operator_report, "run_id"),
        "target": {
            "channelKind": resolve_channel_kind(operator_report, args.channel_kind),
            "deliveryTarget": args.delivery_target,
        },
        "metadata": {
            "supervisor_status": optional_string(operator_report, "status"),
            "operator_action": optional_string(operator_report, "operator_action"),
            "summary_path": require_string(operator_report, "summary_path"),
            "handoff_contract_ref": HANDOFF_CONTRACT_REF,
            "attachments": list(inbox_payload.get("attachments") or []),
        },
    }
    goal_transition_report_path = optional_string(operator_report, "goal_transition_report_path")
    if goal_transition_report_path:
        payload["metadata"]["goal_transition_report_path"] = goal_transition_report_path
    cycle_report_path = optional_string(operator_report, "cycle_report_path")
    if cycle_report_path:
        payload["metadata"]["cycle_report_path"] = cycle_report_path
    if args.thread_ref:
        payload["target"]["threadRef"] = args.thread_ref
    ensure_channel_kind(payload, SLACK_CHANNEL_KINDS)
    return payload


def main():
    args = parse_args()
    operator_report = load_json(args.operator_report_file)
    inbox_payload = load_json(args.inbox_payload_file)
    validate_handoff_contract(operator_report, inbox_payload)
    payload = build_payload(args, operator_report, inbox_payload)
    report = build_delivery_report(
        payload,
        delivery_verdict="dry_run" if args.mode == "dry-run" else "blocked",
        idempotency_key=build_operator_idempotency_key(payload),
        timestamp_utc=now_utc(),
    )
    result = {
        "generated_at_utc": now_utc(),
        "script": str(Path(__file__).name),
        "operator_report_file": args.operator_report_file,
        "inbox_payload_file": args.inbox_payload_file,
        "payload": payload,
        "delivery_report": report,
        "errors": [] if args.mode == "dry-run" else ["operator_transport_not_configured"],
        "verdict": "pass" if args.mode == "dry-run" else "fail",
    }
    write_report(args.output, result)
    print(f"report written: {args.output}")
    print(f"verdict={result['verdict']} delivery_verdict={report['deliveryVerdict']}")
    return 0 if result["verdict"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
