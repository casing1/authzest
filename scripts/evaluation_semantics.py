"""Bound caller-supplied semantic candidates, never authenticate a live transport.

Already-decoded JSON cannot recover duplicate keys or establish origin, ordering,
freshness, timing or provider behavior. Raw envelope checks remain separate.
"""

from __future__ import annotations

import json
import math
import posixpath
import re
from dataclasses import dataclass

from scripts import evaluation_trial_plan as planner

POLICY_VERSION = "offline-selected-response-semantics-v1"
MAX_BYTES = 256 * 1024
MAX_TOTAL_BYTES = 2 * 1024 * 1024
MAX_DEPTH = 32
MAX_NODES = 65536
MAX_INTEGER_BITS = 4096


class SemanticError(ValueError):
    """Closed, redacted diagnostic for unsupported or mismatched candidates."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise SemanticError(code)


def checked(value: object, *, max_bytes: int = MAX_BYTES) -> object:
    """Deep-detach bounded exact built-in JSON data before interpreting it.

    Limits include dictionary keys and escaped compact UTF-8 JSON bytes. Repeated
    references are copied independently; cycles and custom object hooks are refused.
    """
    require(type(max_bytes) is int and 1 <= max_bytes <= MAX_TOTAL_BYTES, "invalid-limit")
    nodes = size = 0
    ancestors: set[int] = set()

    def charge(amount: int) -> None:
        nonlocal size
        size += amount
        require(size <= max_bytes, "input-too-large")

    def visit(node: object, depth: int) -> object:
        nonlocal nodes
        nodes += 1
        require(nodes <= MAX_NODES, "input-too-many-nodes")
        require(depth <= MAX_DEPTH, "input-too-deep")
        kind = type(node)
        if kind is str:
            require(len(node) <= max_bytes, "input-too-large")
            require(
                not any(0xD800 <= ord(character) <= 0xDFFF for character in node),
                "invalid-input-utf8",
            )
            charge(len(json.dumps(node, ensure_ascii=False).encode("utf-8")))
        elif node is None or kind is bool:
            charge(len(json.dumps(node)))
        elif kind is int:
            require(node.bit_length() <= MAX_INTEGER_BITS, "input-number-limit")
            charge(len(str(node)))
        elif kind is float:
            require(math.isfinite(node), "nonfinite-input-number")
            charge(len(json.dumps(node)))
        elif kind in (dict, list):
            require(id(node) not in ancestors, "cyclic-input")
            require(nodes + len(node) <= MAX_NODES, "input-too-many-nodes")
            ancestors.add(id(node))
            charge(2 + max(0, len(node) - 1))
            if kind is dict:
                result = {}
                for key, child in node.items():
                    require(type(key) is str, "invalid-input-key")
                    visit(key, depth + 1)
                    charge(1)
                    result[key] = visit(child, depth + 1)
            else:
                result = [visit(child, depth + 1) for child in node]
            ancestors.remove(id(node))
            return result
        else:
            raise SemanticError("invalid-input-type")
        return node

    return visit(value, 0)


def identifier(value: object) -> str:
    require(
        type(value) is str and re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value) is not None,
        "invalid-identifier",
    )
    return value


@dataclass(frozen=True, slots=True)
class Boundary:
    """Caller-declared expected values, not authenticated execution authority."""

    configuration: planner.TrialConfig
    cwd: str
    thread_id: str

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        require(type(self) is Boundary, "invalid-boundary")
        configuration = getattr(self, "configuration", None)
        require(type(configuration) is planner.TrialConfig, "invalid-configuration")
        try:
            configuration.__post_init__()
        except (planner.TrialPlanError, AttributeError, TypeError) as error:
            raise SemanticError("invalid-configuration") from error
        cwd = getattr(self, "cwd", None)
        require(
            type(cwd) is str
            and 1 <= len(cwd) <= 1024
            and cwd.startswith("/")
            and not cwd.startswith("//")
            and "\x00" not in cwd
            and "\\" not in cwd
            and all(character.isprintable() for character in cwd)
            and posixpath.normpath(cwd) == cwd,
            "invalid-cwd-label",
        )
        checked(cwd, max_bytes=4096)
        identifier(getattr(self, "thread_id", None))


def limitations() -> dict:
    """Stable negative evidence: a matching candidate does not complete a trial."""
    return {
        "policy_version": POLICY_VERSION,
        "caller_supplied_candidate": True,
        "transport_implemented": False,
        "runtime_observed": False,
        "provider_freshness_verified": False,
        "authenticated_ordering": False,
        "timing_verified": False,
        "cleanup_verified": False,
        "full_protocol_validated": False,
        "authenticated": False,
        "sharing_authorized": False,
        "execution_authorized": False,
        "live_configuration_frozen": False,
        "ready_for_live_trial": False,
        "accepted_trial": False,
        "actual_model_calls": 0,
        "target_executed": False,
        "model_quality_measured": False,
        "scoring_status": "not-run",
    }
