#!/usr/bin/env python3

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import sys


def load_json(path: Path, default=None):
    if not path.exists():
        return default if default is not None else {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=True, indent=2), encoding="utf-8")


def append_ndjson(path: Path, row):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=True) + "\n")


def now_utc():
    return datetime.now(timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser(description="Scheduler queue baseline")
    parser.add_argument("--queue", default="fixtures/queue.sample.json")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--idempotency", default="artifacts/scheduler/idempotency.json")
    parser.add_argument("--report", default="artifacts/scheduler/run-report.json")
    parser.add_argument("--transition-log", default="artifacts/transition-log/scheduler.ndjson")
    args = parser.parse_args()

    run_id = args.run_id or f"scheduler-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"

    qdoc = load_json(Path(args.queue), {"items": [], "completed_issues": []})
    items = qdoc.get("items", [])
    completed = set(qdoc.get("completed_issues", []))

    idem_doc = load_json(Path(args.idempotency), {"processed_card_ids": []})
    processed = set(idem_doc.get("processed_card_ids", []))

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

    report = {
        "generated_at_utc": now_utc(),
        "run_id": run_id,
        "dequeued_count": len(dequeued),
        "blocked_count": len(blocked),
        "duplicate_count": len(duplicates),
        "dequeued": dequeued,
        "blocked": blocked,
        "duplicates": duplicates,
        "replanning_triggered_cards": replanning_triggered_cards,
    }

    save_json(Path(args.report), report)

    print(f"report written: {args.report}")
    print(
        f"dequeued={report['dequeued_count']} blocked={report['blocked_count']} duplicates={report['duplicate_count']} replanning={len(replanning_triggered_cards)}"
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
