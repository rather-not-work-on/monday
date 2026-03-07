#!/usr/bin/env python3

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import sys

from runtime_evidence_contract import load_json, validate_report


DEFAULT_TAXONOMY = Path("config/runtime-reason-taxonomy.json")
DEFAULT_SCHEMA = Path("contracts/runtime-scheduler-evidence.schema.json")


def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=True, indent=2), encoding="utf-8")


def append_ndjson(path: Path, row):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=True) + "\n")


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


def main():
    parser = argparse.ArgumentParser(description="Scheduler queue baseline")
    parser.add_argument("--queue", default="fixtures/queue.sample.json")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--idempotency", default="runtime-artifacts/scheduler/idempotency.json")
    parser.add_argument("--report", default="runtime-artifacts/scheduler/run-report.json")
    parser.add_argument("--transition-log", default="runtime-artifacts/transition-log/scheduler.ndjson")
    args = parser.parse_args()

    run_id = args.run_id or f"scheduler-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"

    qdoc = load_json(Path(args.queue), {"items": [], "completed_issues": []})
    items = qdoc.get("items", [])
    completed = set(qdoc.get("completed_issues", []))

    idem_doc = load_json(Path(args.idempotency), {"processed_card_ids": []})
    processed = set(idem_doc.get("processed_card_ids", []))
    taxonomy = load_json(DEFAULT_TAXONOMY)

    dequeued = []
    blocked = []
    duplicates = []
    replanning_triggered_cards = []

    for item in items:
        card_id = item.get("card_id")
        issue_number = item.get("issue_number")
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

        unresolved = [d for d in depends_on if d not in completed]
        if unresolved:
            blocked.append({"card_id": card_id, "issue_number": issue_number, "unresolved_depends_on": unresolved})
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

    save_json(Path(args.idempotency), {"processed_card_ids": sorted(processed)})

    reason_code = resolve_reason_code(len(dequeued), len(blocked), len(duplicates))
    verdict = "pass" if reason_code != "scheduler_no_dequeue" else "fail"

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

    validate_report(report, DEFAULT_SCHEMA, DEFAULT_TAXONOMY)

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
