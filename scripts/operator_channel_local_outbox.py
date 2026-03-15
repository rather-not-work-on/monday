#!/usr/bin/env python3

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re


DEFAULT_PROFILES_CONFIG = "config/local-operator-channel-profiles.json"


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def require_target(doc: dict) -> dict:
    target = doc.get("target")
    if not isinstance(target, dict):
        raise SystemExit("payload missing target object")
    require_string(target, "channelKind")
    return target


def resolve_profiles_config_path(root: Path, config_path: str | None) -> Path:
    raw = str(config_path or DEFAULT_PROFILES_CONFIG).strip()
    path = Path(raw)
    if not path.is_absolute():
        path = root / path
    return path


def load_local_profiles(root: Path, config_path: str | None = None) -> tuple[Path, dict]:
    path = resolve_profiles_config_path(root, config_path)
    if not path.exists():
        raise SystemExit(f"local operator channel profile config missing: {path}")
    doc = json.loads(path.read_text(encoding="utf-8"))
    profiles = doc.get("profiles")
    if not isinstance(profiles, dict) or not profiles:
        raise SystemExit("local operator channel profile config missing profiles object")
    return path, doc


def resolve_profile(doc: dict, channel_kind: str) -> dict:
    profiles = doc.get("profiles") or {}
    profile = profiles.get(channel_kind)
    if not isinstance(profile, dict):
        raise SystemExit(f"no local operator channel profile for channelKind={channel_kind}")
    for key in ["channel_kind", "transport_kind", "outbox_root", "default_target_name", "supports_threads"]:
        if key not in profile:
            raise SystemExit(f"local operator channel profile missing {key} for channelKind={channel_kind}")
    if str(profile.get("channel_kind") or "").strip() != channel_kind:
        raise SystemExit(f"profile channel_kind mismatch for channelKind={channel_kind}")
    if str(profile.get("transport_kind") or "").strip() != "local_outbox":
        raise SystemExit(f"unsupported transport_kind for channelKind={channel_kind}")
    if not isinstance(profile.get("supports_threads"), bool):
        raise SystemExit(f"supports_threads must be boolean for channelKind={channel_kind}")
    return profile


def safe_slug(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value).strip()).strip("-")
    return text or "default"


def resolve_target(payload: dict, *, profiles_config: str | None = None, root: Path | None = None) -> dict:
    root = root or repo_root()
    target = require_target(payload)
    channel_kind = str(target.get("channelKind") or "").strip()
    explicit_target = str(target.get("deliveryTarget") or "").strip()
    if explicit_target:
        return {
            "payload": payload,
            "channel_kind": channel_kind,
            "delivery_target": explicit_target,
            "target_resolution_mode": "explicit_argument",
            "target_profile_ref": "-",
            "transport_kind": "-",
            "outbox_root": "-",
        }

    config_path, doc = load_local_profiles(root, profiles_config)
    profile = resolve_profile(doc, channel_kind)
    if target.get("threadRef") and not profile["supports_threads"]:
        raise SystemExit(f"channelKind={channel_kind} does not support threadRef")

    target["deliveryTarget"] = f"local-outbox://{profile['default_target_name']}"
    return {
        "payload": payload,
        "channel_kind": channel_kind,
        "delivery_target": str(target["deliveryTarget"]),
        "target_resolution_mode": "local_profile",
        "target_profile_ref": f"{repo_relative(config_path, root)}#/profiles/{channel_kind}",
        "transport_kind": str(profile["transport_kind"]),
        "outbox_root": str(profile["outbox_root"]),
        "default_target_name": str(profile["default_target_name"]),
    }


def deliver_local_outbox(payload: dict, *, idempotency_key: str, resolved_target: dict, root: Path | None = None) -> str:
    root = root or repo_root()
    if resolved_target.get("target_resolution_mode") != "local_profile":
        raise SystemExit("local outbox delivery requires target_resolution_mode=local_profile")
    if resolved_target.get("transport_kind") != "local_outbox":
        raise SystemExit("local outbox delivery requires transport_kind=local_outbox")

    outbox_root = root / str(resolved_target["outbox_root"])
    target_name = safe_slug(resolved_target.get("default_target_name") or "default")
    file_name = f"{safe_slug(idempotency_key)}.json"
    output_path = outbox_root / target_name / file_name
    output_path.parent.mkdir(parents=True, exist_ok=True)
    envelope = {
        "generated_at_utc": now_utc(),
        "delivery_idempotency_key": idempotency_key,
        "channel_kind": str(resolved_target["channel_kind"]),
        "delivery_target": str(resolved_target["delivery_target"]),
        "target_resolution_mode": "local_profile",
        "target_profile_ref": str(resolved_target["target_profile_ref"]),
        "transport_kind": "local_outbox",
        "payload": payload,
    }
    output_path.write_text(json.dumps(envelope, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    return repo_relative(output_path, root)
