#!/usr/bin/env python3

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from local_outbox_dispatch_common import repo_relative, repo_root, safe_slug


DEFAULT_DELIVERY_REPORT_ROOT = "runtime-artifacts/messaging/delivery-reports"
DEFAULT_DELIVERY_CYCLE_REPORT_ROOT = "runtime-artifacts/messaging/delivery-cycles"


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_delivery_report_path(kind: str, idempotency_key: str, *, root: Path) -> Path:
    return root / DEFAULT_DELIVERY_REPORT_ROOT / f"{safe_slug(kind)}-{safe_slug(idempotency_key)}.json"


def default_delivery_cycle_report_path(kind: str, idempotency_key: str, *, root: Path) -> Path:
    return root / DEFAULT_DELIVERY_CYCLE_REPORT_ROOT / f"{safe_slug(kind)}-{safe_slug(idempotency_key)}.json"


def source_payload_ref(payload_file: str | None, *, root: Path | None = None) -> str:
    if not payload_file:
        return "-"
    root = root or repo_root()
    path = Path(payload_file).resolve()
    try:
        return repo_relative(path, root)
    except Exception:
        return str(path)
