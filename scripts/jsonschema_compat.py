#!/usr/bin/env python3

import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, List, Sequence


@dataclass
class ValidationError(Exception):
    absolute_path: Sequence[Any]
    message: str
    validator: str

    @property
    def path(self) -> Sequence[Any]:
        return self.absolute_path


class SchemaError(Exception):
    pass


class FormatChecker:
    def __init__(self):
        self.checkers = {"date-time": self._check_datetime}

    def conforms(self, value: Any, fmt: str) -> bool:
        checker = self.checkers.get(fmt)
        if checker is None:
            return True
        return checker(value)

    @staticmethod
    def _check_datetime(value: Any) -> bool:
        if not isinstance(value, str):
            return False
        probe = value.replace("Z", "+00:00")
        try:
            datetime.fromisoformat(probe)
            return True
        except ValueError:
            return False


class _FallbackDraft202012Validator:
    def __init__(self, schema: dict, format_checker: FormatChecker | None = None):
        self.schema = schema
        self.format_checker = format_checker or FormatChecker()

    @staticmethod
    def check_schema(schema: dict):
        if not isinstance(schema, dict):
            raise SchemaError("schema must be an object")
        if schema.get("type") != "object":
            raise SchemaError("only object-root schemas are supported by local fallback")

    def validate(self, instance: Any):
        errors = list(self.iter_errors(instance))
        if errors:
            first = errors[0]
            raise ValidationError(first.absolute_path, first.message, first.validator)

    def iter_errors(self, instance: Any) -> Iterable[ValidationError]:
        yield from _iter_schema_errors(self.schema, instance, [], self.format_checker)


def _iter_schema_errors(
    schema: dict, value: Any, path: List[Any], format_checker: FormatChecker
) -> Iterable[ValidationError]:
    expected_type = schema.get("type")
    if expected_type is not None:
        if expected_type == "object" and not isinstance(value, dict):
            yield ValidationError(list(path), "is not of type 'object'", "type")
            return
        if expected_type == "string" and not isinstance(value, str):
            yield ValidationError(list(path), "is not of type 'string'", "type")
            return
        if expected_type == "integer" and not isinstance(value, int):
            yield ValidationError(list(path), "is not of type 'integer'", "type")
            return
        if expected_type == "array" and not isinstance(value, list):
            yield ValidationError(list(path), "is not of type 'array'", "type")
            return

    if "const" in schema and value != schema["const"]:
        yield ValidationError(list(path), f"{value!r} is not equal to const", "const")

    if "enum" in schema and value not in schema["enum"]:
        yield ValidationError(list(path), f"{value!r} is not one of {schema['enum']}", "enum")

    if isinstance(value, str):
        min_length = schema.get("minLength")
        if min_length is not None and len(value) < min_length:
            yield ValidationError(list(path), f"is too short (minLength={min_length})", "minLength")
        pattern = schema.get("pattern")
        if pattern is not None and re.search(pattern, value) is None:
            yield ValidationError(list(path), f"{value!r} does not match {pattern!r}", "pattern")
        fmt = schema.get("format")
        if fmt is not None and not format_checker.conforms(value, fmt):
            yield ValidationError(list(path), f"{value!r} is not a '{fmt}'", "format")

    if isinstance(value, int):
        minimum = schema.get("minimum")
        if minimum is not None and value < minimum:
            yield ValidationError(list(path), f"{value} is less than minimum {minimum}", "minimum")

    if isinstance(value, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                yield ValidationError(list(path), f"{key!r} is a required property", "required")

        min_props = schema.get("minProperties")
        if min_props is not None and len(value) < min_props:
            yield ValidationError(
                list(path),
                f"{len(value)} properties found, minimum is {min_props}",
                "minProperties",
            )

        properties = schema.get("properties", {})
        additional = schema.get("additionalProperties", True)
        for key, item in value.items():
            child_path = [*path, key]
            if key in properties:
                yield from _iter_schema_errors(properties[key], item, child_path, format_checker)
            elif additional is False:
                yield ValidationError(child_path, f"additional property {key!r} is not allowed", "additionalProperties")

    if isinstance(value, list):
        min_items = schema.get("minItems")
        if min_items is not None and len(value) < min_items:
            yield ValidationError(
                list(path),
                f"{len(value)} items found, minimum is {min_items}",
                "minItems",
            )
        item_schema = schema.get("items")
        if item_schema:
            for idx, item in enumerate(value):
                yield from _iter_schema_errors(item_schema, item, [*path, idx], format_checker)


def _build_fallback_exports():
    return _FallbackDraft202012Validator, FormatChecker, SchemaError


def load_validator_exports():
    force_local = os.getenv("UAP_FORCE_LOCAL_JSONSCHEMA", "").lower() in {"1", "true", "yes"}
    if not force_local:
        try:
            from jsonschema import Draft202012Validator, FormatChecker as JsonschemaFormatChecker
            from jsonschema.exceptions import SchemaError as JsonschemaSchemaError

            return Draft202012Validator, JsonschemaFormatChecker, JsonschemaSchemaError
        except ImportError:
            pass
    return _build_fallback_exports()
