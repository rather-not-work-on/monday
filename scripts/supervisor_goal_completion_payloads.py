#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path

from operator_channel_cli_common import EMAIL_CHANNEL_KINDS, ensure_channel_kind


HANDOFF_CONTRACT_REF = "planningops/contracts/supervisor-operator-handoff-contract.md"


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


def resolve_goal_transition_report_path(operator_report: dict, explicit_path: str | None) -> str:
    explicit = str(explicit_path or "").strip()
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


def build_payload(
    *,
    operator_report: dict,
    operator_summary_body: str,
    transition_report: dict,
    mode: str,
    delivery_target: str | None,
    channel_kind: str | None,
    goal_transition_report_path: str,
) -> dict:
    goal_key = validate_operator_report(operator_report)
    achieved_at_utc = validate_transition_report(transition_report, goal_key)
    payload = {
        "messageClass": "goal_completed",
        "deliveryMode": mode,
        "goalKey": goal_key,
        "body": operator_summary_body,
        "achievedAtUtc": achieved_at_utc,
        "target": {
            "channelKind": resolve_channel_kind(operator_report, channel_kind),
            "deliveryTarget": str(delivery_target or "").strip(),
        },
        "metadata": {
            "handoff_contract_ref": HANDOFF_CONTRACT_REF,
            "summary_path": require_string(operator_report, "summary_path"),
            "goal_transition_report_path": goal_transition_report_path,
            "operator_action": optional_string(operator_report, "operator_action"),
            "headline": optional_string(operator_report, "headline"),
        },
    }
    ensure_channel_kind(payload, EMAIL_CHANNEL_KINDS)
    return payload
