#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from export_local_outbox_dispatch_packet import export_dispatch_packet
from local_delivery_cycle_common import (
    default_delivery_cycle_report_path,
    default_delivery_report_path,
    now_utc,
    source_payload_ref,
)
from local_outbox_dispatch_common import ensure_runtime_artifact_boundary, repo_relative, repo_root, require_string, resolve_path
from operator_channel_cli_common import load_payload, write_report
from run_local_dispatch_cycle import run_dispatch_cycle
from send_goal_completion_notification import run_goal_completion_delivery
from supervisor_goal_completion_payloads import (
    build_payload,
    load_json as load_supervisor_json,
    resolve_goal_transition_report_path,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run one monday goal-completion local delivery cycle through outbox delivery, dispatch export, and local dispatch consumption"
    )
    parser.add_argument("--payload-file", default=None)
    parser.add_argument("--payload-json", default=None)
    parser.add_argument("--operator-report-file", default=None)
    parser.add_argument("--operator-summary-file", default=None)
    parser.add_argument("--goal-transition-report-file", default=None)
    parser.add_argument("--delivery-target", default=None)
    parser.add_argument("--channel-kind", default=None)
    parser.add_argument("--profiles-config", default=None)
    parser.add_argument("--mode", choices=["apply", "dry-run"], default=None)
    parser.add_argument("--delivery-report-file", default=None)
    parser.add_argument("--dispatch-packet-file", default=None)
    parser.add_argument("--execution-packet-file", default=None)
    parser.add_argument("--receipt-file", default=None)
    parser.add_argument("--output", default=None)
    return parser.parse_args()


def resolve_payload(args) -> tuple[dict, str | None]:
    explicit_payload = args.payload_file is not None or args.payload_json is not None
    supervisor_handoff = args.operator_report_file is not None or args.operator_summary_file is not None
    if explicit_payload and supervisor_handoff:
        raise SystemExit("payload inputs and supervisor handoff inputs are mutually exclusive")
    if explicit_payload:
        return load_payload(args.payload_file, args.payload_json), args.payload_file
    if args.operator_report_file or args.operator_summary_file:
        if not args.operator_report_file or not args.operator_summary_file:
            raise SystemExit("both --operator-report-file and --operator-summary-file are required")
        operator_report = load_supervisor_json(args.operator_report_file)
        operator_summary = Path(args.operator_summary_file).read_text(encoding="utf-8")
        transition_report_path = resolve_goal_transition_report_path(operator_report, args.goal_transition_report_file)
        transition_report = load_supervisor_json(transition_report_path)
        payload = build_payload(
            operator_report=operator_report,
            operator_summary_body=operator_summary,
            transition_report=transition_report,
            mode=args.mode,
            delivery_target=args.delivery_target,
            channel_kind=args.channel_kind,
            goal_transition_report_path=transition_report_path,
        )
        return payload, str(Path(args.operator_report_file).resolve())
    raise SystemExit("provide either payload input or supervisor handoff input")


def run_goal_completion_delivery_cycle(
    payload: dict,
    *,
    payload_file: str | None = None,
    profiles_config: str | None = None,
    mode: str = "apply",
    delivery_report_file: str | None = None,
    dispatch_packet_file: str | None = None,
    execution_packet_file: str | None = None,
    receipt_file: str | None = None,
    output: str | None = None,
    root: Path | None = None,
) -> tuple[Path, dict]:
    root = root or repo_root()
    delivery_result = run_goal_completion_delivery(
        payload,
        mode_override=mode,
        profiles_config=profiles_config,
        root=root,
    )
    delivery_report = delivery_result["delivery_report"]
    idempotency_key = require_string(delivery_report, "deliveryIdempotencyKey")
    delivery_report_path = (
        resolve_path(delivery_report_file, root=root)
        if delivery_report_file
        else default_delivery_report_path("goal-completion", idempotency_key, root=root)
    )
    delivery_report_path = ensure_runtime_artifact_boundary(delivery_report_path.resolve(), root=root)
    write_report(str(delivery_report_path), delivery_result)

    report = {
        "delivery_cycle_report_version": 1,
        "generated_at_utc": now_utc(),
        "entrypoint_script": "run_goal_completion_delivery_cycle.py",
        "source_payload_ref": source_payload_ref(payload_file, root=root),
        "delivery_report_ref": repo_relative(delivery_report_path.resolve(), root),
        "dispatch_packet_ref": "-",
        "execution_packet_ref": "-",
        "ack_checkpoint_ref": "-",
        "dispatch_receipt_ref": "-",
        "goal_key": require_string(delivery_report, "goalKey"),
        "message_class": require_string(delivery_report, "messageClass"),
        "channel_kind": require_string(delivery_report, "channelKind"),
        "delivery_idempotency_key": require_string(delivery_report, "deliveryIdempotencyKey"),
        "delivery_verdict": require_string(delivery_report, "deliveryVerdict"),
        "cycle_status": "blocked",
        "verdict": "fail",
    }

    if delivery_result["verdict"] != "pass":
        output_path = resolve_path(output, root=root) if output else default_delivery_cycle_report_path("goal-completion", idempotency_key, root=root)
        output_path = ensure_runtime_artifact_boundary(output_path.resolve(), root=root)
        write_report(str(output_path), report)
        return output_path, report

    if require_string(delivery_report, "deliveryVerdict") == "dry_run":
        report.update({"cycle_status": "dry_run", "verdict": "pass"})
        output_path = resolve_path(output, root=root) if output else default_delivery_cycle_report_path("goal-completion", idempotency_key, root=root)
        output_path = ensure_runtime_artifact_boundary(output_path.resolve(), root=root)
        write_report(str(output_path), report)
        return output_path, report

    if require_string(delivery_report, "deliveryVerdict") != "delivered_local_outbox":
        output_path = resolve_path(output, root=root) if output else default_delivery_cycle_report_path("goal-completion", idempotency_key, root=root)
        output_path = ensure_runtime_artifact_boundary(output_path.resolve(), root=root)
        write_report(str(output_path), report)
        return output_path, report

    dispatch_packet_path, dispatch_packet = export_dispatch_packet(
        repo_relative(delivery_report_path.resolve(), root),
        output=dispatch_packet_file,
        root=root,
    )
    cycle_report_path, cycle_report = run_dispatch_cycle(
        dispatch_packet_file=repo_relative(dispatch_packet_path, root),
        execution_packet_file=execution_packet_file,
        receipt_file=receipt_file,
        output=str(
            default_delivery_cycle_report_path("goal-completion-step", idempotency_key, root=root)
        ),
        root=root,
    )
    report.update(
        {
            "dispatch_packet_ref": repo_relative(dispatch_packet_path, root),
            "execution_packet_ref": str(cycle_report.get("execution_packet_ref") or "-"),
            "ack_checkpoint_ref": str(cycle_report.get("ack_checkpoint_ref") or "-"),
            "dispatch_receipt_ref": str(cycle_report.get("dispatch_receipt_ref") or "-"),
            "cycle_status": str(cycle_report.get("cycle_status") or "blocked"),
            "verdict": str(cycle_report.get("verdict") or "fail"),
            "step_cycle_report_ref": repo_relative(cycle_report_path, root),
            "dispatch_verdict": require_string(dispatch_packet, "dispatch_verdict"),
            "delivery_verdict": require_string(delivery_report, "deliveryVerdict"),
        }
    )
    output_path = resolve_path(output, root=root) if output else default_delivery_cycle_report_path("goal-completion", idempotency_key, root=root)
    output_path = ensure_runtime_artifact_boundary(output_path.resolve(), root=root)
    write_report(str(output_path), report)
    return output_path, report


def main() -> int:
    args = parse_args()
    payload, payload_file = resolve_payload(args)
    output_path, report = run_goal_completion_delivery_cycle(
        payload,
        payload_file=payload_file,
        profiles_config=args.profiles_config,
        mode=args.mode,
        delivery_report_file=args.delivery_report_file,
        dispatch_packet_file=args.dispatch_packet_file,
        execution_packet_file=args.execution_packet_file,
        receipt_file=args.receipt_file,
        output=args.output,
    )
    report["report_ref"] = repo_relative(output_path, repo_root())
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0 if report["verdict"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
