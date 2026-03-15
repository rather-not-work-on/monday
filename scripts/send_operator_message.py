#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from operator_channel_local_outbox import deliver_local_outbox, resolve_target
from operator_channel_cli_common import (
    SLACK_CHANNEL_KINDS,
    build_delivery_report,
    build_operator_idempotency_key,
    ensure_channel_kind,
    ensure_message_class,
    load_payload,
    normalize_mode,
    now_utc,
    require_string,
    write_report,
)


def parse_args():
    parser = argparse.ArgumentParser(description="Send monday operator-channel message payload through the CLI baseline")
    parser.add_argument("--payload-file", default=None)
    parser.add_argument("--payload-json", default=None)
    parser.add_argument("--mode", choices=["dry-run", "apply"], default=None)
    parser.add_argument("--profiles-config", default=None)
    parser.add_argument("--output", default="runtime-artifacts/messaging/operator-message-report.json")
    return parser.parse_args()


def main():
    args = parse_args()
    root = Path(__file__).resolve().parent.parent
    payload = load_payload(args.payload_file, args.payload_json)
    ensure_message_class(payload)
    ensure_channel_kind(payload, SLACK_CHANNEL_KINDS)
    require_string(payload, "goalKey")
    require_string(payload, "body")
    delivery_mode = normalize_mode(payload, args.mode)
    resolved_target = resolve_target(payload, profiles_config=args.profiles_config, root=root)
    idempotency_key = build_operator_idempotency_key(payload)
    outbox_message_ref = "-"
    if delivery_mode == "apply" and resolved_target["target_resolution_mode"] == "local_profile":
        outbox_message_ref = deliver_local_outbox(
            payload,
            idempotency_key=idempotency_key,
            resolved_target=resolved_target,
            root=root,
        )
        delivery_verdict = "delivered_local_outbox"
        errors = []
        verdict = "pass"
    elif delivery_mode == "dry-run":
        delivery_verdict = "dry_run"
        errors = []
        verdict = "pass"
    else:
        delivery_verdict = "blocked"
        errors = ["operator_transport_not_configured"]
        verdict = "fail"
    report = build_delivery_report(
        payload,
        delivery_verdict=delivery_verdict,
        idempotency_key=idempotency_key,
        timestamp_utc=now_utc(),
        target_resolution_mode=resolved_target["target_resolution_mode"],
        target_profile_ref=resolved_target["target_profile_ref"],
        transport_kind=resolved_target["transport_kind"],
        outbox_message_ref=outbox_message_ref,
    )
    result = {
        "generated_at_utc": now_utc(),
        "script": str(Path(__file__).name),
        "payload": payload,
        "delivery_report": report,
        "target_resolution_mode": resolved_target["target_resolution_mode"],
        "target_profile_ref": resolved_target["target_profile_ref"],
        "outbox_message_ref": outbox_message_ref,
        "errors": errors,
        "verdict": verdict,
    }
    write_report(args.output, result)
    print(f"report written: {args.output}")
    print(f"verdict={result['verdict']} delivery_verdict={report['deliveryVerdict']}")
    return 0 if result["verdict"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
