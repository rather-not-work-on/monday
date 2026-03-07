#!/usr/bin/env python3

import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


def load_json(path: Path, default=None):
    if not path.exists():
        return default if default is not None else {}
    return json.loads(path.read_text(encoding="utf-8"))


def validate_reason_code(report: dict, taxonomy_path: Path):
    taxonomy = load_json(taxonomy_path)
    reason_codes = ((taxonomy.get("reason_codes") or {}) if isinstance(taxonomy, dict) else {})
    reason_code = report.get("reason_code")
    if reason_code not in reason_codes:
        raise ValueError(f"reason_code not registered in taxonomy: {reason_code}")

    taxonomy_version = taxonomy.get("version")
    if report.get("reason_taxonomy_version") != taxonomy_version:
        raise ValueError(
            f"reason_taxonomy_version mismatch: report={report.get('reason_taxonomy_version')} taxonomy={taxonomy_version}"
        )


def validate_report(report: dict, schema_path: Path, taxonomy_path: Path):
    schema = load_json(schema_path)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(report)
    validate_reason_code(report, taxonomy_path)
