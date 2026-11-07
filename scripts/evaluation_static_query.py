"""Pure, deliberately narrow source-declaration queries, never target execution.

Virtual path strings are labels only. All modules are independently inventoried;
no import graph, runtime registration, provider graph or access policy is inferred.
Unsupported syntax yields unknown rather than treating partial parser output as a
complete source inventory. No evaluation references are consulted here.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

from authzest.parser import FastAPIRouteParser

KINDS = ("source-http-declaration-count", "direct-security-scopes", "composed-dependency-count")
METHODS = ("DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT")
MAX_SOURCES = 4
MAX_SOURCE_BYTES = 16 * 1024
MAX_ANSWER_CHARS = 512
REASONS = frozenset(
    {
        "complete-source-declarations",
        "complete-direct-scopes",
        "unsupported-composition",
        "parse-error",
        "parser-diagnostics",
        "unsupported-decorator",
        "unsupported-alias",
        "incomplete-source-inventory",
        "nonunique-source-declaration",
        "unsupported-dependency-syntax",
        "incomplete-dependency-inventory",
        "unresolved-dependency",
        "unrepresentable-scopes",
    }
)


class QueryError(ValueError):
    """Invalid evaluator-owned query or bounded source-data input."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise QueryError(message)


@dataclass(frozen=True, slots=True)
class Query:
    """A registered syntax query, not natural-language interpretation."""

    kind: str
    method: str | None = None
    path: str | None = None

    def __post_init__(self) -> None:
        _require(type(self.kind) is str and self.kind in KINDS, "invalid query kind")
        if self.kind == "direct-security-scopes":
            _require(type(self.method) is str and self.method in METHODS, "invalid query method")
            _require(
                type(self.path) is str
                and self.path.startswith("/")
                and len(self.path) <= 512
                and all(character.isprintable() for character in self.path),
                "invalid query path",
            )
            try:
                self.path.encode("utf-8")
            except UnicodeError as error:
                raise QueryError("invalid query path") from error
        else:
            _require(self.method is None and self.path is None, "unexpected query selector")


def _sources(sources: object) -> None:
    _require(type(sources) is dict and 1 <= len(sources) <= MAX_SOURCES, "invalid source count")
    for path, source in sources.items():
        _require(
            type(path) is str
            and len(path) <= 160
            and re.fullmatch(r"(?:[A-Za-z_][A-Za-z0-9_-]*/)*[A-Za-z_][A-Za-z0-9_-]*\.py", path)
            is not None,
            "invalid virtual source path",
        )
        _require(
            type(source) is str and len(source) <= MAX_SOURCE_BYTES and "\x00" not in source,
            "invalid source text or byte limit",
        )
        try:
            _require(len(source.encode("utf-8")) <= MAX_SOURCE_BYTES, "source exceeds byte limit")
        except UnicodeError as error:
            raise QueryError("invalid source UTF-8") from error


def _result(answer: str | None, reason: str, evidence: list[dict] | None = None) -> dict:
    return {"answer": answer, "reason": reason, "evidence": evidence or []}


def _key(path: str, node: ast.AST) -> tuple[str, int, int]:
    return path, node.lineno, node.col_offset + 1


def _location(key: tuple[str, int, int]) -> dict:
    path, line, column = key
    return {"file": path, "line": line, "column": column}


def _decorator(node: ast.expr) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.attr.upper() in METHODS
        and node.func.attr == node.func.attr.lower()
        and len(node.args) == 1
        and isinstance(node.args[0], ast.Constant)
        and type(node.args[0].value) is str
        and all(keyword.arg not in (None, "path") for keyword in node.keywords)
        and not any(isinstance(child, ast.NamedExpr) for child in ast.walk(node))
    )


def _dependency_call(node: ast.expr) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in ("Depends", "Security")
        and not any(isinstance(child, ast.Call) for child in ast.walk(node) if child is not node)
    )


def _direct_calls(
    function: ast.FunctionDef | ast.AsyncFunctionDef, decorator: ast.Call
) -> list[ast.Call] | None:
    arguments = function.args
    parameters = [
        *arguments.posonlyargs,
        *arguments.args,
        *arguments.kwonlyargs,
        arguments.vararg,
        arguments.kwarg,
    ]
    if function.type_params or any(
        parameter.annotation is not None for parameter in parameters if parameter is not None
    ):
        return None
    calls = []
    for default in [*arguments.defaults, *arguments.kw_defaults]:
        if default is None:
            continue
        if not _dependency_call(default):
            return None
        calls.append(default)
    dependencies = [
        keyword.value for keyword in decorator.keywords if keyword.arg == "dependencies"
    ]
    if len(dependencies) > 1:
        return None
    for declared in dependencies:
        if not isinstance(declared, ast.List):
            return None
        for entry in declared.elts:
            if not _dependency_call(entry):
                return None
            calls.append(entry)
    return calls


def _scope_answer(
    routes: list, path: str, function: ast.FunctionDef | ast.AsyncFunctionDef, decorator: ast.Call
) -> dict:
    calls = _direct_calls(function, decorator)
    if calls is None:
        return _result(None, "unsupported-dependency-syntax")
    wanted = {_key(path, call): call.func.id for call in calls}
    collected = []
    for route in routes:
        actual = {
            (item.location.file.as_posix(), item.location.line, item.location.column): item.kind
            for item in route.dependencies
        }
        if actual != wanted or len(actual) != len(route.dependencies):
            return _result(None, "incomplete-dependency-inventory")
        for dependency in route.dependencies:
            if dependency.resolution != "reference" or dependency.unresolved_reasons:
                return _result(None, "unresolved-dependency")
            if dependency.kind == "Security":
                if dependency.scopes is None:
                    return _result(None, "unresolved-dependency")
                collected.extend(dependency.scopes)
    for scope in collected:
        if (
            type(scope) is not str
            or not scope
            or "," in scope
            or scope != scope.strip()
            or not all(character.isprintable() for character in scope)
        ):
            return _result(None, "unrepresentable-scopes")
        try:
            scope.encode("utf-8")
        except UnicodeError:
            return _result(None, "unrepresentable-scopes")
    answer = ",".join(sorted(set(collected)))
    if len(answer) > MAX_ANSWER_CHARS:
        return _result(None, "unrepresentable-scopes")
    return _result(answer, "complete-direct-scopes", [_location(_key(path, decorator))])


def evaluate_query(sources: dict[str, str], query: Query) -> dict:
    """Calculate supported declarations; unsupported or incomplete inventories abstain.

    Count identity is original decorator location, not include-expanded route count.
    A scope selector matches a literal decorator method/path, not a composed URL.
    Inherited dependencies and callable provider signatures are never scope inputs.
    """
    _require(type(query) is Query, "invalid query specification")
    query.__post_init__()
    _sources(sources)
    if query.kind == "composed-dependency-count":
        return _result(None, "unsupported-composition")
    declarations = {}
    registrations = {}
    for path, source in sorted(sources.items()):
        try:
            tree = ast.parse(source, filename=path)
            parsed = FastAPIRouteParser().parse_source(source, Path(path))
        except (SyntaxError, UnicodeError, ValueError, RecursionError):
            return _result(None, "parse-error")
        if parsed.error:
            return _result(None, "parse-error")
        if parsed.diagnostics:
            return _result(None, "parser-diagnostics")
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.ImportFrom)
                and node.module == "fastapi"
                and any(alias.asname is not None or alias.name == "*" for alias in node.names)
            ) or (
                isinstance(node, ast.Import)
                and any(
                    alias.name == "fastapi" and alias.asname is not None for alias in node.names
                )
            ):
                return _result(None, "unsupported-alias")
            if isinstance(node, ast.ClassDef) and node.decorator_list:
                return _result(None, "unsupported-decorator")
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for decorator in node.decorator_list:
                    if not _decorator(decorator):
                        return _result(None, "unsupported-decorator")
                    declarations[_key(path, decorator)] = (node, decorator)
        for route in parsed.routes:
            if route.registration is None:
                return _result(None, "incomplete-source-inventory")
            declaration = route.registration.declaration
            key = (declaration.file.as_posix(), declaration.line, declaration.column)
            registrations.setdefault(key, []).append(route)
    if set(declarations) != set(registrations):
        return _result(None, "incomplete-source-inventory")
    if query.kind == "source-http-declaration-count":
        return _result(
            str(len(declarations)),
            "complete-source-declarations",
            [_location(key) for key in sorted(declarations)],
        )
    selected = [
        (key, function, decorator)
        for key, (function, decorator) in declarations.items()
        if decorator.func.attr.upper() == query.method and decorator.args[0].value == query.path
    ]
    if len(selected) != 1:
        return _result(None, "nonunique-source-declaration")
    key, function, decorator = selected[0]
    return _scope_answer(registrations[key], key[0], function, decorator)
