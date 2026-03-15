#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path

from local_outbox_dispatch_common import ensure_runtime_artifact_boundary, repo_relative, repo_root, require_string, resolve_path
from runtime_evidence_contract import load_json


SCHEDULED_DELIVERY_HANDOFF_CONTRACT_REF = "planningops/contracts/scheduled-delivery-cycle-handoff-contract.md"
OPERATOR_ENTRYPOINT = "scripts/run_operator_message_delivery_cycle.py"
GOAL_COMPLETION_ENTRYPOINT = "scripts/run_goal_completion_delivery_cycle.py"
DELIVERY_WORK_ITEM_ROOT = Path("runtime-artifacts/messaging/scheduled-delivery-work-items")
ALLOWED_OPERATOR_MESSAGE_CLASSES = {"status_update", "decision_request", "blocked_report"}


def _require_optional_string(doc: dict, key: str) -> str | None:
    value = doc.get(key)
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        raise SystemExit(f"delivery work item field must be non-empty when present: {key}")
    return text


def resolve_delivery_entrypoint(work_item: dict) -> str:
    kind = require_string(work_item, "delivery_work_item_kind")
    message_class = require_string(work_item, "message_class")
    if kind == "operator_message_delivery":
        if message_class not in ALLOWED_OPERATOR_MESSAGE_CLASSES:
            raise SystemExit(f"operator_message_delivery message_class invalid: {message_class}")
        return OPERATOR_ENTRYPOINT
    if kind == "goal_completion_delivery":
        if message_class != "goal_completed":
            raise SystemExit("goal_completion_delivery message_class must be goal_completed")
        return GOAL_COMPLETION_ENTRYPOINT
    raise SystemExit(f"unsupported delivery_work_item_kind: {kind}")


def load_delivery_work_item(queue_item: dict, *, root: Path | None = None) -> dict:
    root = root or repo_root()
    queue_item_id = require_string(queue_item, "queue_item_id")
    goal_key = require_string(queue_item, "goal_key")
    work_payload_ref = require_string(queue_item, "work_payload_ref")
    work_payload_path = ensure_runtime_artifact_boundary(resolve_path(work_payload_ref, root=root).resolve(), root=root)
    work_item = load_json(work_payload_path, None)
    if work_item is None:
        raise SystemExit(f"delivery work item not found: {work_payload_path}")

    require_string(work_item, "delivery_work_item_kind")
    require_string(work_item, "message_class")
    if require_string(work_item, "queue_item_id") != queue_item_id:
        raise SystemExit("delivery work item queue_item_id mismatch")
    if require_string(work_item, "goal_key") != goal_key:
        raise SystemExit("delivery work item goal_key mismatch")
    source_artifact_ref = require_string(work_item, "source_artifact_ref")
    delivery_idempotency_key = require_string(work_item, "delivery_idempotency_key")

    selected_entrypoint = resolve_delivery_entrypoint(work_item)
    goal_transition_report_ref = _require_optional_string(work_item, "goal_transition_report_ref")
    if require_string(work_item, "delivery_work_item_kind") != "goal_completion_delivery" and goal_transition_report_ref:
        raise SystemExit("goal_transition_report_ref is allowed only for goal_completion_delivery")

    normalized = {
        "handoff_contract_ref": SCHEDULED_DELIVERY_HANDOFF_CONTRACT_REF,
        "queue_item_id": queue_item_id,
        "goal_key": goal_key,
        "delivery_work_item_kind": require_string(work_item, "delivery_work_item_kind"),
        "message_class": require_string(work_item, "message_class"),
        "source_work_payload_ref": repo_relative(work_payload_path, root),
        "source_artifact_ref": source_artifact_ref,
        "delivery_idempotency_key": delivery_idempotency_key,
        "selected_delivery_entrypoint": selected_entrypoint,
    }

    for key in ["delivery_target", "channel_kind", "thread_ref", "goal_transition_report_ref"]:
        value = _require_optional_string(work_item, key)
        if value is not None:
            normalized[key] = value

    return normalized


def maybe_load_delivery_work_item(queue_item: dict, *, root: Path | None = None) -> dict | None:
    root = root or repo_root()
    work_payload_ref = str(queue_item.get("work_payload_ref") or "").strip()
    if not work_payload_ref:
        return None
    work_payload_path = resolve_path(work_payload_ref, root=root).resolve()
    try:
        relative = work_payload_path.relative_to(root.resolve())
    except ValueError:
        return None
    if relative == DELIVERY_WORK_ITEM_ROOT or DELIVERY_WORK_ITEM_ROOT not in [Path(*relative.parts[: len(DELIVERY_WORK_ITEM_ROOT.parts)])]:
        return None
    return load_delivery_work_item(queue_item, root=root)
