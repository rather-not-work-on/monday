#!/usr/bin/env python3

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import re
import sys


BUNDLE_VERSION_PATTERN = re.compile(r"^\d{4}\.\d{2}\.\d{2}$")
CONTRACT_ID_PATTERN = re.compile(r"^c[1-8]-[a-z0-9-]+$")


def now_utc():
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=True, indent=2), encoding="utf-8")


def validate_pin(pin: dict, required_contracts):
    errors = []
    warnings = []

    source_repo = pin.get("source_repo")
    if source_repo != "rather-not-work-on/platform-contracts":
        errors.append(
            "source_repo must be 'rather-not-work-on/platform-contracts' "
            "(see docs/runbook/planningops-handoff-scheduler-runbook.md#contract-pin-remediation)"
        )

    consumer_repo = pin.get("consumer_repo")
    if consumer_repo != "rather-not-work-on/monday":
        errors.append(
            "consumer_repo must be 'rather-not-work-on/monday' "
            "(see docs/runbook/planningops-handoff-scheduler-runbook.md#contract-pin-remediation)"
        )

    version = pin.get("contract_bundle_version")
    if not isinstance(version, str) or not BUNDLE_VERSION_PATTERN.match(version):
        errors.append(
            "contract_bundle_version must match YYYY.MM.DD "
            "(see docs/runbook/planningops-handoff-scheduler-runbook.md#contract-pin-remediation)"
        )

    pinned = pin.get("pinned_contracts")
    if not isinstance(pinned, list) or not pinned:
        errors.append(
            "pinned_contracts must be a non-empty list "
            "(see docs/runbook/planningops-handoff-scheduler-runbook.md#contract-pin-remediation)"
        )
        pinned = []

    duplicates = sorted({c for c in pinned if pinned.count(c) > 1})
    if duplicates:
        errors.append(
            f"pinned_contracts must be unique; duplicates={duplicates} "
            "(see docs/runbook/planningops-handoff-scheduler-runbook.md#contract-pin-remediation)"
        )

    invalid_ids = [c for c in pinned if not isinstance(c, str) or not CONTRACT_ID_PATTERN.match(c)]
    if invalid_ids:
        errors.append(
            f"invalid contract ids={invalid_ids}; expected c<1-8>-<name> "
            "(see docs/runbook/planningops-handoff-scheduler-runbook.md#contract-pin-remediation)"
        )

    missing_required = sorted(set(required_contracts) - set(pinned))
    if missing_required:
        errors.append(
            f"missing required contracts={missing_required} "
            "(see docs/runbook/planningops-handoff-scheduler-runbook.md#contract-pin-remediation)"
        )

    unknown_ids = sorted(set(pinned) - set(required_contracts))
    if unknown_ids:
        warnings.append(f"additional pinned contracts detected={unknown_ids}")

    return errors, warnings


def main():
    parser = argparse.ArgumentParser(description="Validate monday contract pin against baseline policy")
    parser.add_argument("--pin", default="contracts/contract-pin.json")
    parser.add_argument("--output", default="artifacts/validation/contract-pin-report.json")
    parser.add_argument(
        "--required-contracts",
        default="c1-run-lifecycle,c2-subtask-handoff,c3-executor-result,c8-plan-to-github-projection",
        help="Comma separated required contract IDs",
    )
    args = parser.parse_args()

    required_contracts = [c.strip() for c in args.required_contracts.split(",") if c.strip()]
    pin_path = Path(args.pin)

    try:
        pin = load_json(pin_path)
    except json.JSONDecodeError as exc:
        report = {
            "generated_at_utc": now_utc(),
            "verdict": "fail",
            "pin_path": args.pin,
            "error_count": 1,
            "warning_count": 0,
            "errors": [f"invalid JSON: {exc}"],
            "warnings": [],
        }
        save_json(Path(args.output), report)
        print(f"report written: {args.output}")
        print("verdict=fail error_count=1 warning_count=0")
        return 1

    errors, warnings = validate_pin(pin, required_contracts)
    verdict = "pass" if len(errors) == 0 else "fail"

    report = {
        "generated_at_utc": now_utc(),
        "verdict": verdict,
        "pin_path": args.pin,
        "required_contracts": required_contracts,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
    }
    save_json(Path(args.output), report)

    print(f"report written: {args.output}")
    print(f"verdict={verdict} error_count={len(errors)} warning_count={len(warnings)}")
    return 0 if verdict == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
