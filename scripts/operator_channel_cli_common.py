#!/usr/bin/env python3

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path


VALID_DELIVERY_MODES = {"dry-run", "apply"}
VALID_MESSAGE_CLASSES = {
    "goal_intake_ack",
    "status_update",
    "decision_request",
    "blocked_report",
    "goal_completed",
}
SLACK_CHANNEL_KINDS = {"slack_skill_cli", "slack_skill_mcp"}
EMAIL_CHANNEL_KINDS = {"email_cli", "email_mcp"}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_payload(payload_file: str | None, payload_json: str | None) -> dict:
    if bool(payload_file) == bool(payload_json):
        raise SystemExit("exactly one of --payload-file or --payload-json is required")
    if payload_file:
        return json.loads(Path(payload_file).read_text(encoding="utf-8"))
    return json.loads(payload_json or "{}")


def require_string(doc: dict, key: str) -> str:
    value = str(doc.get(key) or "").strip()
    if not value:
        raise SystemExit(f"payload missing {key}")
    return value


def require_target(doc: dict, *, require_delivery_target: bool = True) -> dict:
    target = doc.get("target")
    if not isinstance(target, dict):
        raise SystemExit("payload missing target object")
    require_string(target, "channelKind")
    if require_delivery_target:
        require_string(target, "deliveryTarget")
    return target


def normalize_mode(doc: dict, mode_override: str | None) -> str:
    mode = str(mode_override or doc.get("deliveryMode") or "").strip()
    if mode not in VALID_DELIVERY_MODES:
        raise SystemExit(f"deliveryMode invalid: {mode}")
    doc["deliveryMode"] = mode
    return mode


def ensure_message_class(doc: dict, expected: str | None = None) -> str:
    message_class = require_string(doc, "messageClass")
    if message_class not in VALID_MESSAGE_CLASSES:
        raise SystemExit(f"messageClass invalid: {message_class}")
    if expected and message_class != expected:
        raise SystemExit(f"messageClass must be {expected}")
    return message_class


def ensure_channel_kind(doc: dict, allowed_kinds: set[str]) -> str:
    target = require_target(doc, require_delivery_target=False)
    channel_kind = str(target["channelKind"]).strip()
    if channel_kind not in allowed_kinds:
        raise SystemExit(f"channelKind invalid for this command: {channel_kind}")
    return channel_kind


def build_operator_idempotency_key(doc: dict) -> str:
    target = require_target(doc)
    return ":".join(
        [
            require_string(doc, "messageClass"),
            require_string(doc, "goalKey"),
            str(target["channelKind"]).strip(),
            str(target["deliveryTarget"]).strip(),
            str(doc.get("runId") or "-").strip() or "-",
            str(doc.get("taskId") or "-").strip() or "-",
        ]
    )


def build_goal_completion_idempotency_key(doc: dict) -> str:
    target = require_target(doc)
    return ":".join(
        [
            require_string(doc, "goalKey"),
            require_string(doc, "achievedAtUtc"),
            str(target["channelKind"]).strip(),
            str(target["deliveryTarget"]).strip(),
        ]
    )


def build_delivery_report(
    doc: dict,
    *,
    delivery_verdict: str,
    idempotency_key: str,
    timestamp_utc: str,
    target_resolution_mode: str | None = None,
    target_profile_ref: str | None = None,
    transport_kind: str | None = None,
    outbox_message_ref: str | None = None,
) -> dict:
    target = require_target(doc)
    report = {
        "messageClass": require_string(doc, "messageClass"),
        "goalKey": require_string(doc, "goalKey"),
        "deliveryMode": require_string(doc, "deliveryMode"),
        "channelKind": str(target["channelKind"]).strip(),
        "deliveryTarget": str(target["deliveryTarget"]).strip(),
        "deliveryVerdict": delivery_verdict,
        "deliveryTimestampUtc": timestamp_utc,
        "deliveryIdempotencyKey": idempotency_key,
        "threadRef": str(target.get("threadRef") or "").strip() or None,
    }
    if target_resolution_mode is not None:
        report["targetResolutionMode"] = target_resolution_mode
    if target_profile_ref is not None:
        report["targetProfileRef"] = target_profile_ref
    if transport_kind is not None:
        report["transportKind"] = transport_kind
    if outbox_message_ref is not None:
        report["outboxMessageRef"] = outbox_message_ref
    return report


def write_report(path: str, payload: dict) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
