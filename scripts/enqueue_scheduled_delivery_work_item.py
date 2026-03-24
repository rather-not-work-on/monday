#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from local_outbox_dispatch_common import (
    apply_operator_handoff_bundle_sidecar_paths,
    repo_relative,
    repo_root,
    resolve_priority_cta_command,
)
from reflection_action_delivery_payloads import (
    build_status_payload,
    load_json as load_reflection_action,
    validate_action,
)
from runtime_queue_store import connect, load_validator, seed_queue_items, save_json
from supervisor_goal_completion_payloads import (
    build_payload as build_goal_completion_payload,
    load_json as load_goal_json,
    resolve_goal_transition_report_path,
)

QUEUE_ITEM_SCHEMA = Path("../platform-contracts/schemas/runtime-scheduler-queue-item.schema.json")
SCHEDULED_DELIVERY_HANDOFF_CONTRACT_REF = "planningops/contracts/scheduled-delivery-cycle-handoff-contract.md"
SCHEDULED_QUEUE_ITEM_REF_CONTRACT = "monday/contracts/runtime-scheduler-queue-item-ref.v1"
WORK_ITEM_ROOT = Path("runtime-artifacts/messaging/scheduled-delivery-work-items")
PAYLOAD_ROOT = Path("runtime-artifacts/messaging/scheduled-delivery-payloads")
QUEUE_ITEM_REF_ROOT = Path("runtime-artifacts/scheduler-queue/item-refs")


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Admit a reflection-action or supervisor handoff into monday scheduled delivery queue items"
    )
    parser.add_argument("--reflection-action-file", default=None)
    parser.add_argument("--operator-report-file", default=None)
    parser.add_argument("--operator-summary-file", default=None)
    parser.add_argument("--goal-transition-report-file", default=None)
    parser.add_argument("--schedule-key", required=True)
    parser.add_argument("--mode", choices=["apply", "dry-run"], default="apply")
    parser.add_argument("--queue-db", required=True)
    parser.add_argument("--queue-item-schema", default=str(QUEUE_ITEM_SCHEMA))
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def list_of_strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if text:
            result.append(text)
    return result


def resolve_remediation_fields(metadata: dict[str, Any]) -> tuple[list[str], str | None, str | None]:
    federated = metadata.get("federated_ci_summary")
    remediation_commands: list[str] = []
    primary_remediation_command: str | None = None
    if isinstance(federated, dict):
        remediation_commands = list_of_strings(federated.get("remediation_commands"))
        primary_remediation_command = str(federated.get("primary_remediation_command") or "").strip() or None
        if primary_remediation_command and primary_remediation_command not in remediation_commands:
            remediation_commands = [primary_remediation_command, *remediation_commands]
        if not primary_remediation_command and remediation_commands:
            primary_remediation_command = remediation_commands[0]
    first_action_command = resolve_priority_cta_command(
        metadata.get("first_action_command"),
        metadata.get("priority_cta_command"),
        primary_remediation_command,
    )
    return remediation_commands, primary_remediation_command, first_action_command


def write_payload_artifact(payload: dict[str, Any], *, queue_item_id: str, root: Path) -> str:
    path = root / PAYLOAD_ROOT / f"{queue_item_id}.json"
    save_json(path, payload)
    return repo_relative(path, root)


def write_work_item_artifact(work_item: dict[str, Any], *, queue_item_id: str, root: Path) -> str:
    path = root / WORK_ITEM_ROOT / f"{queue_item_id}.json"
    save_json(path, work_item)
    return repo_relative(path, root)


def write_queue_ref_artifact(queue_item: dict[str, Any], *, queue_item_id: str, root: Path) -> str:
    ref_payload = {
        "generated_at_utc": now_utc(),
        "contract_ref": SCHEDULED_QUEUE_ITEM_REF_CONTRACT,
        "queue_item_id": queue_item_id,
        "goal_key": queue_item["goal_key"],
        "schedule_key": queue_item["schedule_key"],
        "state": queue_item["state"],
        "queue_db_locator": "sqlite-runtime-queue",
    }
    path = root / QUEUE_ITEM_REF_ROOT / f"{queue_item_id}.json"
    save_json(path, ref_payload)
    return repo_relative(path, root)


def assign_optional_string(doc: dict[str, Any], key: str, value: object) -> None:
    text = str(value or "").strip()
    if text:
        doc[key] = text


def build_from_reflection(args: argparse.Namespace, *, root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], str]:
    action = load_reflection_action(args.reflection_action_file)
    validate_action(action)
    if not action.get("delivery_required"):
        raise SystemExit("reflection action must require delivery for scheduled queue admission")

    payload = build_status_payload(
        action,
        mode="dry-run",
        delivery_target=None,
        channel_kind=None,
        thread_ref=None,
    )
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        raise SystemExit("reflection payload metadata missing")
    target = payload.get("target")
    if not isinstance(target, dict):
        raise SystemExit("reflection payload target missing")

    queue_item_id = str(action.get("queue_item_id") or "").strip()
    if not queue_item_id:
        raise SystemExit("reflection action queue_item_id missing")
    goal_key = str(action.get("active_goal_key") or "").strip()
    if not goal_key:
        raise SystemExit("reflection action active_goal_key missing")

    remediation_commands, primary_remediation_command, first_action_command = resolve_remediation_fields(metadata)
    delivery_idempotency_key = ":".join(
        [
            "scheduled",
            "operator",
            goal_key,
            str(target.get("channelKind") or "-").strip() or "-",
            str(target.get("deliveryTarget") or "-").strip() or "-",
            queue_item_id,
        ]
    )

    payload_ref = write_payload_artifact(payload, queue_item_id=queue_item_id, root=root)
    work_item = {
        "queue_item_id": queue_item_id,
        "goal_key": goal_key,
        "delivery_work_item_kind": "operator_message_delivery",
        "message_class": str(payload.get("messageClass") or "").strip(),
        "source_artifact_ref": payload_ref,
        "payload_ref": payload_ref,
        "delivery_idempotency_key": delivery_idempotency_key,
        "primary_remediation_command": primary_remediation_command,
        "first_action_command": first_action_command,
        "priority_cta_command": first_action_command or primary_remediation_command,
        "remediation_commands": remediation_commands,
    }
    assign_optional_string(work_item, "delivery_target", target.get("deliveryTarget"))
    assign_optional_string(work_item, "channel_kind", target.get("channelKind"))
    assign_optional_string(work_item, "thread_ref", target.get("threadRef"))
    work_item["operator_handoff_validation_path"] = str(metadata.get("operator_handoff_validation_path") or "").strip()
    apply_operator_handoff_bundle_sidecar_paths(work_item, metadata)
    work_item_ref = write_work_item_artifact(work_item, queue_item_id=queue_item_id, root=root)

    queue_item = {
        "queue_item_id": queue_item_id,
        "goal_key": goal_key,
        "schedule_key": args.schedule_key,
        "state": "ready",
        "idempotency_key": delivery_idempotency_key,
        "priority_class": "standard",
        "retry_budget": {"max_attempts": 3, "backoff_profile": "exponential"},
        "retry_budget_remaining": 3,
        "attempt_count": 0,
        "dependency_keys": [],
        "escalation_policy_ref": "planningops/contracts/escalation-gate-contract.md",
        "completion_policy_ref": "planningops/contracts/goal-completion-contract.md",
        "target_repo": "rather-not-work-on/monday",
        "work_payload_ref": work_item_ref,
    }
    report_fields = {
        "delivery_work_item_kind": "operator_message_delivery",
        "selected_delivery_entrypoint": "scripts/run_operator_message_delivery_cycle.py",
        "delivery_idempotency_key": delivery_idempotency_key,
        "goal_key": goal_key,
        "primary_remediation_command": primary_remediation_command,
        "first_action_command": first_action_command or primary_remediation_command,
        "priority_cta_command": first_action_command or primary_remediation_command,
        "operator_handoff_validation_path": str(work_item.get("operator_handoff_validation_path") or "").strip(),
        "remediation_commands": remediation_commands,
    }
    apply_operator_handoff_bundle_sidecar_paths(report_fields, work_item)
    return payload, work_item, queue_item, work_item_ref


def build_from_goal_completion(args: argparse.Namespace, *, root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], str]:
    if not args.operator_report_file or not args.operator_summary_file:
        raise SystemExit("both --operator-report-file and --operator-summary-file are required")

    operator_report = load_goal_json(args.operator_report_file)
    operator_summary = Path(args.operator_summary_file).read_text(encoding="utf-8")
    goal_transition_report_path = resolve_goal_transition_report_path(operator_report, args.goal_transition_report_file)
    transition_report = load_goal_json(goal_transition_report_path)

    payload = build_goal_completion_payload(
        operator_report=operator_report,
        operator_summary_body=operator_summary,
        transition_report=transition_report,
        mode="dry-run",
        delivery_target=None,
        channel_kind=None,
        goal_transition_report_path=goal_transition_report_path,
    )
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        raise SystemExit("goal completion payload metadata missing")
    target = payload.get("target")
    if not isinstance(target, dict):
        raise SystemExit("goal completion payload target missing")

    goal_key = str(payload.get("goalKey") or "").strip()
    if not goal_key:
        raise SystemExit("goal completion payload goalKey missing")
    queue_item_id = f"goal-completion-{goal_key}-{str(payload.get('achievedAtUtc') or '').replace(':', '-').replace('+', '-')}"
    queue_item_id = queue_item_id.replace(" ", "-")

    remediation_commands, primary_remediation_command, first_action_command = resolve_remediation_fields(metadata)
    priority_cta_command = str(metadata.get("priority_cta_command") or "").strip() or first_action_command or primary_remediation_command
    first_action_command = priority_cta_command or first_action_command
    if not remediation_commands and first_action_command:
        remediation_commands = [first_action_command]
    delivery_idempotency_key = ":".join(
        [
            "scheduled",
            "goal-completion",
            goal_key,
            str(payload.get("achievedAtUtc") or "-").strip() or "-",
            str(target.get("channelKind") or "-").strip() or "-",
            str(target.get("deliveryTarget") or "-").strip() or "-",
        ]
    )

    payload_ref = write_payload_artifact(payload, queue_item_id=queue_item_id, root=root)
    work_item = {
        "queue_item_id": queue_item_id,
        "goal_key": goal_key,
        "delivery_work_item_kind": "goal_completion_delivery",
        "message_class": str(payload.get("messageClass") or "").strip(),
        "source_artifact_ref": payload_ref,
        "payload_ref": payload_ref,
        "delivery_idempotency_key": delivery_idempotency_key,
        "headline": str(metadata.get("priority_headline") or metadata.get("headline") or "").strip(),
        "priority_headline": str(metadata.get("priority_headline") or metadata.get("headline") or "").strip(),
        "priority_summary_markdown": str(metadata.get("priority_summary_markdown") or "").strip(),
        "first_action_command": first_action_command or primary_remediation_command,
        "priority_cta_command": priority_cta_command,
        "primary_remediation_command": primary_remediation_command,
        "remediation_commands": remediation_commands,
    }
    assign_optional_string(work_item, "delivery_target", target.get("deliveryTarget"))
    assign_optional_string(work_item, "channel_kind", target.get("channelKind"))
    assign_optional_string(work_item, "goal_transition_report_ref", metadata.get("goal_transition_report_path"))
    work_item["operator_handoff_validation_path"] = str(metadata.get("operator_handoff_validation_path") or "").strip()
    apply_operator_handoff_bundle_sidecar_paths(work_item, metadata)
    work_item_ref = write_work_item_artifact(work_item, queue_item_id=queue_item_id, root=root)

    queue_item = {
        "queue_item_id": queue_item_id,
        "goal_key": goal_key,
        "schedule_key": args.schedule_key,
        "state": "ready",
        "idempotency_key": delivery_idempotency_key,
        "priority_class": "standard",
        "retry_budget": {"max_attempts": 3, "backoff_profile": "exponential"},
        "retry_budget_remaining": 3,
        "attempt_count": 0,
        "dependency_keys": [],
        "escalation_policy_ref": "planningops/contracts/escalation-gate-contract.md",
        "completion_policy_ref": "planningops/contracts/goal-completion-contract.md",
        "target_repo": "rather-not-work-on/monday",
        "work_payload_ref": work_item_ref,
    }
    return payload, work_item, queue_item, work_item_ref


def main() -> int:
    args = parse_args()
    root = repo_root()

    use_reflection = bool(args.reflection_action_file)
    use_goal_completion = bool(args.operator_report_file or args.operator_summary_file)
    if use_reflection == use_goal_completion:
        raise SystemExit("provide exactly one source: reflection action or supervisor goal completion handoff")

    if use_reflection:
        _payload, work_item, queue_item, work_item_ref = build_from_reflection(args, root=root)
    else:
        _payload, work_item, queue_item, work_item_ref = build_from_goal_completion(args, root=root)

    queue_item_ref = write_queue_ref_artifact(queue_item, queue_item_id=queue_item["queue_item_id"], root=root)
    admitted_count = 0
    if args.mode == "apply":
        queue_validator = load_validator(Path(args.queue_item_schema))
        conn = connect(Path(args.queue_db))
        admitted_count = seed_queue_items(conn, [queue_item], queue_validator, replace_existing=False)
        conn.commit()
        conn.close()

    report = {
        "generated_at_utc": now_utc(),
        "handoff_contract_ref": SCHEDULED_DELIVERY_HANDOFF_CONTRACT_REF,
        "mode": args.mode,
        "verdict": "pass",
        "admitted_count": admitted_count,
        "queue_db": args.queue_db,
        "schedule_key": args.schedule_key,
        "delivery_work_item_kind": work_item["delivery_work_item_kind"],
        "selected_delivery_entrypoint": (
            "scripts/run_operator_message_delivery_cycle.py"
            if work_item["delivery_work_item_kind"] == "operator_message_delivery"
            else "scripts/run_goal_completion_delivery_cycle.py"
        ),
        "scheduled_delivery_work_item_ref": work_item_ref,
        "scheduled_queue_item_ref": queue_item_ref,
        "queue_item_id": queue_item["queue_item_id"],
        "delivery_idempotency_key": work_item["delivery_idempotency_key"],
        "goal_key": queue_item["goal_key"],
    }

    for key in [
        "headline",
        "priority_headline",
        "priority_summary_markdown",
        "first_action_command",
        "priority_cta_command",
        "primary_remediation_command",
        "operator_handoff_validation_path",
    ]:
        value = str(work_item.get(key) or "").strip()
        if value:
            report[key] = value
    remediation_commands = list_of_strings(work_item.get("remediation_commands"))
    if remediation_commands:
        report["remediation_commands"] = remediation_commands
    apply_operator_handoff_bundle_sidecar_paths(report, work_item)

    save_json(Path(args.output), report)
    print(f"report written: {args.output}")
    print(
        " ".join(
            [
                f"kind={report['delivery_work_item_kind']}",
                f"verdict={report['verdict']}",
                f"admitted={report['admitted_count']}",
                f"queue_item_id={report['queue_item_id']}",
            ]
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
