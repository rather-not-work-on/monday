#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from runtime_evidence_contract import load_json
from runtime_queue_store import (
    DEFAULT_WORKER_OUTCOME_SCHEMA,
    connect,
    load_validator,
    read_queue_rows,
)

SELECTOR_CONTRACT_REF = "planningops/contracts/scheduler-native-worker-outcome-selection-contract.md"
WORKER_OUTCOME_CONTRACT_REF = "platform-contracts/schemas/runtime-queue-worker-outcome.schema.json"
REPO_ROOT = Path(__file__).resolve().parents[1]


def save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


def normalize_repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve()))
    except ValueError:
        return str(path.resolve())


def iter_json_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    return sorted(path for path in root.rglob("*.json") if path.is_file())


def resolve_queue_item(queue_item_id: str, queue_db: Path | None, queue_doc: dict[str, Any]) -> dict[str, Any]:
    if queue_db is not None:
        conn = connect(queue_db)
        try:
            rows = read_queue_rows(conn, "WHERE queue_item_id = ?", [queue_item_id])
        finally:
            conn.close()
        if rows:
            return rows[0]
    for item in queue_doc.get("queue_items", []):
        if item.get("queue_item_id") == queue_item_id:
            return item
    raise RuntimeError(f"queue item not found for selector: {queue_item_id}")


def build_base_report(*, scheduled_report: dict[str, Any], scheduled_report_path: Path, selected: bool) -> dict[str, Any]:
    return {
        "selected": selected,
        "scheduled_run_id": scheduled_report["run_id"],
        "goal_key": "-",
        "schedule_key": "-",
        "queue_item_id": "-",
        "worker_run_id": scheduled_report["run_id"],
        "source_worker_outcome_ref": "-",
        "source_worker_outcome_contract_ref": WORKER_OUTCOME_CONTRACT_REF,
        "selection_reason": "scheduled_run_match",
        "selector_contract_ref": SELECTOR_CONTRACT_REF,
        "scheduled_report_ref": normalize_repo_path(scheduled_report_path),
        "candidate_count": 0,
        "verdict": "fail",
        "error_count": 0,
        "errors": [],
    }


def select_worker_outcome(
    *,
    scheduled_report: dict[str, Any],
    scheduled_report_path: Path,
    queue_doc: dict[str, Any],
    queue_db: Path | None,
    worker_outcome_root: Path,
    worker_outcome_schema: Path,
) -> dict[str, Any]:
    report = build_base_report(
        scheduled_report=scheduled_report,
        scheduled_report_path=scheduled_report_path,
        selected=False,
    )

    dequeued = scheduled_report.get("dequeued") or []
    dequeued_count = int(scheduled_report.get("dequeued_count") or 0)
    if dequeued_count == 0:
        report["selection_reason"] = "scheduler_no_dequeue"
        report["verdict"] = "skipped"
        return report
    if dequeued_count != 1 or len(dequeued) != 1:
        report["errors"] = [f"expected exactly one dequeued queue item, got {dequeued_count}"]
        report["error_count"] = len(report["errors"])
        return report

    queue_item_id = str(dequeued[0]["card_id"])
    queue_item = resolve_queue_item(queue_item_id, queue_db, queue_doc)
    report["queue_item_id"] = queue_item_id
    report["goal_key"] = str(queue_item["goal_key"])
    report["schedule_key"] = str(queue_item["schedule_key"])

    if not worker_outcome_root.exists():
        report["errors"] = [f"worker outcome root not found: {worker_outcome_root}"]
        report["error_count"] = len(report["errors"])
        return report

    validator = load_validator(worker_outcome_schema)
    candidates: list[tuple[Path, dict[str, Any]]] = []
    for path in iter_json_files(worker_outcome_root):
        doc = load_json(path, None)
        if not isinstance(doc, dict):
            continue
        try:
            validator.validate(doc)
        except Exception:  # noqa: BLE001
            continue
        if doc.get("worker_run_id") != scheduled_report["run_id"]:
            continue
        if doc.get("queue_item_id") != queue_item_id:
            continue
        if doc.get("goal_key") != queue_item["goal_key"]:
            continue
        if doc.get("schedule_key") != queue_item["schedule_key"]:
            continue
        candidates.append((path, doc))

    report["candidate_count"] = len(candidates)
    if len(candidates) != 1:
        report["errors"] = [f"expected exactly one worker outcome candidate, got {len(candidates)}"]
        report["error_count"] = len(report["errors"])
        return report

    selected_path, selected_doc = candidates[0]
    report["selected"] = True
    report["worker_run_id"] = str(selected_doc["worker_run_id"])
    report["source_worker_outcome_ref"] = normalize_repo_path(selected_path)
    report["source_worker_outcome_contract_ref"] = WORKER_OUTCOME_CONTRACT_REF
    report["selection_reason"] = "scheduled_run_match"
    report["verdict"] = "pass"
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Resolve the current scheduled worker outcome from monday-owned runtime evidence")
    parser.add_argument("--scheduled-report", required=True)
    parser.add_argument("--queue", required=True)
    parser.add_argument("--queue-db", default=None)
    parser.add_argument("--worker-outcome-root", required=True)
    parser.add_argument("--worker-outcome-schema", default=str(DEFAULT_WORKER_OUTCOME_SCHEMA))
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    scheduled_report_path = Path(args.scheduled_report)
    queue_path = Path(args.queue)
    queue_db = Path(args.queue_db) if args.queue_db else None
    worker_outcome_root = Path(args.worker_outcome_root)
    worker_outcome_schema = Path(args.worker_outcome_schema)
    output_path = Path(args.output)

    scheduled_report = load_json(scheduled_report_path, None)
    if scheduled_report is None:
        raise SystemExit(f"scheduled report not found: {args.scheduled_report}")
    queue_doc = load_json(queue_path, {})

    report = select_worker_outcome(
        scheduled_report=scheduled_report,
        scheduled_report_path=scheduled_report_path,
        queue_doc=queue_doc,
        queue_db=queue_db,
        worker_outcome_root=worker_outcome_root,
        worker_outcome_schema=worker_outcome_schema,
    )
    save_json(output_path, report)
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0 if report["verdict"] in {"pass", "skipped"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
