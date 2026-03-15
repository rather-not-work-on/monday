#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from local_outbox_dispatch_common import (
    HANDOFF_CONTRACT_REF,
    default_ack_checkpoint_path,
    default_dispatch_packet_path,
    ensure_runtime_artifact_boundary,
    load_delivery_wrapper,
    repo_relative,
    repo_root,
    require_string,
    resolve_path,
    write_json,
)
from runtime_evidence_contract import load_json


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args():
    parser = argparse.ArgumentParser(
        description="Export a monday local outbox delivery report into a deterministic dispatch packet"
    )
    parser.add_argument("--delivery-report-file", required=True)
    parser.add_argument("--output", default=None)
    return parser.parse_args()


def validate_delivery_report(delivery_report: dict) -> str:
    if require_string(delivery_report, "deliveryVerdict") != "delivered_local_outbox":
        raise SystemExit("delivery report must have deliveryVerdict=delivered_local_outbox")
    if require_string(delivery_report, "targetResolutionMode") != "local_profile":
        raise SystemExit("delivery report must have targetResolutionMode=local_profile")
    if require_string(delivery_report, "transportKind") != "local_outbox":
        raise SystemExit("delivery report must have transportKind=local_outbox")
    require_string(delivery_report, "goalKey")
    require_string(delivery_report, "messageClass")
    require_string(delivery_report, "channelKind")
    require_string(delivery_report, "deliveryTarget")
    require_string(delivery_report, "targetProfileRef")
    require_string(delivery_report, "outboxMessageRef")
    return require_string(delivery_report, "deliveryIdempotencyKey")


def load_outbox_envelope(outbox_ref: str, *, root: Path) -> tuple[Path, dict]:
    outbox_path = ensure_runtime_artifact_boundary(resolve_path(outbox_ref, root=root), root=root)
    envelope = load_json(outbox_path, None)
    if envelope is None:
        raise SystemExit(f"local outbox message not found: {outbox_path}")
    if require_string(envelope, "transport_kind") != "local_outbox":
        raise SystemExit("local outbox envelope transport_kind must be local_outbox")
    if require_string(envelope, "target_resolution_mode") != "local_profile":
        raise SystemExit("local outbox envelope target_resolution_mode must be local_profile")
    return outbox_path, envelope


def export_dispatch_packet(
    delivery_report_file: str,
    *,
    output: str | None = None,
    root: Path | None = None,
) -> tuple[Path, dict]:
    root = root or repo_root()
    report_path = resolve_path(delivery_report_file, root=root)
    wrapper, delivery_report = load_delivery_wrapper(report_path)
    delivery_idempotency_key = validate_delivery_report(delivery_report)

    outbox_path, envelope = load_outbox_envelope(
        require_string(delivery_report, "outboxMessageRef"),
        root=root,
    )

    if require_string(envelope, "delivery_idempotency_key") != delivery_idempotency_key:
        raise SystemExit("deliveryIdempotencyKey mismatch between delivery report and outbox envelope")
    if require_string(envelope, "delivery_target") != require_string(delivery_report, "deliveryTarget"):
        raise SystemExit("deliveryTarget mismatch between delivery report and outbox envelope")
    if require_string(envelope, "channel_kind") != require_string(delivery_report, "channelKind"):
        raise SystemExit("channelKind mismatch between delivery report and outbox envelope")

    ack_path = ensure_runtime_artifact_boundary(
        default_ack_checkpoint_path(delivery_idempotency_key, root=root),
        root=root,
    )
    dispatch_verdict = "already_acknowledged" if ack_path.exists() else "ready_for_dispatch"
    output_path = resolve_path(output, root=root) if output else default_dispatch_packet_path(delivery_idempotency_key, root=root)

    packet = {
        "dispatch_packet_version": 1,
        "generated_at_utc": now_utc(),
        "dispatch_contract_ref": HANDOFF_CONTRACT_REF,
        "source_delivery_report_ref": repo_relative(report_path, root),
        "source_outbox_message_ref": repo_relative(outbox_path, root),
        "goal_key": require_string(delivery_report, "goalKey"),
        "message_class": require_string(delivery_report, "messageClass"),
        "channel_kind": require_string(delivery_report, "channelKind"),
        "delivery_target": require_string(delivery_report, "deliveryTarget"),
        "delivery_idempotency_key": delivery_idempotency_key,
        "target_resolution_mode": require_string(delivery_report, "targetResolutionMode"),
        "target_profile_ref": require_string(delivery_report, "targetProfileRef"),
        "transport_kind": require_string(delivery_report, "transportKind"),
        "dispatch_verdict": dispatch_verdict,
        "dispatch_ack_checkpoint_ref": repo_relative(ack_path, root) if ack_path.exists() else "-",
        "source_delivery_script": str(wrapper.get("script") or "-"),
    }
    write_json(output_path, packet)
    return ensure_runtime_artifact_boundary(output_path.resolve(), root=root), packet


def main() -> int:
    args = parse_args()
    output_path, packet = export_dispatch_packet(args.delivery_report_file, output=args.output)
    packet["dispatch_packet_ref"] = repo_relative(output_path, repo_root())
    print(json.dumps(packet, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
