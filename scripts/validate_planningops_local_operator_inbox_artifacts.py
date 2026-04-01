#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import sys

from jsonschema_compat import load_validator_exports
from runtime_evidence_contract import load_json


REPO_ROOT = Path(__file__).resolve().parents[1]
PLANNINGOPS_BRIDGE_CONTRACT_REF = "planningops/contracts/monday-local-operator-inbox-payload-bridge-contract.md"
CONSUMER_CONTRACT_REF = "contracts/planningops-local-operator-inbox-consumer-contract.md"
DEFAULT_SCHEMA_BY_KIND = {
    "bridge": Path("contracts/planningops-local-operator-inbox-payload-bridge.schema.json"),
    "consumer-report": Path("contracts/planningops-local-operator-inbox-consumer-report.schema.json"),
}
DEFAULT_OUTPUT_BY_KIND = {
    "bridge": Path("runtime-artifacts/validation/planningops-local-operator-inbox-payload-validation-report.json"),
    "consumer-report": Path("runtime-artifacts/validation/planningops-local-operator-inbox-consumer-report-validation-report.json"),
}

Draft202012Validator, FormatChecker, _SchemaError = load_validator_exports()


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_path(raw_path: str | Path) -> Path:
    path = raw_path if isinstance(raw_path, Path) else Path(raw_path)
    if path.is_absolute():
        return path.resolve()
    return (REPO_ROOT / path).resolve()


def require_dict(value: object, label: str, *, errors: list[str]) -> dict:
    if not isinstance(value, dict):
        errors.append(f"{label} must be a JSON object")
        return {}
    return value


def require_string(value: object, label: str, *, errors: list[str]) -> str:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{label} must be a non-empty string")
        return ""
    return value.strip()


def maybe_existing_path(raw_path: object) -> Path | None:
    if not isinstance(raw_path, str) or not raw_path.strip():
        return None
    return resolve_path(raw_path)


def validate_against_schema(doc: dict, schema_path: Path, *, errors: list[str]) -> None:
    if not schema_path.exists():
        errors.append(f"schema file not found: {schema_path}")
        return
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"invalid schema JSON: {exc}")
        return

    try:
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(doc)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"schema validation failed: {exc}")


def validate_bridge_semantics(doc: dict) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    if require_string(doc.get("contract_ref"), "contract_ref", errors=errors) != PLANNINGOPS_BRIDGE_CONTRACT_REF:
        errors.append("bridge contract ref does not match planningops inbox payload bridge contract")

    payload = require_dict(doc.get("payload"), "payload", errors=errors)
    if require_string(payload.get("bridge_contract_ref"), "payload.bridge_contract_ref", errors=errors) != PLANNINGOPS_BRIDGE_CONTRACT_REF:
        errors.append("payload bridge contract ref does not match planningops inbox payload bridge contract")

    source_artifacts = require_dict(payload.get("source_artifacts"), "payload.source_artifacts", errors=errors)
    for key in ("day_packet_path", "mission_packet_path", "handoff_report_path", "local_operator_report_path"):
        artifact_path = maybe_existing_path(source_artifacts.get(key))
        if artifact_path is None:
            continue
        if not artifact_path.exists():
            errors.append(f"{key} missing: {artifact_path}")

    attachments = payload.get("attachments")
    if isinstance(attachments, list):
        for attachment in attachments:
            attachment_path = maybe_existing_path(attachment)
            if attachment_path is not None and not attachment_path.exists():
                warnings.append(f"attachment missing: {attachment_path}")

    return errors, warnings


def validate_consumer_report_semantics(doc: dict) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    if require_string(doc.get("consumer_contract_ref"), "consumer_contract_ref", errors=errors) != CONSUMER_CONTRACT_REF:
        errors.append("consumer contract ref does not match planningops local operator inbox consumer contract")

    bridge_id = require_string(doc.get("bridge_id"), "bridge_id", errors=errors)
    source_bridge_path = maybe_existing_path(doc.get("source_bridge_path"))
    if source_bridge_path is not None and not source_bridge_path.exists():
        errors.append(f"source bridge path missing: {source_bridge_path}")

    mode = require_string(doc.get("mode"), "mode", errors=errors)
    verdict = require_string(doc.get("verdict"), "verdict", errors=errors)
    consumer_status = require_string(doc.get("consumer_status"), "consumer_status", errors=errors)

    launch_request = require_dict(doc.get("launch_request"), "launch_request", errors=errors)
    if require_string(launch_request.get("source_bridge_id"), "launch_request.source_bridge_id", errors=errors) != bridge_id:
        errors.append("launch_request.source_bridge_id must match bridge_id")

    source_artifacts = require_dict(launch_request.get("source_artifacts"), "launch_request.source_artifacts", errors=errors)
    for key in ("day_packet_path", "mission_packet_path", "handoff_report_path", "local_operator_report_path"):
        artifact_path = maybe_existing_path(source_artifacts.get(key))
        if artifact_path is None:
            continue
        if not artifact_path.exists():
            errors.append(f"launch_request.source_artifacts.{key} missing: {artifact_path}")

    artifact_paths = require_dict(doc.get("artifact_paths"), "artifact_paths", errors=errors)
    for key in ("launch_request_path", "mission_file_path", "report_path"):
        artifact_path = maybe_existing_path(artifact_paths.get(key))
        if artifact_path is None:
            continue
        if not artifact_path.exists():
            errors.append(f"artifact_paths.{key} missing: {artifact_path}")

    if mode == "dry-run" and "execution" in doc:
        errors.append("dry-run consumer report must not include execution")
    if mode == "apply" and not isinstance(doc.get("execution"), dict):
        errors.append("apply consumer report must include execution")

    execution = doc.get("execution")
    if isinstance(execution, dict):
        attempted = execution.get("attempted")
        if attempted is True and mode != "apply":
            errors.append("execution.attempted=true is only valid for apply mode")

    runtime_report_summary = doc.get("runtime_report_summary")
    if isinstance(runtime_report_summary, dict):
        report_path = maybe_existing_path(runtime_report_summary.get("report_path"))
        if report_path is not None and not report_path.exists():
            errors.append(f"runtime_report_summary.report_path missing: {report_path}")

    overrides = launch_request.get("runtime_input_overrides")
    if isinstance(overrides, dict):
        if not any(isinstance(overrides.get(key), str) and str(overrides.get(key)).strip() for key in ("planner_runtime_config", "runtime_profile_file")):
            errors.append("runtime_input_overrides must include at least one non-empty override path")
        for key in ("planner_runtime_config", "runtime_profile_file"):
            override_path = maybe_existing_path(overrides.get(key))
            if override_path is not None and not override_path.exists():
                errors.append(f"launch_request.runtime_input_overrides.{key} missing: {override_path}")

    if verdict == "blocked" and consumer_status != "blocked":
        errors.append("blocked verdict must use consumer_status=blocked")

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate monday-owned planningops local inbox payload and consumer report artifacts")
    parser.add_argument("--kind", choices=sorted(DEFAULT_SCHEMA_BY_KIND), required=True)
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--schema", default=None)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    artifact_path = resolve_path(args.artifact)
    schema_path = resolve_path(args.schema) if args.schema else resolve_path(DEFAULT_SCHEMA_BY_KIND[args.kind])
    output_path = resolve_path(args.output) if args.output else resolve_path(DEFAULT_OUTPUT_BY_KIND[args.kind])

    errors: list[str] = []
    warnings: list[str] = []
    doc: dict = {}

    if not artifact_path.exists():
        errors.append(f"artifact file not found: {artifact_path}")
    else:
        try:
            raw_doc = json.loads(artifact_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"invalid artifact JSON: {exc}")
        else:
            if not isinstance(raw_doc, dict):
                errors.append("artifact must be a JSON object")
            else:
                doc = raw_doc

    if not errors:
        validate_against_schema(doc, schema_path, errors=errors)

    if not errors:
        if args.kind == "bridge":
            semantic_errors, semantic_warnings = validate_bridge_semantics(doc)
        else:
            semantic_errors, semantic_warnings = validate_consumer_report_semantics(doc)
        errors.extend(semantic_errors)
        warnings.extend(semantic_warnings)

    verdict = "pass" if not errors else "fail"
    report = {
        "generated_at_utc": now_utc(),
        "kind": args.kind,
        "artifact_path": str(artifact_path),
        "schema_path": str(schema_path),
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "verdict": verdict,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

    print(f"report written: {output_path}")
    print(f"kind={args.kind} verdict={verdict} error_count={len(errors)} warning_count={len(warnings)}")
    return 0 if verdict == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
