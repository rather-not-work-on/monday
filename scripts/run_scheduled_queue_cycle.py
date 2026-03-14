#!/usr/bin/env python3

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
import sys

from jsonschema_compat import load_validator_exports
from runtime_queue_store import (
    connect as connect_queue_store,
    list_completed_queue_item_ids,
    load_validator as load_store_validator,
    read_queue_rows,
    seed_queue_items,
    store_transition,
)
from runtime_evidence_contract import load_json, validate_report


DEFAULT_TAXONOMY = Path("config/runtime-reason-taxonomy.json")
DEFAULT_EVIDENCE_SCHEMA = Path("contracts/runtime-scheduler-evidence.schema.json")
DEFAULT_QUEUE_ITEM_SCHEMA = Path("../platform-contracts/schemas/runtime-scheduler-queue-item.schema.json")

Draft202012Validator, FormatChecker, _SchemaError = load_validator_exports()


def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=True, indent=2), encoding="utf-8")


def append_ndjson(path: Path, row):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=True) + "\n")


def now_utc():
    return datetime.now(timezone.utc).isoformat()


def resolve_reason_code(dequeued_count: int, blocked_count: int, duplicate_count: int):
    if dequeued_count == 0 and blocked_count == 0 and duplicate_count == 0:
        return "scheduler_no_dequeue"
    if blocked_count > 0:
        return "blocked_dependencies"
    if duplicate_count > 0:
        return "duplicates_detected"
    return "ok"


def infer_issue_number(token: str, fallback: int):
    matches = re.findall(r"\d+", token or "")
    if not matches:
        return fallback
    return int(matches[-1])


def validate_wave4_queue_items(queue_items: list[dict], schema_path: Path):
    if not schema_path.exists():
        raise FileNotFoundError(
            f"queue item schema not found at {schema_path}; ensure platform-contracts D20 is available"
        )
    schema = load_json(schema_path)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for idx, item in enumerate(queue_items):
        try:
            validator.validate(item)
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"queue_items[{idx}] failed schema validation: {exc}") from exc


def lease_expiry(now_value: datetime, duration_seconds: int) -> str:
    return (now_value + timedelta(seconds=duration_seconds)).isoformat()


def run_legacy_cycle(args, queue_doc: dict, processed: set[str], run_id: str):
    items = queue_doc.get("items", [])
    completed = set(queue_doc.get("completed_issues", []))

    dequeued = []
    blocked = []
    duplicates = []
    replanning_triggered_cards = []

    for item in items:
        card_id = str(item.get("card_id", ""))
        issue_number = int(item.get("issue_number", 0) or 0)
        depends_on = item.get("depends_on", [])

        if card_id in processed:
            duplicates.append(card_id)
            append_ndjson(
                Path(args.transition_log),
                {
                    "transition_id": f"{run_id}-{card_id}-duplicate",
                    "run_id": run_id,
                    "card_id": card_id,
                    "from_state": "Todo",
                    "to_state": "Skipped",
                    "transition_reason": "idempotency.duplicate_dequeue",
                    "replanning_flag": False,
                    "decided_at_utc": now_utc(),
                },
            )
            continue

        unresolved = [int(dep) for dep in depends_on if dep not in completed]
        if unresolved:
            blocked.append(
                {
                    "card_id": card_id,
                    "issue_number": issue_number,
                    "unresolved_depends_on": unresolved,
                }
            )
            reason_history = item.get("reason_history", [])
            replanning_flag = len(reason_history) >= 2 and len(set(reason_history[-2:])) == 1
            if replanning_flag:
                replanning_triggered_cards.append(card_id)

            append_ndjson(
                Path(args.transition_log),
                {
                    "transition_id": f"{run_id}-{card_id}-blocked",
                    "run_id": run_id,
                    "card_id": card_id,
                    "from_state": "Todo",
                    "to_state": "Blocked",
                    "transition_reason": "dependency.unresolved",
                    "unresolved_depends_on": unresolved,
                    "replanning_flag": replanning_flag,
                    "decided_at_utc": now_utc(),
                },
            )
            continue

        dequeued.append({"card_id": card_id, "issue_number": issue_number})
        processed.add(card_id)
        append_ndjson(
            Path(args.transition_log),
            {
                "transition_id": f"{run_id}-{card_id}-dequeued",
                "run_id": run_id,
                "card_id": card_id,
                "from_state": "Todo",
                "to_state": "In Progress",
                "transition_reason": "scheduler.dequeue",
                "replanning_flag": False,
                "decided_at_utc": now_utc(),
            },
        )

    return dequeued, blocked, duplicates, replanning_triggered_cards


def run_wave4_cycle(args, queue_doc: dict, processed: set[str], run_id: str):
    queue_items = queue_doc.get("queue_items", [])
    completed = set(queue_doc.get("completed_queue_item_ids", []))
    validate_wave4_queue_items(queue_items, Path(args.queue_item_schema))

    dequeued = []
    blocked = []
    duplicates = []
    replanning_triggered_cards = []

    for idx, item in enumerate(queue_items, start=1):
        queue_item_id = item["queue_item_id"]
        idempotency_key = item["idempotency_key"]
        state = item["state"]
        deps = item.get("dependency_keys", [])
        fallback_issue = idx
        issue_number = infer_issue_number(queue_item_id, fallback_issue)

        if idempotency_key in processed:
            duplicates.append(queue_item_id)
            append_ndjson(
                Path(args.transition_log),
                {
                    "transition_id": f"{run_id}-{queue_item_id}-duplicate",
                    "run_id": run_id,
                    "card_id": queue_item_id,
                    "from_state": state,
                    "to_state": "Skipped",
                    "transition_reason": "idempotency.duplicate_dequeue",
                    "replanning_flag": False,
                    "decided_at_utc": now_utc(),
                },
            )
            continue

        if state not in {"ready", "scheduled", "retry_wait"}:
            continue

        unresolved = [dep for dep in deps if dep not in completed]
        if unresolved:
            blocked.append(
                {
                    "card_id": queue_item_id,
                    "issue_number": issue_number,
                    "unresolved_depends_on": [infer_issue_number(dep, idx) for dep in unresolved],
                }
            )
            append_ndjson(
                Path(args.transition_log),
                {
                    "transition_id": f"{run_id}-{queue_item_id}-blocked",
                    "run_id": run_id,
                    "card_id": queue_item_id,
                    "from_state": state,
                    "to_state": "blocked",
                    "transition_reason": "dependency.unresolved",
                    "unresolved_depends_on": unresolved,
                    "replanning_flag": False,
                    "decided_at_utc": now_utc(),
                },
            )
            continue

        dequeued.append({"card_id": queue_item_id, "issue_number": issue_number})
        processed.add(idempotency_key)
        completed.add(queue_item_id)
        append_ndjson(
            Path(args.transition_log),
            {
                "transition_id": f"{run_id}-{queue_item_id}-dequeued",
                "run_id": run_id,
                "card_id": queue_item_id,
                "from_state": state,
                "to_state": "running",
                "transition_reason": "scheduler.dequeue",
                "replanning_flag": False,
                "decided_at_utc": now_utc(),
            },
        )

    return dequeued, blocked, duplicates, replanning_triggered_cards


def run_store_backed_wave4_cycle(args, queue_doc: dict, processed: set[str], run_id: str):
    conn = connect_queue_store(Path(args.queue_db))
    queue_validator = load_store_validator(Path(args.queue_item_schema))
    lease_validator = load_store_validator(Path(args.lease_schema))
    queue_items = queue_doc.get("queue_items", [])
    if not isinstance(queue_items, list):
        raise ValueError("queue_items must be a list")
    seed_queue_items(
        conn,
        queue_items,
        queue_validator,
        replace_existing=args.db_seed_mode == "replace",
    )
    completed = set(queue_doc.get("completed_queue_item_ids", []))
    completed.update(list_completed_queue_item_ids(conn))
    current_time = datetime.now(timezone.utc)
    ready_items = read_queue_rows(
        conn,
        "WHERE state IN ('ready', 'scheduled') OR (state = 'retry_wait' AND retry_after_utc IS NOT NULL AND retry_after_utc <= ?)",
        [current_time.isoformat()],
    )

    dequeued = []
    blocked = []
    duplicates = []
    replanning_triggered_cards = []

    for idx, item in enumerate(ready_items, start=1):
        queue_item_id = item["queue_item_id"]
        idempotency_key = item["idempotency_key"]
        state = item["state"]
        deps = item.get("dependency_keys", [])
        issue_number = infer_issue_number(queue_item_id, idx)
        transition_id = f"{run_id}-{queue_item_id}"

        if idempotency_key in processed:
            duplicates.append(queue_item_id)
            append_ndjson(
                Path(args.transition_log),
                {
                    "transition_id": f"{transition_id}-duplicate",
                    "run_id": run_id,
                    "card_id": queue_item_id,
                    "from_state": state,
                    "to_state": "Skipped",
                    "transition_reason": "idempotency.duplicate_dequeue",
                    "replanning_flag": False,
                    "decided_at_utc": now_utc(),
                },
            )
            continue

        unresolved = [dep for dep in deps if dep not in completed]
        if unresolved:
            blocked.append(
                {
                    "card_id": queue_item_id,
                    "issue_number": issue_number,
                    "unresolved_depends_on": [infer_issue_number(dep, idx) for dep in unresolved],
                }
            )
            store_transition(
                conn,
                {
                    "transition_id": f"{transition_id}-blocked",
                    "queue_item_id": queue_item_id,
                    "goal_key": item["goal_key"],
                    "schedule_key": item["schedule_key"],
                    "lease_owner": args.lease_owner,
                    "lease_token": transition_id,
                    "state_from": state,
                    "state_to": "blocked",
                    "transition_reason": "dependency.unresolved",
                    "occurred_at_utc": current_time.isoformat(),
                    "attempt_count": item["attempt_count"],
                    "retry_budget_remaining": item["retry_budget_remaining"],
                },
                lease_validator,
            )
            append_ndjson(
                Path(args.transition_log),
                {
                    "transition_id": f"{transition_id}-blocked",
                    "run_id": run_id,
                    "card_id": queue_item_id,
                    "from_state": state,
                    "to_state": "blocked",
                    "transition_reason": "dependency.unresolved",
                    "unresolved_depends_on": unresolved,
                    "replanning_flag": False,
                    "decided_at_utc": current_time.isoformat(),
                },
            )
            continue

        dequeued.append({"card_id": queue_item_id, "issue_number": issue_number})
        processed.add(idempotency_key)
        completed.add(queue_item_id)
        store_transition(
            conn,
            {
                "transition_id": f"{transition_id}-leased",
                "queue_item_id": queue_item_id,
                "goal_key": item["goal_key"],
                "schedule_key": item["schedule_key"],
                "lease_owner": args.lease_owner,
                "lease_token": transition_id,
                "state_from": state,
                "state_to": "leased",
                "transition_reason": "scheduler.dequeue",
                "occurred_at_utc": current_time.isoformat(),
                "lease_expires_at_utc": lease_expiry(current_time, args.lease_duration_seconds),
                "heartbeat_at_utc": current_time.isoformat(),
                "attempt_count": item["attempt_count"] + 1,
                "retry_budget_remaining": item["retry_budget_remaining"],
                "worker_run_id": run_id,
            },
            lease_validator,
        )
        append_ndjson(
            Path(args.transition_log),
            {
                "transition_id": f"{transition_id}-leased",
                "run_id": run_id,
                "card_id": queue_item_id,
                "from_state": state,
                "to_state": "leased",
                "transition_reason": "scheduler.dequeue",
                "replanning_flag": False,
                "decided_at_utc": current_time.isoformat(),
            },
        )

    conn.close()
    return dequeued, blocked, duplicates, replanning_triggered_cards


def main():
    parser = argparse.ArgumentParser(description="Run a scheduled queue cycle baseline")
    parser.add_argument("--queue", default="fixtures/queue.sample.json")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--idempotency", default="runtime-artifacts/scheduler-cycle/idempotency.json")
    parser.add_argument("--report", default="runtime-artifacts/scheduler-cycle/run-report.json")
    parser.add_argument(
        "--transition-log",
        default="runtime-artifacts/transition-log/scheduled-queue-cycle.ndjson",
    )
    parser.add_argument("--queue-item-schema", default=str(DEFAULT_QUEUE_ITEM_SCHEMA))
    parser.add_argument("--queue-db", default=None)
    parser.add_argument(
        "--lease-schema",
        default=str(Path("../platform-contracts/schemas/runtime-scheduler-lease-lifecycle.schema.json")),
    )
    parser.add_argument("--lease-owner", default="monday-local-worker")
    parser.add_argument("--lease-duration-seconds", type=int, default=300)
    parser.add_argument("--db-seed-mode", choices=["insert", "replace"], default="insert")
    args = parser.parse_args()

    run_id = args.run_id or f"scheduled-cycle-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    queue_doc = load_json(Path(args.queue), {})
    idem_doc = load_json(Path(args.idempotency), {"processed_card_ids": []})
    processed = set(idem_doc.get("processed_card_ids", []))

    if args.queue_db and "queue_items" in queue_doc:
        dequeued, blocked, duplicates, replanning_triggered_cards = run_store_backed_wave4_cycle(
            args, queue_doc, processed, run_id
        )
    elif "queue_items" in queue_doc:
        dequeued, blocked, duplicates, replanning_triggered_cards = run_wave4_cycle(
            args, queue_doc, processed, run_id
        )
    else:
        dequeued, blocked, duplicates, replanning_triggered_cards = run_legacy_cycle(
            args, queue_doc, processed, run_id
        )

    save_json(Path(args.idempotency), {"processed_card_ids": sorted(processed)})

    reason_code = resolve_reason_code(len(dequeued), len(blocked), len(duplicates))
    verdict = "pass" if reason_code != "scheduler_no_dequeue" else "fail"
    taxonomy = load_json(DEFAULT_TAXONOMY)
    report = {
        "generated_at_utc": now_utc(),
        "run_id": run_id,
        "verdict": verdict,
        "reason_code": reason_code,
        "reason_taxonomy_version": int(taxonomy.get("version", 0)),
        "dequeued_count": len(dequeued),
        "blocked_count": len(blocked),
        "duplicate_count": len(duplicates),
        "replanning_trigger_count": len(replanning_triggered_cards),
        "dequeued": dequeued,
        "blocked": blocked,
        "duplicates": duplicates,
        "replanning_triggered_cards": replanning_triggered_cards,
    }
    validate_report(report, DEFAULT_EVIDENCE_SCHEMA, DEFAULT_TAXONOMY)
    save_json(Path(args.report), report)

    print(f"report written: {args.report}")
    print(
        " ".join(
            [
                f"verdict={verdict}",
                f"reason_code={reason_code}",
                f"dequeued={report['dequeued_count']}",
                f"blocked={report['blocked_count']}",
                f"duplicates={report['duplicate_count']}",
                f"replanning={len(replanning_triggered_cards)}",
            ]
        )
    )
    return 0 if verdict == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
