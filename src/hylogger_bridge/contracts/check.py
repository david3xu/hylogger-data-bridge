# Purpose: check JSON values against the canonical contract schema using a small, strict subset.
import json
import math
import re
from typing import Any

from hylogger_bridge.contracts.load import schema

_NOTES = {"$schema", "$id", "$defs", "$comment", "title", "description"}
_RULES = {
    "$ref",
    "type",
    "enum",
    "const",
    "required",
    "properties",
    "additionalProperties",
    "maxProperties",
    "items",
    "minItems",
    "maxItems",
    "uniqueItems",
    "contains",
    "minLength",
    "maxLength",
    "pattern",
    "minimum",
    "maximum",
    "if",
    "then",
    "anyOf",
    "allOf",
}


class ContractError(ValueError):
    """A value does not satisfy the versioned contract."""


def _is(kind: str, value: object) -> bool:
    match kind:
        case "object":
            return isinstance(value, dict)
        case "array":
            return isinstance(value, list)
        case "string":
            return isinstance(value, str)
        case "boolean":
            return isinstance(value, bool)
        case "null":
            return value is None
        case "integer":
            return isinstance(value, int) and not isinstance(value, bool)
        case "number":
            return (
                isinstance(value, int | float)
                and not isinstance(value, bool)
                and math.isfinite(value)
            )
    raise ValueError(f"unsupported schema type {kind}")


def _same(left: object, right: object) -> bool:
    # JSON true is not 1, although Python treats them as equal.
    return type(left) is type(right) and left == right


def _target(ref: str, root: dict[str, Any]) -> dict[str, Any]:
    prefix = "#/$defs/"
    name = ref[len(prefix) :]
    if not ref.startswith(prefix) or name not in root["$defs"]:
        raise ValueError(f"unknown contract reference {ref}")
    target: dict[str, Any] = root["$defs"][name]
    return target


def _anchored(pattern: str) -> str:
    # Python's $ also matches before a trailing newline; ECMAScript's does not.
    return pattern[:-1] + r"\Z" if pattern.endswith("$") else pattern


def _object(
    rule: dict[str, Any], value: dict[str, Any], root: dict[str, Any], path: str
) -> list[str]:
    out = [f"{path}: missing {name}" for name in rule.get("required", []) if name not in value]
    properties: dict[str, Any] = rule.get("properties", {})
    extra = rule.get("additionalProperties", True)
    if len(value) > rule.get("maxProperties", len(value)):
        out.append(f"{path}: too many properties")
    for name, item in value.items():
        if name in properties:
            out += walk(properties[name], item, root, f"{path}.{name}")
        elif extra is False:
            out.append(f"{path}: unexpected {name}")
        elif isinstance(extra, dict):
            out += walk(extra, item, root, f"{path}.{name}")
    return out


def _array(rule: dict[str, Any], value: list[Any], root: dict[str, Any], path: str) -> list[str]:
    out: list[str] = []
    if len(value) < rule.get("minItems", 0):
        out.append(f"{path}: too few items")
    if len(value) > rule.get("maxItems", len(value)):
        out.append(f"{path}: too many items")
    unique = len({json.dumps(item, sort_keys=True) for item in value}) == len(value)
    if rule.get("uniqueItems") and not unique:
        out.append(f"{path}: items must be unique")
    if "items" in rule:
        for index, item in enumerate(value):
            out += walk(rule["items"], item, root, f"{path}[{index}]")
    if "contains" in rule and all(walk(rule["contains"], i, root, path) for i in value):
        out.append(f"{path}: no item matches")
    return out


def _text(rule: dict[str, Any], value: str, path: str) -> list[str]:
    out: list[str] = []
    if len(value) < rule.get("minLength", 0):
        out.append(f"{path}: too short")
    if len(value) > rule.get("maxLength", len(value)):
        out.append(f"{path}: too long")
    if "pattern" in rule and re.search(_anchored(rule["pattern"]), value, re.ASCII) is None:
        out.append(f"{path}: does not match the required format")
    return out


def _number(rule: dict[str, Any], value: int | float, path: str) -> list[str]:
    out: list[str] = []
    if value < rule.get("minimum", value):
        out.append(f"{path}: below the minimum")
    if value > rule.get("maximum", value):
        out.append(f"{path}: above the maximum")
    return out


def _branches(rule: dict[str, Any], value: object, root: dict[str, Any], path: str) -> list[str]:
    out: list[str] = []
    for item in rule.get("allOf", []):
        out += walk(item, value, root, path)
    if "anyOf" in rule:
        tries = [walk(item, value, root, path) for item in rule["anyOf"]]
        if all(tries):
            out.append(f"{path}: matches none of the allowed shapes ({tries[0][0]})")
    if "if" in rule and "then" in rule and not walk(rule["if"], value, root, path):
        out += walk(rule["then"], value, root, path)
    return out


def walk(rule: dict[str, Any], value: object, root: dict[str, Any], path: str = "$") -> list[str]:
    """Return every way `value` breaks `rule`; an unsupported keyword is a schema bug, not data."""
    unknown = set(rule) - _NOTES - _RULES
    if unknown:
        raise ValueError(f"unsupported schema keyword {sorted(unknown)[0]}")
    out: list[str] = []
    if "$ref" in rule:
        out += walk(_target(rule["$ref"], root), value, root, path)
    if "type" in rule:
        kinds = rule["type"] if isinstance(rule["type"], list) else [rule["type"]]
        if not any(_is(kind, value) for kind in kinds):
            return [*out, f"{path}: expected {'/'.join(kinds)}"]
    if "enum" in rule and not any(_same(value, item) for item in rule["enum"]):
        out.append(f"{path}: not an allowed value")
    if "const" in rule and not _same(value, rule["const"]):
        out.append(f"{path}: must be {rule['const']!r}")
    if isinstance(value, dict):
        out += _object(rule, value, root, path)
    elif isinstance(value, list):
        out += _array(rule, value, root, path)
    elif isinstance(value, str):
        out += _text(rule, value, path)
    elif isinstance(value, int | float) and not isinstance(value, bool):
        out += _number(rule, value, path)
    return out + _branches(rule, value, root, path)


def problems(name: str, value: object) -> list[str]:
    root = schema()
    return walk(_target(f"#/$defs/{name}", root), value, root)


def validate(name: str, value: object) -> None:
    found = problems(name, value)
    if found:
        raise ContractError("; ".join(found[:5]))
