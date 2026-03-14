#!/usr/bin/env python3

import argparse
import json
from pathlib import Path

from runtime_queue_store import (
    DEFAULT_WORKER_OUTCOME_SCHEMA,
    connect,
    load_validator,
    save_json,
    store_worker_outcome,
)
from runtime_evidence_contract import load_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Record monday queue worker outcomes into the local queue store")
    parser.add_argument("--db", default="runtime-artifacts/scheduler-queue/runtime-queue.sqlite3")
    parser.add_argument("--outcome-json", required=True)
    parser.add_argument("--worker-outcome-schema", default=str(DEFAULT_WORKER_OUTCOME_SCHEMA))
    parser.add_argument("--output", default="runtime-artifacts/worker-outcome/record-worker-outcome-report.json")
    args = parser.parse_args()

    outcome_validator = load_validator(Path(args.worker_outcome_schema))
    outcome = load_json(Path(args.outcome_json), None)
    if outcome is None:
        raise SystemExit(f"worker outcome json not found: {args.outcome_json}")

    conn = connect(Path(args.db))
    updated = store_worker_outcome(conn, outcome, outcome_validator)
    conn.close()

    report = {
        "db": args.db,
        "outcome_json": args.outcome_json,
        "queue_item_id": outcome["queue_item_id"],
        "state_to": outcome["state_to"],
        "verdict": "pass",
        "queue_item": updated,
    }
    save_json(Path(args.output), report)
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
