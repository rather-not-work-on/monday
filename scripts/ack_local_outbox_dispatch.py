#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from local_outbox_dispatch_common import (
    HANDOFF_CONTRACT_REF,
    default_ack_checkpoint_path,
    ensure_runtime_artifact_boundary,
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
        description="Record deterministic acknowledgement checkpoints for monday local outbox dispatch packets"
    )
    parser.add_argument("--dispatch-packet-file", required=True)
    parser.add_argument("--ack-reason", default="dispatch_consumed_by_local_skill_boundary")
    parser.add_argument("--output", default="runtime-artifacts/messaging/dispatch-ack-report.json")
    return parser.parse_args()


def load_dispatch_packet(path: Path) -> dict:
    packet = load_json(path, None)
    if packet is None:
        raise SystemExit(f"dispatch packet not found: {path}")
    if int(packet.get("dispatch_packet_version") or 0) != 1:
        raise SystemExit("dispatch packet version must be 1")
    if require_string(packet, "dispatch_contract_ref") != HANDOFF_CONTRACT_REF:
        raise SystemExit("dispatch packet contract ref mismatch")
    if require_string(packet, "transport_kind") != "local_outbox":
        raise SystemExit("dispatch packet transport_kind must be local_outbox")
    if require_string(packet, "target_resolution_mode") != "local_profile":
        raise SystemExit("dispatch packet target_resolution_mode must be local_profile")
    if require_string(packet, "dispatch_verdict") not in {"ready_for_dispatch", "already_acknowledged"}:
        raise SystemExit("dispatch packet must be ready_for_dispatch or already_acknowledged")
    require_string(packet, "source_outbox_message_ref")
    require_string(packet, "goal_key")
    require_string(packet, "delivery_idempotency_key")
    require_string(packet, "channel_kind")
    return packet


def build_checkpoint(packet: dict, checkpoint_ref: str, ack_reason: str) -> dict:
    return {
        "dispatch_ack_version": 1,
        "generated_at_utc": now_utc(),
        "dispatch_contract_ref": HANDOFF_CONTRACT_REF,
        "dispatch_packet_ref": require_string(packet, "dispatch_packet_ref")
        if "dispatch_packet_ref" in packet
        else "-",
        "source_outbox_message_ref": require_string(packet, "source_outbox_message_ref"),
        "goal_key": require_string(packet, "goal_key"),
        "delivery_idempotency_key": require_string(packet, "delivery_idempotency_key"),
        "channel_kind": require_string(packet, "channel_kind"),
        "ack_status": "recorded",
        "ack_reason": ack_reason,
        "ack_checkpoint_ref": checkpoint_ref,
        "transport_kind": require_string(packet, "transport_kind"),
        "message_class": require_string(packet, "message_class"),
        "verdict": "pass",
    }


def record_ack_checkpoint(
    dispatch_packet_file: str,
    *,
    ack_reason: str,
    root: Path | None = None,
) -> tuple[Path, dict]:
    root = root or repo_root()
    packet_path = resolve_path(dispatch_packet_file, root=root)
    packet = load_dispatch_packet(packet_path)

    ensure_runtime_artifact_boundary(
        resolve_path(require_string(packet, "source_outbox_message_ref"), root=root),
        root=root,
    )
    checkpoint_path = ensure_runtime_artifact_boundary(
        default_ack_checkpoint_path(require_string(packet, "delivery_idempotency_key"), root=root),
        root=root,
    )
    checkpoint_ref = repo_relative(checkpoint_path, root)
    dispatch_packet_ref = repo_relative(packet_path, root)

    if checkpoint_path.exists():
        checkpoint = load_json(checkpoint_path, None)
        if checkpoint is None:
            raise SystemExit(f"ack checkpoint unreadable: {checkpoint_path}")
        ack_status = "already_recorded"
        ack_reason = require_string(checkpoint, "ack_reason")
    else:
        checkpoint = build_checkpoint(packet, checkpoint_ref, ack_reason)
        checkpoint["dispatch_packet_ref"] = dispatch_packet_ref
        write_json(checkpoint_path, checkpoint)
        ack_status = "recorded"

    return checkpoint_path, {
        "dispatch_packet_file": dispatch_packet_ref,
        "ack_status": ack_status,
        "ack_reason": ack_reason,
        "ack_checkpoint_ref": checkpoint_ref,
        "ack_checkpoint": checkpoint,
    }


def main() -> int:
    args = parse_args()
    root = repo_root()
    _checkpoint_path, ack_result = record_ack_checkpoint(
        args.dispatch_packet_file,
        ack_reason=args.ack_reason,
        root=root,
    )
    report = {
        "generated_at_utc": now_utc(),
        "script": str(Path(__file__).name),
        **ack_result,
        "verdict": "pass",
    }
    write_json(Path(args.output), report)
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
