#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from local_outbox_dispatch_common import (
    DISPATCH_CYCLE_CONTRACT_REF,
    HANDOFF_CONTRACT_REF,
    default_dispatch_receipt_path,
    default_execution_packet_path,
    ensure_runtime_artifact_boundary,
    repo_relative,
    repo_root,
    require_string,
    resolve_path,
    write_json,
)
from runtime_evidence_contract import load_json


SUPPORTED_MESSAGE_CLASSES = {
    "status_update",
    "decision_request",
    "blocked_report",
    "goal_completed",
}
SUPPORTED_CHANNEL_KINDS = {"slack_skill_cli", "slack_skill_mcp", "email_cli", "email_mcp"}
BRIDGE_ADAPTER_KIND = "monday_local_operator_bridge"


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args():
    parser = argparse.ArgumentParser(
        description="Export a monday local dispatch execution packet from a ready local outbox dispatch packet"
    )
    parser.add_argument("--dispatch-packet-file", required=True)
    parser.add_argument("--output", default=None)
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
    require_string(packet, "message_class")
    require_string(packet, "channel_kind")
    require_string(packet, "delivery_target")
    require_string(packet, "delivery_idempotency_key")
    return packet


def load_outbox_envelope(packet: dict, *, root: Path) -> tuple[Path, dict, dict]:
    outbox_path = ensure_runtime_artifact_boundary(
        resolve_path(require_string(packet, "source_outbox_message_ref"), root=root),
        root=root,
    )
    envelope = load_json(outbox_path, None)
    if envelope is None:
        raise SystemExit(f"local outbox message not found: {outbox_path}")
    if require_string(envelope, "transport_kind") != "local_outbox":
        raise SystemExit("local outbox envelope transport_kind must be local_outbox")
    if require_string(envelope, "target_resolution_mode") != "local_profile":
        raise SystemExit("local outbox envelope target_resolution_mode must be local_profile")
    payload = envelope.get("payload")
    if not isinstance(payload, dict):
        raise SystemExit("local outbox envelope missing payload object")
    message_class = require_string(payload, "messageClass")
    if message_class not in SUPPORTED_MESSAGE_CLASSES:
        raise SystemExit(f"payload messageClass unsupported for local dispatch cycle: {message_class}")
    channel_kind = str((payload.get("target") or {}).get("channelKind") or "").strip()
    if channel_kind not in SUPPORTED_CHANNEL_KINDS:
        raise SystemExit(f"payload channelKind unsupported for local dispatch cycle: {channel_kind}")
    require_string(payload, "goalKey")
    require_string(payload, "body")
    return outbox_path, envelope, payload


def build_execution_packet(
    packet: dict,
    packet_path: Path,
    *,
    outbox_path: Path,
    payload: dict,
    root: Path,
) -> dict:
    delivery_idempotency_key = require_string(packet, "delivery_idempotency_key")
    receipt_path = ensure_runtime_artifact_boundary(
        default_dispatch_receipt_path(delivery_idempotency_key, root=root),
        root=root,
    )
    receipt_ref = repo_relative(receipt_path, root) if receipt_path.exists() else "-"
    thread_ref = str(((payload.get("target") or {}).get("threadRef") or "")).strip() or "-"
    execution_verdict = "already_dispatched" if receipt_path.exists() else "ready_for_local_bridge"
    return {
        "execution_packet_version": 1,
        "generated_at_utc": now_utc(),
        "dispatch_cycle_contract_ref": DISPATCH_CYCLE_CONTRACT_REF,
        "source_dispatch_packet_ref": repo_relative(packet_path, root),
        "source_outbox_message_ref": repo_relative(outbox_path, root),
        "goal_key": require_string(packet, "goal_key"),
        "message_class": require_string(packet, "message_class"),
        "channel_kind": require_string(packet, "channel_kind"),
        "delivery_target": require_string(packet, "delivery_target"),
        "delivery_idempotency_key": delivery_idempotency_key,
        "payload_body": require_string(payload, "body"),
        "thread_ref": thread_ref,
        "transport_kind": require_string(packet, "transport_kind"),
        "bridge_adapter_kind": BRIDGE_ADAPTER_KIND,
        "execution_verdict": execution_verdict,
        "dispatch_receipt_ref": receipt_ref,
        "target_resolution_mode": require_string(packet, "target_resolution_mode"),
        "target_profile_ref": require_string(packet, "target_profile_ref"),
    }


def export_execution_packet(dispatch_packet_file: str, *, output: str | None = None, root: Path | None = None) -> tuple[Path, dict]:
    root = root or repo_root()
    packet_path = ensure_runtime_artifact_boundary(resolve_path(dispatch_packet_file, root=root), root=root)
    packet = load_dispatch_packet(packet_path)
    outbox_path, _envelope, payload = load_outbox_envelope(packet, root=root)
    output_path = Path(output) if output else default_execution_packet_path(
        require_string(packet, "delivery_idempotency_key"),
        root=root,
    )
    execution_packet = build_execution_packet(
        packet,
        packet_path,
        outbox_path=outbox_path,
        payload=payload,
        root=root,
    )
    write_json(output_path, execution_packet)
    return ensure_runtime_artifact_boundary(output_path.resolve(), root=root), execution_packet


def main() -> int:
    args = parse_args()
    output_path, packet = export_execution_packet(args.dispatch_packet_file, output=args.output)
    packet["execution_packet_ref"] = repo_relative(output_path, repo_root())
    print(json.dumps(packet, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
