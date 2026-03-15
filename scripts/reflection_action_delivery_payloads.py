#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path


HANDOFF_CONTRACT_REF = "planningops/contracts/reflection-action-handoff-contract.md"
STATUS_MESSAGE_CLASSES = {"status_update", "decision_request", "blocked_report"}


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


def validate_action(action: dict) -> None:
    if require_string(action, "handoff_contract_ref") != HANDOFF_CONTRACT_REF:
        raise SystemExit("handoff_contract_ref does not match reflection action handoff contract")
    if require_string(action, "verdict") != "pass":
        raise SystemExit("action artifact verdict must be pass")
    require_string(action, "active_goal_key")
    require_string(action, "queue_item_id")
    require_string(action, "worker_run_id")
    require_string(action, "reflection_decision")
    require_string(action, "action_kind")
    require_string(action, "message_class_hint")
    operator_channel_role = require_string(action, "operator_channel_role")
    if operator_channel_role not in {"none", "primary_operator_channel", "terminal_notification_channel"}:
        raise SystemExit(f"operator_channel_role invalid: {operator_channel_role}")
    delivery_required = action.get("delivery_required")
    if not isinstance(delivery_required, bool):
        raise SystemExit("delivery_required must be boolean")
    if delivery_required:
        require_string(action, "operator_channel_kind")
        require_string(action, "operator_channel_execution_repo")
        require_string(action, "operator_channel_adapter_contract_ref")
        if require_string(action, "operator_channel_execution_repo") != "rather-not-work-on/monday":
            raise SystemExit("operator_channel_execution_repo must be rather-not-work-on/monday")
    else:
        if optional_string(action, "operator_channel_kind") not in {None, "-"}:
            raise SystemExit("non-delivery action must not project a concrete channel kind")


def build_status_payload(action: dict, *, mode: str, delivery_target: str | None, channel_kind: str | None, thread_ref: str | None) -> dict:
    message_class = require_string(action, "message_class_hint")
    if message_class not in STATUS_MESSAGE_CLASSES:
        raise SystemExit(f"message_class_hint invalid for status delivery: {message_class}")
    payload = {
        "messageClass": message_class,
        "deliveryMode": mode,
        "goalKey": require_string(action, "active_goal_key"),
        "body": require_string(action, "handoff_summary"),
        "runId": require_string(action, "worker_run_id"),
        "taskId": require_string(action, "queue_item_id"),
        "target": {
            "channelKind": (channel_kind or require_string(action, "operator_channel_kind")).strip(),
            "deliveryTarget": str(delivery_target or "").strip(),
        },
        "metadata": {
            "handoffContractRef": HANDOFF_CONTRACT_REF,
            "actionKind": require_string(action, "action_kind"),
            "reflectionDecision": require_string(action, "reflection_decision"),
            "decisionReason": require_string(action, "decision_reason"),
            "controlPlaneAction": require_string(action, "control_plane_action"),
            "sourcePacketRef": require_string(action, "source_packet_ref"),
            "reflectionEvaluationRef": require_string(action, "reflection_evaluation_ref"),
        },
    }
    goal_transition_report_path = optional_string(action, "goal_transition_report_path")
    if goal_transition_report_path and goal_transition_report_path != "-":
        payload["metadata"]["goalTransitionReportPath"] = goal_transition_report_path
    if thread_ref:
        payload["target"]["threadRef"] = thread_ref
    return payload

