"""Fixed source-only suggestion for a legitimate owner's archived-record read."""

from __future__ import annotations

import ast
import re
import warnings
from dataclasses import dataclass
from hashlib import sha256
from importlib.resources import files
from typing import Any

from authzest.codex.contracts import AdapterConfig, ContractError, canonical, decode, identity
from authzest.codex.fixture_draft import HOST_INSTRUCTIONS

SOURCE_PATH = "src/authzest/owner_read_demo/availability.py"
TEST_PATH = "tests/test_owner_archived_read.py"
BASELINE_SHA256 = "0cf37a75536af33aeb6569214e4f869209a632f44dd34d706032b9a2d218cf13"
_STATUSES = ("proposed-change", "no-change", "unknown", "refused")
_STATES = ("active", "archived", "pending")
_ROUTE = "/records/archived-note"
_CODE_BYTES = 4096
_POLICY = (
    "The app authenticates the reader and checks ownership before available_to_owner(state).",
    "An owner may read active and archived notes (200). Their pending notes remain denied (403).",
    "An anonymous read of an active note returns 401. Non-owner active and archived reads "
    "return 403. An authenticated owner's read of a missing note returns 404.",
    "The single observed mismatch is the owner's archived note: expected 200, observed 403.",
)
_TASK = (
    "Propose a new positive regression test and a correction for this owned synthetic fixture. "
    "The complete editable source is supplied below. Keep the interface "
    "available_to_owner(state: str) -> bool. Use one return composed only of positive state "
    "comparisons (==, membership in a literal tuple/list/set, or combinations with or). "
    "Use the declared state names only. Write one new ordinary function test_…(owner_client). "
    "Its injected authenticated owner_client sends exactly one GET to /records/archived-note. "
    "Assert the response status_code equals 200, using the call directly or one assignment first. "
    "Supply the complete source and test as printable ASCII Python with LF line endings. "
    "No imports, comments, decorators, extra functions or calls are in scope. Optional docstrings "
    "are permitted. Return the exact request_id. For no-change, unknown or refused return null "
    "source and test. Return one short rationale in every case."
)


@dataclass(frozen=True, slots=True)
class OwnerReadRequest:
    payload_json: str

    def to_dict(self) -> dict[str, Any]:
        return decode(self.payload_json)

    @property
    def request_id(self) -> str:
        return self.to_dict()["request_id"]


def _baseline_source() -> str:
    try:
        resource = files("authzest.owner_read_demo").joinpath("availability.py")
        with resource.open("rb") as stream:
            data = stream.read(_CODE_BYTES + 1)
    except OSError:
        raise ContractError("Packaged baseline unavailable", code="validation-identity") from None
    if sha256(data).hexdigest() != BASELINE_SHA256:
        raise ContractError("Packaged baseline differs", code="validation-identity")
    return data.decode("ascii")


def build_owner_read_request(model: str) -> OwnerReadRequest:
    AdapterConfig(model=model, temperature=None)
    source = {"path": SOURCE_PATH, "sha256": BASELINE_SHA256, "text": _baseline_source()}
    inputs = {"source": source, "test_path": TEST_PATH, "policy": list(_POLICY)}
    fields = {
        "request_id": {"type": "string"},
        "status": {"type": "string", "enum": list(_STATUSES)},
        "rationale": {"type": "string", "minLength": 1, "maxLength": 1024},
        "source": {"type": ["string", "null"], "maxLength": _CODE_BYTES},
        "test": {"type": ["string", "null"], "maxLength": _CODE_BYTES},
    }
    schema = {
        "type": "object",
        "properties": fields,
        "required": list(fields),
        "additionalProperties": False,
    }
    request = {
        "kind": "owner-read-suggestion-request-v1",
        "config": {"model": model},
        **inputs,
        "host_instructions": HOST_INSTRUCTIONS,
        "prompt": _TASK + "\n\n" + canonical(inputs),
        "output_schema": schema,
    }
    # Bind the entire envelope first, then insert its ID into the two wire fields.
    request_id = identity(request)
    request["request_id"] = request_id
    request["prompt"] += "\n\nrequest_id: " + request_id
    fields["request_id"]["enum"] = [request_id]
    return OwnerReadRequest(canonical(request))


def validate_owner_read_request(request: OwnerReadRequest) -> OwnerReadRequest:
    if type(request) is not OwnerReadRequest:
        raise ContractError("Expected an owner-read request", code="validation-shape")
    payload = request.to_dict()
    config = payload.get("config")
    if not isinstance(config, dict) or type(config.get("model")) is not str:
        raise ContractError("Invalid owner-read configuration", code="validation-shape")
    checked = build_owner_read_request(config["model"])
    if request.payload_json != checked.payload_json:
        raise ContractError("Owner-read request changed", code="validation-identity")
    return checked


def _without_docstring(body: list[ast.stmt]) -> list[ast.stmt]:
    if body and isinstance(body[0], ast.Expr):
        value = body[0].value
        if isinstance(value, ast.Constant) and type(value.value) is str:
            return body[1:]
    return body


def _single_function(text: str) -> ast.FunctionDef:
    # Source may eventually be written as UTF-8. Excluding comments also excludes alternate
    # Python encoding declarations and pytest/coverage directives that alter interpretation.
    if (
        type(text) is not str
        or not 0 < len(text) <= _CODE_BYTES
        or not text.isascii()
        or "#" in text
        or any(not c.isprintable() and c not in "\n\t" for c in text)
    ):
        raise ContractError("Invalid owner-read code text", code="validation-text")
    try:
        # Keep warnings caused by returned text inside this validation boundary.
        with warnings.catch_warnings():
            warnings.simplefilter("error", SyntaxWarning)
            tree = ast.parse(text)
    except (SyntaxError, SyntaxWarning, ValueError, RecursionError):
        raise ContractError("Invalid owner-read Python", code="validation-shape") from None
    pending = [(tree, 0)]
    count = 0
    while pending:
        node, depth = pending.pop()
        count += 1
        if depth > 20 or count > 120:
            raise ContractError("Owner-read Python exceeds limits", code="validation-budget")
        pending.extend((child, depth + 1) for child in ast.iter_child_nodes(node))
    match _without_docstring(tree.body):
        case [ast.FunctionDef() as func] if (
            not func.decorator_list
            and not func.type_params
            and not func.args.posonlyargs
            and not func.args.kwonlyargs
            and not func.args.vararg
            and not func.args.kwarg
            and not func.args.defaults
            and len(func.args.args) == 1
        ):
            return func
    raise ContractError("Invalid owner-read function", code="validation-shape")


def _state_literal(expr: ast.expr) -> bool:
    return isinstance(expr, ast.Constant) and expr.value in _STATES


def _state_predicate(expr: ast.expr) -> bool:
    match expr:
        case ast.BoolOp(op=ast.Or(), values=values):
            return all(_state_predicate(value) for value in values)
        case ast.Compare(left=ast.Name(id="state"), ops=[ast.Eq()], comparators=[right]):
            return _state_literal(right)
        case ast.Compare(left=ast.Name(id="state"), ops=[ast.In()], comparators=[right]):
            return (
                isinstance(right, ast.Tuple | ast.List | ast.Set)
                and bool(right.elts)
                and all(_state_literal(elt) for elt in right.elts)
            )
    return False


def _validate_rule(source: str) -> ast.FunctionDef:
    func = _single_function(source)
    match func.name, func.args.args[0], func.returns, _without_docstring(func.body):
        case (
            "available_to_owner",
            ast.arg(arg="state", annotation=ast.Name(id="str")),
            ast.Name(id="bool"),
            [ast.Return(value=predicate)],
        ) if _state_predicate(predicate):
            return func
    raise ContractError("Invalid owner-read availability rule", code="validation-shape")


def _owner_get(expr: ast.expr) -> bool:
    match expr:
        case ast.Call(
            func=ast.Attribute(value=ast.Name(id="owner_client"), attr="get"),
            args=[ast.Constant(value=path)],
            keywords=[],
        ):
            return path == _ROUTE
    return False


def _validate_test(test: str) -> ast.FunctionDef:
    func = _single_function(test)
    arg = func.args.args[0]
    if (
        not re.fullmatch(r"test_[A-Za-z][A-Za-z0-9_]{0,64}", func.name)
        or arg.arg != "owner_client"
        or arg.annotation is not None
        or (
            func.returns is not None
            and not (isinstance(func.returns, ast.Constant) and func.returns.value is None)
        )
    ):
        raise ContractError("Invalid owner-read test signature", code="validation-shape")
    body = _without_docstring(func.body)
    match body[-1:]:
        case [
            ast.Assert(
                test=ast.Compare(
                    left=ast.Attribute(value=result, attr="status_code"),
                    ops=[ast.Eq()],
                    comparators=[ast.Constant(value=status)],
                ),
                msg=None,
            )
        ] if type(status) is int and status == 200:
            match body[:-1]:
                case [] if _owner_get(result):
                    return func
                case [ast.Assign(targets=[ast.Name(id=name)], value=get)] if (
                    isinstance(result, ast.Name)
                    and result.id == name
                    and name not in {"owner_client", "__debug__"}
                    and _owner_get(get)
                ):
                    return func
    raise ContractError("Invalid positive regression test", code="validation-shape")


def validate_owner_read_response(raw: str, request: OwnerReadRequest) -> dict[str, Any]:
    checked = validate_owner_read_request(request)
    value = decode(raw)
    if set(value) != {"request_id", "status", "rationale", "source", "test"}:
        raise ContractError("Unexpected owner-read response fields", code="validation-shape")
    if value["request_id"] != checked.request_id:
        raise ContractError("Response belongs to another request", code="validation-identity")
    rationale = value["rationale"]
    if (
        type(rationale) is not str
        or not rationale.strip()
        or len(rationale) > 1024
        or any(not c.isprintable() and c not in "\n\t" for c in rationale)
    ):
        raise ContractError("Invalid owner-read rationale", code="validation-text")
    status = value["status"]
    if status not in _STATUSES:
        raise ContractError("Invalid owner-read status", code="validation-shape")
    if status == "proposed-change":
        _validate_rule(value["source"])
        _validate_test(value["test"])
        if value["source"] == checked.to_dict()["source"]["text"]:
            raise ContractError("Proposed source is unchanged", code="validation-shape")
    elif value["source"] is not None or value["test"] is not None:
        raise ContractError("Unexpected artifacts for owner-read status", code="validation-shape")
    return value
