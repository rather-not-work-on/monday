#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from operator_channel_cli_common import (
    EMAIL_CHANNEL_KINDS,
    build_delivery_report,
    build_goal_completion_idempotency_key,
    ensure_channel_kind,
    ensure_message_class,
    load_payload,
    normalize_mode,
    now_utc,
    require_string,
    write_report,
)


def parse_args():
    parser = argparse.ArgumentParser(description="Send monday goal-completion notification payload through the CLI baseline")
    parser.add_argument("--payload-file", default=None)
    parser.add_argument("--payload-json", default=None)
    parser.add_argument("--mode", choices=["dry-run", "apply"], default=None)
    parser.add_argument("--output", default="runtime-artifacts/messaging/goal-completion-notification-report.json")
    return parser.parse_args()


def main():
    args = parse_args()
    payload = load_payload(args.payload_file, args.payload_json)
    ensure_message_class(payload, expected="goal_completed")
    ensure_channel_kind(payload, EMAIL_CHANNEL_KINDS)
    require_string(payload, "goalKey")
    require_string(payload, "body")
    require_string(payload, "achievedAtUtc")
    delivery_mode = normalize_mode(payload, args.mode)
    report = build_delivery_report(
        payload,
        delivery_verdict="dry_run" if delivery_mode == "dry-run" else "blocked",
        idempotency_key=build_goal_completion_idempotency_key(payload),
        timestamp_utc=now_utc(),
    )
    result = {
        "generated_at_utc": now_utc(),
        "script": str(Path(__file__).name),
        "payload": payload,
        "delivery_report": report,
        "errors": [] if delivery_mode == "dry-run" else ["goal_completion_transport_not_configured"],
        "verdict": "pass" if delivery_mode == "dry-run" else "fail",
    }
    write_report(args.output, result)
    print(f"report written: {args.output}")
    print(f"verdict={result['verdict']} delivery_verdict={report['deliveryVerdict']}")
    return 0 if result["verdict"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
