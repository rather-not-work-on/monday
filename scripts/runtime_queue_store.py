#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema_compat import load_validator_exports
from runtime_evidence_contract import load_json

DEFAULT_QUEUE_ITEM_SCHEMA = Path("../platform-contracts/schemas/runtime-scheduler-queue-item.schema.json")
DEFAULT_LEASE_SCHEMA = Path("../platform-contracts/schemas/runtime-scheduler-lease-lifecycle.schema.json")
DEFAULT_WORKER_OUTCOME_SCHEMA = Path("../platform-contracts/schemas/runtime-queue-worker-outcome.schema.json")

Draft202012Validator, FormatChecker, _SchemaError = load_validator_exports()

QUEUE_TABLE = """
CREATE TABLE IF NOT EXISTS queue_items (
  queue_item_id TEXT PRIMARY KEY,
  goal_key TEXT NOT NULL,
  schedule_key TEXT NOT NULL,
  state TEXT NOT NULL,
  idempotency_key TEXT NOT NULL,
  priority_class TEXT NOT NULL,
  retry_budget_json TEXT NOT NULL,
  retry_budget_remaining INTEGER NOT NULL,
  attempt_count INTEGER NOT NULL,
  dependency_keys_json TEXT NOT NULL,
  escalation_policy_ref TEXT NOT NULL,
  completion_policy_ref TEXT NOT NULL,
  target_repo TEXT,
  work_payload_ref TEXT,
  lease_owner TEXT,
  lease_expires_at_utc TEXT,
  blocked_reason TEXT,
  dead_letter_reason TEXT,
  completion_evidence_ref TEXT,
  raw_payload_json TEXT NOT NULL,
  updated_at_utc TEXT NOT NULL
);
"""

TRANSITION_TABLE = """
CREATE TABLE IF NOT EXISTS queue_transitions (
  transition_id TEXT PRIMARY KEY,
  queue_item_id TEXT NOT NULL,
  occurred_at_utc TEXT NOT NULL,
  raw_payload_json TEXT NOT NULL
);
"""


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


def load_validator(schema_path: Path):
    schema = load_json(schema_path, None)
    if schema is None:
        raise FileNotFoundError(f"schema not found: {schema_path}")
    return Draft202012Validator(schema, format_checker=FormatChecker())


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute(QUEUE_TABLE)
    conn.execute(TRANSITION_TABLE)
    return conn


def normalize_queue_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "queue_item_id": item["queue_item_id"],
        "goal_key": item["goal_key"],
        "schedule_key": item["schedule_key"],
        "state": item["state"],
        "idempotency_key": item["idempotency_key"],
        "priority_class": item["priority_class"],
        "retry_budget_json": json.dumps(item["retry_budget"], ensure_ascii=True, sort_keys=True),
        "retry_budget_remaining": item["retry_budget_remaining"],
        "attempt_count": item["attempt_count"],
        "dependency_keys_json": json.dumps(item.get("dependency_keys", []), ensure_ascii=True),
        "escalation_policy_ref": item["escalation_policy_ref"],
        "completion_policy_ref": item["completion_policy_ref"],
        "target_repo": item.get("target_repo"),
        "work_payload_ref": item.get("work_payload_ref"),
        "lease_owner": item.get("lease_owner"),
        "lease_expires_at_utc": item.get("lease_expires_at_utc"),
        "blocked_reason": item.get("blocked_reason"),
        "dead_letter_reason": item.get("dead_letter_reason"),
        "completion_evidence_ref": item.get("completion_evidence_ref"),
        "raw_payload_json": json.dumps(item, ensure_ascii=True, sort_keys=True),
        "updated_at_utc": now_utc(),
    }


def upsert_queue_item(conn: sqlite3.Connection, normalized: dict[str, Any]) -> None:
    columns = list(normalized.keys())
    assignments = ", ".join(f"{column}=excluded.{column}" for column in columns if column != "queue_item_id")
    conn.execute(
        f"""
        INSERT INTO queue_items ({", ".join(columns)})
        VALUES ({", ".join("?" for _ in columns)})
        ON CONFLICT(queue_item_id) DO UPDATE SET
          {assignments}
        """,
        [normalized[column] for column in columns],
    )


def insert_queue_item_if_missing(conn: sqlite3.Connection, normalized: dict[str, Any]) -> None:
    columns = list(normalized.keys())
    conn.execute(
        f"""
        INSERT OR IGNORE INTO queue_items ({", ".join(columns)})
        VALUES ({", ".join("?" for _ in columns)})
        """,
        [normalized[column] for column in columns],
    )


def seed_queue_items(
    conn: sqlite3.Connection,
    queue_items: list[dict[str, Any]],
    queue_validator,
    *,
    replace_existing: bool,
) -> int:
    inserted = 0
    for item in queue_items:
        queue_validator.validate(item)
        normalized = normalize_queue_item(item)
        if replace_existing:
            upsert_queue_item(conn, normalized)
        else:
            insert_queue_item_if_missing(conn, normalized)
        inserted += 1
    return inserted


def command_init(args) -> int:
    conn = connect(Path(args.db))
    conn.close()
    report = {"db": args.db, "verdict": "pass", "initialized": True}
    if args.output:
        save_json(Path(args.output), report)
    else:
        print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0


def command_seed(args) -> int:
    queue_validator = load_validator(Path(args.queue_item_schema))
    queue_doc = load_json(Path(args.queue), {})
    queue_items = queue_doc.get("queue_items", [])
    if not isinstance(queue_items, list):
        raise SystemExit("queue_items must be a list")
    conn = connect(Path(args.db))
    inserted = seed_queue_items(
        conn,
        queue_items,
        queue_validator,
        replace_existing=args.replace_existing,
    )
    conn.commit()
    conn.close()
    report = {
        "db": args.db,
        "queue": args.queue,
        "inserted_count": inserted,
        "replace_existing": args.replace_existing,
        "verdict": "pass",
    }
    if args.output:
        save_json(Path(args.output), report)
    else:
        print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0


def read_queue_rows(conn: sqlite3.Connection, where_clause: str = "", params: list[Any] | None = None):
    sql = """
    SELECT queue_item_id, goal_key, schedule_key, state, idempotency_key, priority_class,
           retry_budget_remaining, attempt_count, dependency_keys_json, lease_owner,
           lease_expires_at_utc, blocked_reason, dead_letter_reason, completion_evidence_ref,
           raw_payload_json, updated_at_utc
    FROM queue_items
    """
    if where_clause:
        sql += " " + where_clause
    sql += " ORDER BY queue_item_id"
    rows = conn.execute(sql, params or []).fetchall()
    result = []
    for row in rows:
        payload = json.loads(row["raw_payload_json"])
        payload["state"] = row["state"]
        payload["retry_budget_remaining"] = row["retry_budget_remaining"]
        payload["attempt_count"] = row["attempt_count"]
        payload["lease_owner"] = row["lease_owner"]
        payload["lease_expires_at_utc"] = row["lease_expires_at_utc"]
        payload["blocked_reason"] = row["blocked_reason"]
        payload["dead_letter_reason"] = row["dead_letter_reason"]
        payload["completion_evidence_ref"] = row["completion_evidence_ref"]
        result.append(payload)
    return result


def list_completed_queue_item_ids(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT queue_item_id FROM queue_items WHERE state = 'completed'"
    ).fetchall()
    return {str(row["queue_item_id"]) for row in rows}


def insert_transition_row(conn: sqlite3.Connection, transition: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO queue_transitions (transition_id, queue_item_id, occurred_at_utc, raw_payload_json)
        VALUES (?, ?, ?, ?)
        """,
        [
            transition["transition_id"],
            transition["queue_item_id"],
            transition["occurred_at_utc"],
            json.dumps(transition, ensure_ascii=True, sort_keys=True),
        ],
    )


def store_transition(conn: sqlite3.Connection, transition: dict[str, Any], lease_validator) -> dict[str, Any]:
    lease_validator.validate(transition)
    queue_item_id = transition["queue_item_id"]
    row = conn.execute(
        "SELECT queue_item_id, state FROM queue_items WHERE queue_item_id = ?",
        [queue_item_id],
    ).fetchone()
    if row is None:
        raise RuntimeError(f"queue item not found: {queue_item_id}")
    if row["state"] != transition["state_from"]:
        raise RuntimeError(
            f"queue item state mismatch for {queue_item_id}: expected {transition['state_from']}, got {row['state']}"
        )
    insert_transition_row(conn, transition)
    blocked_reason = None
    if transition["state_to"] == "blocked":
        blocked_reason = transition["transition_reason"]
    conn.execute(
        """
        UPDATE queue_items
        SET state = ?,
            lease_owner = ?,
            lease_expires_at_utc = ?,
            blocked_reason = ?,
            attempt_count = ?,
            retry_budget_remaining = ?,
            dead_letter_reason = ?,
            completion_evidence_ref = ?,
            updated_at_utc = ?
        WHERE queue_item_id = ?
        """,
        [
            transition["state_to"],
            transition["lease_owner"],
            transition.get("lease_expires_at_utc"),
            blocked_reason,
            transition["attempt_count"],
            transition["retry_budget_remaining"],
            transition.get("dead_letter_reason"),
            transition.get("completion_evidence_ref"),
            now_utc(),
            queue_item_id,
        ],
    )
    conn.commit()
    return read_queue_rows(conn, "WHERE queue_item_id = ?", [queue_item_id])[0]


def store_worker_outcome(conn: sqlite3.Connection, outcome: dict[str, Any], outcome_validator) -> dict[str, Any]:
    outcome_validator.validate(outcome)
    queue_item_id = outcome["queue_item_id"]
    row = conn.execute(
        "SELECT queue_item_id, state, lease_owner FROM queue_items WHERE queue_item_id = ?",
        [queue_item_id],
    ).fetchone()
    if row is None:
        raise RuntimeError(f"queue item not found: {queue_item_id}")
    if row["state"] != outcome["state_from"]:
        raise RuntimeError(
            f"queue item state mismatch for {queue_item_id}: expected {outcome['state_from']}, got {row['state']}"
        )
    if row["lease_owner"] and row["lease_owner"] != outcome["lease_owner"]:
        raise RuntimeError(
            f"queue item lease owner mismatch for {queue_item_id}: expected {row['lease_owner']}, got {outcome['lease_owner']}"
        )
    insert_transition_row(conn, outcome)
    conn.execute(
        """
        UPDATE queue_items
        SET state = ?,
            lease_owner = ?,
            lease_expires_at_utc = ?,
            blocked_reason = ?,
            attempt_count = ?,
            retry_budget_remaining = ?,
            dead_letter_reason = ?,
            completion_evidence_ref = ?,
            updated_at_utc = ?
        WHERE queue_item_id = ?
        """,
        [
            outcome["state_to"],
            outcome["lease_owner"],
            None,
            None,
            outcome["attempt_count"],
            outcome["retry_budget_remaining"],
            outcome.get("dead_letter_reason"),
            outcome.get("completion_evidence_ref"),
            now_utc(),
            queue_item_id,
        ],
    )
    conn.commit()
    return read_queue_rows(conn, "WHERE queue_item_id = ?", [queue_item_id])[0]


def command_list_ready(args) -> int:
    conn = connect(Path(args.db))
    rows = read_queue_rows(
        conn,
        "WHERE state IN ('ready', 'scheduled', 'retry_wait')",
    )
    conn.close()
    report = {"db": args.db, "ready_count": len(rows), "queue_items": rows, "verdict": "pass"}
    if args.output:
        save_json(Path(args.output), report)
    else:
        print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0


def command_record_transition(args) -> int:
    lease_validator = load_validator(Path(args.lease_schema))
    transition = load_json(Path(args.transition_json), None)
    if transition is None:
        raise SystemExit(f"transition json not found: {args.transition_json}")
    conn = connect(Path(args.db))
    updated = store_transition(conn, transition, lease_validator)
    conn.close()
    report = {
        "db": args.db,
        "transition_json": args.transition_json,
        "queue_item_id": transition["queue_item_id"],
        "state_to": transition["state_to"],
        "verdict": "pass",
        "queue_item": updated,
    }
    if args.output:
        save_json(Path(args.output), report)
    else:
        print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage monday local SQLite queue store baseline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("--db", default="runtime-artifacts/scheduler-queue/runtime-queue.sqlite3")
    init_parser.add_argument("--output", default=None)
    init_parser.set_defaults(func=command_init)

    seed_parser = subparsers.add_parser("seed")
    seed_parser.add_argument("--db", default="runtime-artifacts/scheduler-queue/runtime-queue.sqlite3")
    seed_parser.add_argument("--queue", required=True)
    seed_parser.add_argument("--queue-item-schema", default=str(DEFAULT_QUEUE_ITEM_SCHEMA))
    seed_parser.add_argument("--replace-existing", action="store_true")
    seed_parser.add_argument("--output", default=None)
    seed_parser.set_defaults(func=command_seed)

    ready_parser = subparsers.add_parser("list-ready")
    ready_parser.add_argument("--db", default="runtime-artifacts/scheduler-queue/runtime-queue.sqlite3")
    ready_parser.add_argument("--output", default=None)
    ready_parser.set_defaults(func=command_list_ready)

    transition_parser = subparsers.add_parser("record-transition")
    transition_parser.add_argument("--db", default="runtime-artifacts/scheduler-queue/runtime-queue.sqlite3")
    transition_parser.add_argument("--transition-json", required=True)
    transition_parser.add_argument("--lease-schema", default=str(DEFAULT_LEASE_SCHEMA))
    transition_parser.add_argument("--output", default=None)
    transition_parser.set_defaults(func=command_record_transition)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
