#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from runtime_evidence_contract import load_json
from runtime_queue_store import DEFAULT_WORKER_OUTCOME_SCHEMA, load_validator, save_json


SOURCE_REPO = "rather-not-work-on/monday"
SOURCE_CONTRACT_REF = "platform-contracts/schemas/runtime-queue-worker-outcome.schema.json"
REFLECTION_CONTRACT_REF = "planningops/contracts/worker-outcome-reflection-contract.md"


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args():
    parser = argparse.ArgumentParser(description="Export monday worker outcomes as reflection packets for planningops")
    parser.add_argument("--outcome-json", required=True)
    parser.add_argument("--worker-outcome-schema", default=str(DEFAULT_WORKER_OUTCOME_SCHEMA))
    parser.add_argument("--source-outcome-ref", default=None)
    parser.add_argument("--output", default="runtime-artifacts/worker-outcome-reflection/reflection-packet.json")
    return parser.parse_args()


def derive_outcome_class(state_to: str) -> str:
    if state_to == "completed":
        return "completion"
    if state_to == "retry_wait":
        return "retry_wait"
    if state_to == "dead_letter":
        return "dead_letter"
    raise ValueError(f"unsupported worker outcome state_to: {state_to}")


def derive_allowed_decisions(outcome_class: str) -> list[str]:
    mapping = {
        "completion": ["continue", "goal_achieved"],
        "retry_wait": ["continue"],
        "dead_letter": ["replan_required", "operator_notify"],
    }
    return mapping[outcome_class]


def build_reflection_hints(outcome: dict) -> dict:
    outcome_class = derive_outcome_class(outcome["state_to"])
    retry_exhausted = outcome["state_to"] == "dead_letter" or (
        outcome["state_to"] == "retry_wait" and int(outcome["retry_budget_remaining"]) == 0
    )
    dead_letter = outcome["state_to"] == "dead_letter"
    operator_attention_recommended = retry_exhausted or bool(outcome.get("dead_letter_reason"))
    return {
        "outcome_class": outcome_class,
        "completion_candidate": outcome_class == "completion",
        "retry_exhausted": retry_exhausted,
        "dead_letter": dead_letter,
        "operator_attention_recommended": operator_attention_recommended,
        "allowed_decisions": derive_allowed_decisions(outcome_class),
    }


def main() -> int:
    args = parse_args()
    outcome_validator = load_validator(Path(args.worker_outcome_schema))
    outcome = load_json(Path(args.outcome_json), None)
    if outcome is None:
        raise SystemExit(f"worker outcome json not found: {args.outcome_json}")
    outcome_validator.validate(outcome)

    packet = {
        "packet_version": 1,
        "exported_at_utc": now_utc(),
        "source_repo": SOURCE_REPO,
        "source_contract_ref": SOURCE_CONTRACT_REF,
        "reflection_contract_ref": REFLECTION_CONTRACT_REF,
        "source_outcome_ref": args.source_outcome_ref or args.outcome_json,
        "worker_outcome": outcome,
        "reflection_hints": build_reflection_hints(outcome),
    }
    save_json(Path(args.output), packet)
    print(json.dumps(packet, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
