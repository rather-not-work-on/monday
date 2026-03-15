#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from runtime_evidence_contract import load_json
from runtime_queue_store import connect, load_validator, save_json, seed_queue_items


ADMISSION_CONTRACT_REF = "planningops/contracts/scheduled-queue-admission-handoff-contract.md"
SOURCE_REPO = "rather-not-work-on/platform-planningops"
DEFAULT_QUEUE_ITEM_SCHEMA = Path("../platform-contracts/schemas/runtime-scheduler-queue-item.schema.json")


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_repo_path(current_repo: Path, workspace_root_arg: str, repo_dir_arg: str) -> Path:
    repo_dir = Path(repo_dir_arg)
    if repo_dir.is_absolute():
        return repo_dir.resolve()
    workspace_root = Path(workspace_root_arg)
    if not workspace_root.is_absolute():
        workspace_root = (current_repo / workspace_root).resolve()
    candidates = [
        (workspace_root / repo_dir).resolve(),
        (current_repo / repo_dir).resolve(),
        repo_dir.resolve(),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def load_packet(packet_path: Path) -> dict:
    packet = load_json(packet_path, None)
    if packet is None:
        raise SystemExit(f"queue admission packet not found: {packet_path}")
    required = [
        "admission_version",
        "generated_at_utc",
        "admission_contract_ref",
        "source_repo",
        "goal_key",
        "schedule_key",
        "queue_seed_ref",
        "seed_format",
        "seed_item_count",
        "verdict",
    ]
    missing = [key for key in required if key not in packet]
    if missing:
        raise SystemExit(f"queue admission packet missing fields: {', '.join(missing)}")
    if packet["admission_contract_ref"] != ADMISSION_CONTRACT_REF:
        raise SystemExit(f"unexpected admission_contract_ref: {packet['admission_contract_ref']}")
    if packet["source_repo"] != SOURCE_REPO:
        raise SystemExit(f"unexpected source_repo: {packet['source_repo']}")
    if packet["seed_format"] != "runtime_scheduler_queue_items_json":
        raise SystemExit(f"unexpected seed_format: {packet['seed_format']}")
    if packet["verdict"] not in {"pass", "skipped"}:
        raise SystemExit(f"unexpected verdict: {packet['verdict']}")
    return packet


def resolve_queue_seed(packet: dict, planningops_repo: Path) -> Path:
    queue_seed_ref = str(packet["queue_seed_ref"]).strip()
    path = Path(queue_seed_ref)
    if path.is_absolute():
        return path
    return (planningops_repo / path).resolve()


def main() -> int:
    parser = argparse.ArgumentParser(description="Admit a planningops queue seed packet into the monday queue store")
    parser.add_argument("--packet", required=True)
    parser.add_argument("--queue-db", required=True)
    parser.add_argument("--workspace-root", default="..")
    parser.add_argument("--planningops-repo-dir", default="platform-planningops")
    parser.add_argument("--queue-item-schema", default=str(DEFAULT_QUEUE_ITEM_SCHEMA))
    parser.add_argument("--replace-existing", action="store_true")
    parser.add_argument("--output", default="runtime-artifacts/scheduler-queue/admission-report.json")
    args = parser.parse_args()

    monday_repo = Path(__file__).resolve().parents[1]
    planningops_repo = resolve_repo_path(monday_repo, args.workspace_root, args.planningops_repo_dir)
    packet_path = Path(args.packet)
    if not packet_path.is_absolute():
        packet_path = (monday_repo / packet_path).resolve()

    packet = load_packet(packet_path)
    queue_seed_path = resolve_queue_seed(packet, planningops_repo)
    queue_doc = load_json(queue_seed_path, None)
    if queue_doc is None:
        raise SystemExit(f"queue seed not found: {queue_seed_path}")

    queue_items = queue_doc.get("queue_items", [])
    if not isinstance(queue_items, list):
        raise SystemExit("queue_items must be a list")
    if len(queue_items) != int(packet["seed_item_count"]):
        raise SystemExit(
            f"seed_item_count mismatch: expected {packet['seed_item_count']}, got {len(queue_items)}"
        )

    goal_keys = {item.get("goal_key") for item in queue_items}
    schedule_keys = {item.get("schedule_key") for item in queue_items}
    if goal_keys != {packet["goal_key"]}:
        raise SystemExit(f"goal_key mismatch in queue seed: {sorted(goal_keys)}")
    if schedule_keys != {packet["schedule_key"]}:
        raise SystemExit(f"schedule_key mismatch in queue seed: {sorted(schedule_keys)}")

    admitted_count = 0
    verdict = packet["verdict"]
    if verdict == "pass":
        queue_validator = load_validator(Path(args.queue_item_schema))
        conn = connect(Path(args.queue_db))
        admitted_count = seed_queue_items(
            conn,
            queue_items,
            queue_validator,
            replace_existing=args.replace_existing,
        )
        conn.commit()
        conn.close()

    report = {
        "generated_at_utc": now_utc(),
        "admission_contract_ref": ADMISSION_CONTRACT_REF,
        "source_repo": SOURCE_REPO,
        "packet_path": str(packet_path),
        "planningops_repo": str(planningops_repo),
        "queue_seed_ref": str(packet["queue_seed_ref"]),
        "queue_seed_path": str(queue_seed_path),
        "queue_db": args.queue_db,
        "goal_key": packet["goal_key"],
        "schedule_key": packet["schedule_key"],
        "seed_item_count": int(packet["seed_item_count"]),
        "admitted_count": admitted_count,
        "replace_existing": args.replace_existing,
        "verdict": verdict,
    }
    save_json(Path(args.output), report)
    print(f"report written: {args.output}")
    print(
        " ".join(
            [
                f"verdict={report['verdict']}",
                f"admitted={report['admitted_count']}",
                f"goal_key={report['goal_key']}",
                f"schedule_key={report['schedule_key']}",
            ]
        )
    )
    return 0 if report["verdict"] in {"pass", "skipped"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
