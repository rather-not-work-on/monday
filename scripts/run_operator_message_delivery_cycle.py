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
from send_operator_message import run_operator_message_delivery


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run one monday local operator-message delivery cycle through outbox delivery, dispatch export, and local dispatch consumption"
    )
    parser.add_argument("--payload-file", default=None)
    parser.add_argument("--payload-json", default=None)
    parser.add_argument("--profiles-config", default=None)
    parser.add_argument("--mode", choices=["apply", "dry-run"], default="apply")
    parser.add_argument("--delivery-report-file", default=None)
    parser.add_argument("--dispatch-packet-file", default=None)
    parser.add_argument("--execution-packet-file", default=None)
    parser.add_argument("--receipt-file", default=None)
    parser.add_argument("--output", default=None)
    return parser.parse_args()


def run_operator_delivery_cycle(
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
    delivery_result = run_operator_message_delivery(
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
        else default_delivery_report_path("operator-message", idempotency_key, root=root)
    )
    delivery_report_path = ensure_runtime_artifact_boundary(delivery_report_path.resolve(), root=root)
    write_report(str(delivery_report_path), delivery_result)

    report = {
        "delivery_cycle_report_version": 1,
        "generated_at_utc": now_utc(),
        "entrypoint_script": "run_operator_message_delivery_cycle.py",
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
        "cycle_status": "blocked",
        "verdict": "fail",
    }

    if delivery_result["verdict"] != "pass" or require_string(delivery_report, "deliveryVerdict") != "delivered_local_outbox":
        output_path = resolve_path(output, root=root) if output else default_delivery_cycle_report_path("operator-message", idempotency_key, root=root)
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
            default_delivery_cycle_report_path("operator-message-step", idempotency_key, root=root)
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
    output_path = resolve_path(output, root=root) if output else default_delivery_cycle_report_path("operator-message", idempotency_key, root=root)
    output_path = ensure_runtime_artifact_boundary(output_path.resolve(), root=root)
    write_report(str(output_path), report)
    return output_path, report


def main() -> int:
    args = parse_args()
    payload = load_payload(args.payload_file, args.payload_json)
    output_path, report = run_operator_delivery_cycle(
        payload,
        payload_file=args.payload_file,
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
