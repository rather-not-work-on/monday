#!/usr/bin/env python3

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys

from runtime_evidence_contract import load_json, validate_report


DEFAULT_TAXONOMY = Path("config/runtime-reason-taxonomy.json")
DEFAULT_SCHEMA = Path("contracts/runtime-integration-evidence.schema.json")

def now_utc():
    return datetime.now(timezone.utc).isoformat()


def run_cmd(cmd):
    completed = subprocess.run(cmd, capture_output=True, text=True)
    return completed.returncode, completed.stdout.strip(), completed.stderr.strip()


def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=True, indent=2), encoding="utf-8")


def build_handoff(last_run: dict, fallback_handoff: dict):
    if not last_run:
        return fallback_handoff

    issue_number = last_run.get("selected_issue") or fallback_handoff.get("issue_number", 0)
    loop_id = fallback_handoff.get("loop_id", f"loop-fallback-issue-{issue_number}")

    return {
        "issue_number": issue_number,
        "loop_id": loop_id,
        "ecp_ref": "planningops/templates/ecp-template.md",
        "delta_notes": "generated from planningops loop-runner last-run",
        "intake_check_ref": "planningops/artifacts/loops/<date>/<loop_id>/intake-check.json",
        "simulation_report_ref": "planningops/artifacts/loops/<date>/<loop_id>/simulation-report.md",
        "verification_report_ref": f"planningops/artifacts/verification/issue-{issue_number}-verification.json",
        "transition_log_ref": "planningops/artifacts/transition-log/<date>.ndjson",
        "recommended_next_step": "enqueue-runtime-worker",
        "blocker_if_any": "",
    }


def default_integration_path(run_id: str, filename: str) -> str:
    return f"runtime-artifacts/integration/{run_id}/{filename}"


def main():
    parser = argparse.ArgumentParser(description="Integrate planningops handoff with monday scheduler runner")
    parser.add_argument(
        "--planningops-last-run",
        default="../platform-planningops/planningops/artifacts/loop-runner/last-run.json",
    )
    parser.add_argument("--handoff-sample", default="fixtures/handoff-packet.sample.json")
    parser.add_argument("--queue-out", default=None)
    parser.add_argument("--handoff-report", default=None)
    parser.add_argument("--scheduler-report", default=None)
    parser.add_argument("--integration-report", default=None)
    parser.add_argument("--idempotency", default=None)
    parser.add_argument("--transition-log", default=None)
    parser.add_argument("--run-id", default=f"handoff-integration-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}")
    args = parser.parse_args()
    taxonomy = load_json(DEFAULT_TAXONOMY)

    queue_out = args.queue_out or default_integration_path(args.run_id, "queue.from-planningops.json")
    handoff_report_path = args.handoff_report or default_integration_path(args.run_id, "handoff-smoke-report.json")
    scheduler_report_path = args.scheduler_report or default_integration_path(args.run_id, "scheduler-run-report.json")
    integration_report_path = args.integration_report or default_integration_path(args.run_id, "planningops-handoff-report.json")
    idempotency_path = args.idempotency or default_integration_path(args.run_id, "idempotency.json")
    transition_log_path = args.transition_log or default_integration_path(args.run_id, "scheduler.ndjson")

    # Step 1: validate handoff map
    rc_map, out_map, err_map = run_cmd(
        [
            "python3",
            "scripts/validate_handoff_mapping.py",
            "--run-id",
            args.run_id,
            "--output",
            handoff_report_path,
        ]
    )
    handoff_report = load_json(Path(handoff_report_path), {})

    # Step 2: build handoff+queue from planningops run
    last_run = load_json(Path(args.planningops_last_run), {})
    fallback_handoff = load_json(Path(args.handoff_sample), {})
    handoff = build_handoff(last_run or {}, fallback_handoff or {})

    deps = []
    if isinstance(last_run, dict):
        deps = [d for d in (last_run.get("deps") or []) if isinstance(d, int)]

    queue_doc = {
        "items": [
            {
                "card_id": f"card-{handoff['issue_number']}",
                "issue_number": handoff["issue_number"],
                "status": "Todo",
                "depends_on": deps,
                "reason_history": [],
            }
        ],
        "completed_issues": deps,
    }
    save_json(Path(queue_out), queue_doc)

    # Step 3: run scheduler on generated queue
    rc_sched, out_sched, err_sched = run_cmd(
        [
            "python3",
            "scripts/scheduler_queue.py",
            "--queue",
            queue_out,
            "--run-id",
            args.run_id,
            "--report",
            scheduler_report_path,
            "--idempotency",
            idempotency_path,
            "--transition-log",
            transition_log_path,
        ]
    )
    scheduler_report = load_json(Path(scheduler_report_path), {})

    mismatch_count = int(handoff_report.get("mismatch_count", 9999))
    dequeued_count = int(scheduler_report.get("dequeued_count", 0))
    blocked_count = int(scheduler_report.get("blocked_count", 0))

    rollback_triggered = mismatch_count > 0 or dequeued_count == 0 or blocked_count > 0
    rollback_reason = []
    if mismatch_count > 0:
        rollback_reason.append("handoff_mapping_mismatch")
    if dequeued_count == 0:
        rollback_reason.append("scheduler_no_dequeue")
    if blocked_count > 0:
        rollback_reason.append("scheduler_blocked_cards")

    reason_code = rollback_reason[0] if rollback_reason else "ok"
    verdict = "pass" if not rollback_triggered and rc_map == 0 and rc_sched == 0 else "fail"

    report = {
        "generated_at_utc": now_utc(),
        "run_id": args.run_id,
        "verdict": verdict,
        "reason_code": reason_code,
        "reason_taxonomy_version": int(taxonomy.get("version", 0)),
        "handoff_validation": {
            "exit_code": rc_map,
            "stdout": out_map[-1000:],
            "stderr": err_map[-1000:],
            "report_path": handoff_report_path,
            "mismatch_count": mismatch_count,
        },
        "scheduler_execution": {
            "exit_code": rc_sched,
            "stdout": out_sched[-1000:],
            "stderr": err_sched[-1000:],
            "report_path": scheduler_report_path,
            "dequeued_count": dequeued_count,
            "blocked_count": blocked_count,
            "duplicate_count": int(scheduler_report.get("duplicate_count", 0)),
        },
        "rollback_trigger": {
            "triggered": rollback_triggered,
            "reasons": rollback_reason,
            "policy": "trigger when handoff mismatch exists, or no dequeue, or blocked cards > 0",
        },
        "queue_path": queue_out,
    }

    validate_report(report, DEFAULT_SCHEMA, DEFAULT_TAXONOMY)
    save_json(Path(integration_report_path), report)

    print(f"integration report written: {integration_report_path}")
    print(
        f"verdict={verdict} reason_code={reason_code} mismatch_count={mismatch_count} dequeued={dequeued_count} blocked={blocked_count}"
    )
    return 0 if verdict == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
