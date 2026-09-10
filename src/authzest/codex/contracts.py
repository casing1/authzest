"""Offline, source-minimized contracts. No filesystem, process, or provider access."""

from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import PurePosixPath
from typing import Any, Literal

from authzest.models import REPORT_SCHEMA_VERSION, ScanReport

AI_SCHEMA_VERSION = "1.0"
MAX_JSON_BYTES = 262_144
Mode = Literal["model-only", "evidence-plus-model"]


class ContractError(ValueError):
    """Invalid input/output. Messages never include source or provider output."""


def canonical(value: Any) -> str:
    try:
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        )
    except (ValueError, TypeError, RecursionError) as exc:
        raise ContractError("Not a finite JSON value") from exc


def identity(value: Any) -> str:
    try:
        return sha256(canonical(value).encode("utf-8")).hexdigest()
    except UnicodeError as exc:
        raise ContractError("Invalid Unicode") from exc


def _object(value: Any, fields: set[str]) -> dict[str, Any]:
    if type(value) is not dict or set(value) != fields:
        raise ContractError("Unexpected object fields")
    return value


def _text(value: Any, limit: int = 4096) -> str:
    if type(value) is not str or not value.strip() or len(value) > limit:
        raise ContractError("Invalid text")
    if any(ord(char) < 32 and char not in "\n\t\r" for char in value):
        raise ContractError("Invalid control character")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise ContractError("Invalid Unicode") from exc
    return value


def _list(value: Any, limit: int = 256) -> list[Any]:
    if type(value) is not list or len(value) > limit:
        raise ContractError("Invalid collection")
    return value


def _integer(value: Any, minimum: int = 0) -> int:
    if type(value) is not int or not minimum <= value <= 1_000_000_000:
        raise ContractError("Invalid integer")
    return value


def _unique(values: list[str]) -> None:
    if len(set(values)) != len(values):
        raise ContractError("Duplicate identifier")


def decode(raw: str) -> dict[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        _unique([key for key, _ in items])
        return dict(items)

    def constant(_: str) -> None:
        raise ContractError("Non-finite JSON number")

    if type(raw) is not str:
        raise ContractError("Expected JSON text")
    try:
        if len(raw) > MAX_JSON_BYTES or len(raw.encode("utf-8")) > MAX_JSON_BYTES:
            raise ContractError("JSON size limit exceeded")
        value = json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ContractError("Invalid JSON") from exc
    if type(value) is not dict:
        raise ContractError("Expected JSON object")
    pending = [(value, 0)]
    visited = 0
    while pending:
        item, depth = pending.pop()
        visited += 1
        if depth > 32 or visited > 8192:
            raise ContractError("JSON structural limit exceeded")
        if isinstance(item, dict):
            pending.extend((child, depth + 1) for child in item.values())
            pending.extend((key, depth + 1) for key in item)
        elif isinstance(item, list):
            pending.extend((child, depth + 1) for child in item)
        elif isinstance(item, float) and not math.isfinite(item):
            raise ContractError("Non-finite JSON number")
        elif isinstance(item, str):
            try:
                item.encode("utf-8")
            except UnicodeError as exc:
                raise ContractError("Invalid Unicode") from exc
    return value


@dataclass(frozen=True, slots=True)
class AdapterConfig:
    provider: str = "mock"
    model: str = "scripted-v1"
    adapter_version: str = "1.0"
    prompt_version: str = "review-v1"
    temperature: float = 0.0
    seed: int | None = None

    def __post_init__(self) -> None:
        for value in (self.provider, self.model, self.adapter_version, self.prompt_version):
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}", _text(value, 128)):
                raise ContractError("Invalid adapter identity")
        if (
            type(self.temperature) not in (float, int)
            or not math.isfinite(self.temperature)
            or not 0 <= self.temperature <= 2
        ):
            raise ContractError("Invalid temperature")
        if self.seed is not None:
            _integer(self.seed)


def _source_path(value: Any) -> str:
    path = _text(value, 512)
    if (
        "\\" in path
        or ":" in path
        or any(ord(c) < 32 for c in path)
        or PurePosixPath(path).is_absolute()
        or any(part in ("", ".", "..") for part in path.split("/"))
    ):
        raise ContractError("Source path must be repository-relative")
    return path


def _locations(value: Any, sources: dict[str, str]) -> None:
    """Reject references outside the explicitly supplied source snapshots."""
    if isinstance(value, dict):
        if "file" in value:
            path = _source_path(value["file"])
            if path not in sources:
                raise ContractError("Evidence references unselected source")
            line = _integer(value["line"], 1)
            if line > len(sources[path].splitlines()):
                raise ContractError("Evidence line outside source snapshot")
            if value.get("column") is not None:
                column = _integer(value["column"], 1)
                if column > len(sources[path].splitlines()[line - 1].encode("utf-8")) + 1:
                    raise ContractError("Evidence column outside source snapshot")
        for child in value.values():
            _locations(child, sources)
    elif isinstance(value, list):
        for child in value:
            _locations(child, sources)


@dataclass(frozen=True, slots=True)
class CodexAnalysisRequest:
    """Immutable JSON snapshot. Returned dictionaries are detached copies."""

    payload_json: str

    def __post_init__(self) -> None:
        payload = decode(self.payload_json)
        _object(
            payload,
            {
                "schema_version",
                "report_schema_version",
                "mode",
                "config",
                "source_revision",
                "source_identity",
                "evidence",
                "questions",
            },
        )
        if payload["schema_version"] != AI_SCHEMA_VERSION:
            raise ContractError("Unsupported AI schema version")
        if payload["report_schema_version"] != REPORT_SCHEMA_VERSION:
            raise ContractError("Unsupported report schema version")
        if payload["mode"] not in ("model-only", "evidence-plus-model"):
            raise ContractError("Unsupported mode")
        AdapterConfig(**_object(payload["config"], set(asdict(AdapterConfig()))))
        if payload["source_revision"] is not None and not re.fullmatch(
            r"[a-f0-9]{40}|[a-f0-9]{64}", _text(payload["source_revision"], 64)
        ):
            raise ContractError("Expected source revision hash")
        items = _list(payload["evidence"])
        sources: dict[str, str] = {}
        for item in items:
            _object(item, {"id", "kind", "data"})
            if item["kind"] not in ("source", "route", "policy", "limitations"):
                raise ContractError("Unsupported evidence kind")
            if item["id"] != "ev-" + identity({"kind": item["kind"], "data": item["data"]}):
                raise ContractError("Evidence identity mismatch")
            if item["kind"] == "source":
                data = _object(item["data"], {"path", "text"})
                path = _source_path(data["path"])
                if path in sources:
                    raise ContractError("Duplicate source path")
                sources[path] = _text(data["text"], 32_768)
            if item["kind"] == "policy":
                _text(item["data"])
            if item["kind"] == "limitations":
                limits = _object(
                    item["data"],
                    {
                        "analysis_status",
                        "scope",
                        "diagnostic_codes",
                        "parse_error_count",
                        "security_verdict",
                    },
                )
                if (
                    limits["analysis_status"] not in ("bounded", "partial")
                    or limits["scope"] != "selected-source-declarations"
                    or limits["security_verdict"] != "unknown"
                ):
                    raise ContractError("Invalid analysis limitations")
                _integer(limits["parse_error_count"])
                for code in _list(limits["diagnostic_codes"]):
                    _text(code, 128)
            if payload["mode"] == "model-only" and item["kind"] in ("route", "limitations"):
                raise ContractError("Model-only mode cannot include extracted evidence")
        if not 1 <= len(sources) <= 16 or payload["source_identity"] != identity(sources):
            raise ContractError("Invalid source snapshot identity")
        _unique([item["id"] for item in items])
        for item in items:
            if item["kind"] == "route":
                data = item["data"]
                if type(data) is not dict or not re.fullmatch(
                    r"route-[a-f0-9]{64}", str(data.get("registration_id"))
                ):
                    raise ContractError("Missing registration identity")
                _object(
                    data,
                    {
                        "path",
                        "methods",
                        "function",
                        "file",
                        "line",
                        "registration_id",
                        "registration",
                        "dependencies",
                        "effective_dependencies",
                    },
                )
                _text(data["path"])
                _text(data["function"])
                for method in _list(data["methods"], 32):
                    _text(method, 32)
                registration = _object(
                    data["registration"],
                    {"declaration", "owner", "application", "include_chain", "execution_scope"},
                )
                if registration["execution_scope"] not in ("module", "deferred"):
                    raise ContractError("Invalid registration execution scope")
                _list(registration["include_chain"], 32)
                original = {
                    key: data[key]
                    for key in ("path", "methods", "function", "file", "line", "registration")
                }
                if data["registration_id"] != "route-" + identity(original):
                    raise ContractError("Registration identity mismatch")
                for field in ("dependencies", "effective_dependencies"):
                    for dep in _list(data[field]):
                        _object(
                            dep,
                            {
                                "kind",
                                "target",
                                "location",
                                "declaration_level",
                                "parameter",
                                "resolution",
                                "scopes",
                                "unresolved_reasons",
                            },
                        )
                _locations(data, sources)
        questions = _list(payload["questions"], 32)
        if not questions:
            raise ContractError("At least one question is required")
        for question in questions:
            _object(question, {"id", "text"})
            _text(question["id"], 128)
            _text(question["text"])
        _unique([question["id"] for question in questions])

    @property
    def request_id(self) -> str:
        return "request-" + identity(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return decode(self.payload_json)


def prepare_request(
    report: ScanReport,
    *,
    registration_ids: tuple[str, ...],
    sources: dict[str, str],
    policies: tuple[str, ...],
    questions: tuple[tuple[str, str], ...],
    config: AdapterConfig | None = None,
    mode: Mode = "evidence-plus-model",
    source_revision: str | None = None,
) -> CodexAnalysisRequest:
    """Select supplied data only; never read files or infer sharing permission.

    Caller must obtain the report and snapshots from the same reviewed source state.
    This identity is not a Git/worktree freshness check or patch approval token.
    """
    _unique(list(registration_ids))
    routes = {}
    for route in report.routes:
        item = route.to_dict(report.root)
        if item["registration_id"] is not None:
            try:
                item["file"] = route.file.relative_to(report.root).as_posix()
            except ValueError as exc:
                raise ContractError("Route outside report root") from exc
            routes[item["registration_id"]] = item
    if not set(registration_ids) <= routes.keys():
        raise ContractError("Unknown registration selection")
    selected = [routes[key] for key in sorted(registration_ids)]
    for route in selected:
        _locations(route, sources)
    evidence = [
        {"kind": "source", "data": {"path": path, "text": text}}
        for path, text in sorted(sources.items())
    ]
    evidence += [{"kind": "policy", "data": policy} for policy in sorted(set(policies))]
    if mode == "evidence-plus-model":
        evidence += [{"kind": "route", "data": route} for route in selected]
        # Deliberately exclude root, raw parse errors and diagnostic messages (may contain source).
        evidence.append(
            {
                "kind": "limitations",
                "data": {
                    "analysis_status": report.analysis_status,
                    "scope": "selected-source-declarations",
                    "diagnostic_codes": sorted({item.code for item in report.diagnostics}),
                    "parse_error_count": len(report.parse_errors),
                    "security_verdict": "unknown",
                },
            }
        )
    items = [{"id": "ev-" + identity(item), **item} for item in evidence]
    return CodexAnalysisRequest(
        canonical(
            {
                "schema_version": AI_SCHEMA_VERSION,
                "report_schema_version": REPORT_SCHEMA_VERSION,
                "mode": mode,
                "config": asdict(config if config is not None else AdapterConfig()),
                "source_revision": source_revision,
                "source_identity": identity(sources),
                "evidence": items,
                "questions": [{"id": key, "text": text} for key, text in questions],
            }
        )
    )


@dataclass(frozen=True, slots=True)
class ValidatedResponse:
    """Schema/citation validity is NOT semantic truth or a security finding."""

    payload_json: str

    def to_dict(self) -> dict[str, Any]:
        return decode(self.payload_json)


def validate_response(raw: str, request: CodexAnalysisRequest) -> ValidatedResponse:
    data = decode(raw)
    _object(data, {"schema_version", "request_id", "identity", "answers", "usage"})
    if data["schema_version"] != AI_SCHEMA_VERSION or data["request_id"] != request.request_id:
        raise ContractError("Response version or request identity mismatch")
    payload = request.to_dict()
    expected_identity = {
        key: payload["config"][key]
        for key in ("provider", "model", "adapter_version", "prompt_version")
    }
    if data["identity"] != expected_identity:
        raise ContractError("Provider/model/version substitution rejected")
    allowed = {item["id"] for item in payload["evidence"]}
    questions = {question["id"] for question in payload["questions"]}
    answers = _list(data["answers"], 32)
    _unique(
        [
            _text(
                _object(
                    answer,
                    {
                        "question_id",
                        "status",
                        "answer",
                        "explanation",
                        "evidence_ids",
                        "assumptions",
                        "unknowns",
                        "review_questions",
                    },
                )["question_id"],
                128,
            )
            for answer in answers
        ]
    )
    if {answer["question_id"] for answer in answers} != questions:
        raise ContractError("Responses must cover exactly the supplied questions")
    for answer in answers:
        if answer["status"] not in ("hypothesis", "unknown"):
            raise ContractError("Unsupported certainty; no confirmed findings are allowed")
        _text(answer["explanation"])
        refs = [_text(ref, 128) for ref in _list(answer["evidence_ids"])]
        _unique(refs)
        if not refs or not set(refs) <= allowed:
            raise ContractError("Missing or nonexistent evidence reference")
        for field in ("assumptions", "unknowns", "review_questions"):
            for value in _list(answer[field], 32):
                _text(value)
        if answer["status"] == "unknown":
            if answer["answer"] is not None or not answer["unknowns"]:
                raise ContractError("Unknown requires abstention and an explicit limitation")
        else:
            _text(answer["answer"])
    usage = data["usage"]
    if usage is not None:
        _object(usage, {"input_tokens", "output_tokens"})
        for value in usage.values():
            if value is not None:
                _integer(value)
    return ValidatedResponse(canonical(data))
