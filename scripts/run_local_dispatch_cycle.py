#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from ack_local_outbox_dispatch import record_ack_checkpoint
from export_local_dispatch_execution_packet import export_execution_packet, load_dispatch_packet
from local_outbox_dispatch_common import (
    DISPATCH_CYCLE_CONTRACT_REF,
    DEFAULT_DISPATCH_ROOT,
    default_dispatch_receipt_path,
    ensure_runtime_artifact_boundary,
    repo_relative,
    repo_root,
    require_string,
    resolve_path,
    write_json,
)
from runtime_evidence_contract import load_json


DEFAULT_REPORT_PATH = "runtime-artifacts/messaging/local-dispatch-cycle-report.json"


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run one monday local dispatch cycle from a ready local outbox dispatch packet"
    )
    parser.add_argument("--dispatch-packet-file", default=None)
    parser.add_argument("--execution-packet-file", default=None)
    parser.add_argument("--receipt-file", default=None)
    parser.add_argument("--ack-reason", default="dispatch_consumed_by_local_skill_boundary")
    parser.add_argument("--output", default=DEFAULT_REPORT_PATH)
    return parser.parse_args()


def select_ready_dispatch_packet(*, root: Path) -> tuple[Path | None, str]:
    dispatch_root = ensure_runtime_artifact_boundary((root / DEFAULT_DISPATCH_ROOT).resolve(), root=root)
    if not dispatch_root.exists():
        return None, "dispatch_root_missing"
    candidates = sorted(dispatch_root.glob("*.json"))
    for candidate in candidates:
        if candidate.name.startswith("._"):
            continue
        packet = load_dispatch_packet(candidate)
        if require_string(packet, "dispatch_verdict") != "ready_for_dispatch":
            continue
        receipt_path = default_dispatch_receipt_path(require_string(packet, "delivery_idempotency_key"), root=root)
        if receipt_path.exists():
            continue
        return candidate, "first_ready_packet"
    return None, "no_ready_dispatch_packet"


def build_receipt(
    execution_packet: dict,
    *,
    execution_packet_ref: str,
    dispatch_packet_ref: str,
    ack_checkpoint_ref: str,
    receipt_checkpoint_ref: str,
    receipt_reason: str,
) -> dict:
    return {
        "dispatch_receipt_version": 1,
        "generated_at_utc": now_utc(),
        "dispatch_cycle_contract_ref": DISPATCH_CYCLE_CONTRACT_REF,
        "source_execution_packet_ref": execution_packet_ref,
        "dispatch_packet_ref": dispatch_packet_ref,
        "ack_checkpoint_ref": ack_checkpoint_ref,
        "goal_key": require_string(execution_packet, "goal_key"),
        "delivery_idempotency_key": require_string(execution_packet, "delivery_idempotency_key"),
        "channel_kind": require_string(execution_packet, "channel_kind"),
        "receipt_status": "recorded",
        "receipt_reason": receipt_reason,
        "receipt_checkpoint_ref": receipt_checkpoint_ref,
        "transport_kind": require_string(execution_packet, "transport_kind"),
        "bridge_adapter_kind": require_string(execution_packet, "bridge_adapter_kind"),
        "verdict": "pass",
    }


def record_receipt(
    execution_packet: dict,
    *,
    execution_packet_path: Path,
    dispatch_packet_path: Path,
    ack_checkpoint_ref: str,
    receipt_file: str | None,
    root: Path,
) -> tuple[Path, dict, str]:
    delivery_idempotency_key = require_string(execution_packet, "delivery_idempotency_key")
    receipt_path = (
        Path(receipt_file)
        if receipt_file
        else default_dispatch_receipt_path(delivery_idempotency_key, root=root)
    )
    receipt_path = ensure_runtime_artifact_boundary(receipt_path.resolve(), root=root)
    receipt_ref = repo_relative(receipt_path, root)
    if receipt_path.exists():
        receipt = load_json(receipt_path, None)
        if receipt is None:
            raise SystemExit(f"dispatch receipt unreadable: {receipt_path}")
        return receipt_path, receipt, "already_recorded"
    receipt = build_receipt(
        execution_packet,
        execution_packet_ref=repo_relative(execution_packet_path, root),
        dispatch_packet_ref=repo_relative(dispatch_packet_path, root),
        ack_checkpoint_ref=ack_checkpoint_ref,
        receipt_checkpoint_ref=receipt_ref,
        receipt_reason="local_dispatch_cycle_recorded",
    )
    write_json(receipt_path, receipt)
    return receipt_path, receipt, "recorded"


def run_dispatch_cycle(
    *,
    dispatch_packet_file: str | None = None,
    execution_packet_file: str | None = None,
    receipt_file: str | None = None,
    ack_reason: str = "dispatch_consumed_by_local_skill_boundary",
    output: str = DEFAULT_REPORT_PATH,
    root: Path | None = None,
) -> tuple[Path, dict]:
    root = root or repo_root()

    if dispatch_packet_file:
        dispatch_packet_path = ensure_runtime_artifact_boundary(
            resolve_path(dispatch_packet_file, root=root).resolve(),
            root=root,
        )
        selection_mode = "explicit_argument"
    else:
        selected, selection_mode = select_ready_dispatch_packet(root=root)
        if selected is None:
            report = {
                "generated_at_utc": now_utc(),
                "script": str(Path(__file__).name),
                "selection_mode": selection_mode,
                "selected_dispatch_packet_ref": "-",
                "cycle_status": "no_ready_dispatch_packet",
                "verdict": "pass",
            }
            report_path = resolve_path(output, root=root)
            write_json(report_path, report)
            return ensure_runtime_artifact_boundary(report_path.resolve(), root=root), report
        dispatch_packet_path = selected

    execution_packet_path, execution_packet = export_execution_packet(
        repo_relative(dispatch_packet_path, root),
        output=execution_packet_file,
        root=root,
    )
    ack_checkpoint_path, ack_result = record_ack_checkpoint(
        repo_relative(dispatch_packet_path, root),
        ack_reason=ack_reason,
        root=root,
    )
    receipt_path, receipt, cycle_status = record_receipt(
        execution_packet,
        execution_packet_path=execution_packet_path,
        dispatch_packet_path=dispatch_packet_path,
        ack_checkpoint_ref=ack_result["ack_checkpoint_ref"],
        receipt_file=receipt_file,
        root=root,
    )
    report = {
        "generated_at_utc": now_utc(),
        "script": str(Path(__file__).name),
        "selection_mode": selection_mode,
        "selected_dispatch_packet_ref": repo_relative(dispatch_packet_path, root),
        "execution_packet_ref": repo_relative(execution_packet_path, root),
        "execution_verdict": require_string(execution_packet, "execution_verdict"),
        "ack_checkpoint_ref": repo_relative(ack_checkpoint_path, root),
        "ack_status": ack_result["ack_status"],
        "dispatch_receipt_ref": repo_relative(receipt_path, root),
        "cycle_status": cycle_status,
        "receipt_status": require_string(receipt, "receipt_status"),
        "verdict": "pass",
    }
    report_path = resolve_path(output, root=root)
    write_json(report_path, report)
    return ensure_runtime_artifact_boundary(report_path.resolve(), root=root), report


def main() -> int:
    args = parse_args()
    report_path, report = run_dispatch_cycle(
        dispatch_packet_file=args.dispatch_packet_file,
        execution_packet_file=args.execution_packet_file,
        receipt_file=args.receipt_file,
        ack_reason=args.ack_reason,
        output=args.output,
    )
    report["report_ref"] = repo_relative(report_path, repo_root())
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
