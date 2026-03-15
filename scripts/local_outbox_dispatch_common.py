#!/usr/bin/env python3

from __future__ import annotations

import re
from pathlib import Path

from runtime_evidence_contract import load_json
from runtime_queue_store import save_json


HANDOFF_CONTRACT_REF = "planningops/contracts/local-outbox-dispatch-handoff-contract.md"
DISPATCH_CYCLE_CONTRACT_REF = "planningops/contracts/local-dispatch-cycle-handoff-contract.md"
DEFAULT_DISPATCH_ROOT = "runtime-artifacts/messaging/dispatch-packets"
DEFAULT_ACK_ROOT = "runtime-artifacts/messaging/dispatch-acks"
DEFAULT_EXECUTION_ROOT = "runtime-artifacts/messaging/dispatch-execution-packets"
DEFAULT_RECEIPT_ROOT = "runtime-artifacts/messaging/dispatch-receipts"


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def repo_relative(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def require_string(doc: dict, key: str) -> str:
    value = str(doc.get(key) or "").strip()
    if not value:
        raise SystemExit(f"missing required field: {key}")
    return value


def safe_slug(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value).strip()).strip("-")
    return text or "default"


def load_delivery_wrapper(path: Path) -> tuple[dict, dict]:
    wrapper = load_json(path, None)
    if wrapper is None:
        raise SystemExit(f"delivery report file not found: {path}")
    delivery_report = wrapper.get("delivery_report")
    if not isinstance(delivery_report, dict):
        raise SystemExit("delivery wrapper missing delivery_report object")
    return wrapper, delivery_report


def resolve_path(ref: str, *, root: Path) -> Path:
    path = Path(str(ref).strip())
    if not path.is_absolute():
        path = root / path
    return path


def ensure_runtime_artifact_boundary(path: Path, *, root: Path) -> Path:
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise SystemExit(f"artifact path escapes monday repo root: {path}") from exc
    if not relative.parts or relative.parts[0] != "runtime-artifacts":
        raise SystemExit(f"artifact path must stay under runtime-artifacts/: {path}")
    return resolved


def default_dispatch_packet_path(idempotency_key: str, *, root: Path) -> Path:
    return root / DEFAULT_DISPATCH_ROOT / f"{safe_slug(idempotency_key)}.json"


def default_ack_checkpoint_path(idempotency_key: str, *, root: Path) -> Path:
    return root / DEFAULT_ACK_ROOT / f"{safe_slug(idempotency_key)}.json"


def default_execution_packet_path(idempotency_key: str, *, root: Path) -> Path:
    return root / DEFAULT_EXECUTION_ROOT / f"{safe_slug(idempotency_key)}.json"


def default_dispatch_receipt_path(idempotency_key: str, *, root: Path) -> Path:
    return root / DEFAULT_RECEIPT_ROOT / f"{safe_slug(idempotency_key)}.json"


def write_json(path: Path, payload: dict) -> None:
    save_json(path, payload)
