"""Pure comparison of a deliberately small source-declaration subset.

No model, bundle contract, file access, source import or execution belongs here.
Matching explicit syntax is not evidence of callable behavior or authorization.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from authzest.models import Route
from authzest.parser.fastapi import HTTP_METHODS, FastAPIRouteParser

_FACTORIES = {"Depends", "Security"}
_PRIMITIVES = {"str", "int", "float", "bool", "bytes", "object"}
_GENERICS = {"list", "dict", "tuple", "set", "frozenset", "type"}
_SOURCE_LIMIT = 32_768


@dataclass(frozen=True, slots=True)
class DeclarationTarget:
    """Caller-supplied baseline and expectation, neither approved nor verified."""

    baseline: dict
    observation: str
    expected: dict


@dataclass(frozen=True, slots=True)
class _Snapshot:
    routes: tuple[Route, ...] = ()
    owner: str | None = None
    reason: str | None = None


def _result(status: str, reason: str, *, before=None, observed=None, registration_id=None) -> dict:
    return {
        "status": status,
        "reason": reason,
        "before_observed": before,
        "observed": observed,
        "after_registration_id": registration_id,
    }


def _literal(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant):
        return node.value is None or type(node.value) in (bool, str, bytes, int, float)
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return all(_literal(item) for item in node.elts)
    if isinstance(node, ast.Dict):
        return all(key is not None and _literal(key) for key in node.keys) and all(
            _literal(value) for value in node.values
        )
    return (
        isinstance(node, ast.UnaryOp)
        and isinstance(node.op, (ast.UAdd, ast.USub))
        and isinstance(node.operand, ast.Constant)
        and type(node.operand.value) in (int, float)
    )


def _reference(node: ast.AST) -> bool:
    while isinstance(node, ast.Attribute):
        node = node.value
    return isinstance(node, ast.Name)


def _dependency(node: ast.AST, imported: set[str]) -> bool:
    if not (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in _FACTORIES & imported
    ):
        return False
    keywords = [keyword.arg for keyword in node.keywords]
    allowed = {"dependency", "use_cache", "scope" if node.func.id == "Depends" else "scopes"}
    if (
        len(node.args) > 1
        or None in keywords
        or len(keywords) != len(set(keywords))
        or not set(keywords) <= allowed
    ):
        return False
    targets = [*node.args, *(item.value for item in node.keywords if item.arg == "dependency")]
    if len(targets) != 1 or not _reference(targets[0]):
        return False
    return all(item.arg == "dependency" or _literal(item.value) for item in node.keywords)


def _arguments(call: ast.Call, imported: set[str]) -> bool:
    keywords = [keyword.arg for keyword in call.keywords]
    if None in keywords or len(keywords) != len(set(keywords)):
        return False
    for keyword in call.keywords:
        value = keyword.value
        if keyword.arg == "dependencies":
            if isinstance(value, ast.Constant) and value.value is None:
                continue
            if not isinstance(value, ast.List) or not all(
                _dependency(item, imported) for item in value.elts
            ):
                return False
        elif not _literal(value):
            return False
    return True


def _type_annotation(node: ast.AST, imported: set[str]) -> bool:
    if isinstance(node, ast.Name):
        return node.id in _PRIMITIVES | _GENERICS or node.id == "Any" and "Any" in imported
    if isinstance(node, ast.Constant):
        return node.value is None or node.value is Ellipsis
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return _type_annotation(node.left, imported) and _type_annotation(node.right, imported)
    if (
        isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Name)
        and node.value.id in _GENERICS
    ):
        arguments = node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]
        return all(_type_annotation(argument, imported) for argument in arguments)
    return False


def _annotation(node: ast.AST | None, imported: set[str]) -> bool:
    if node is None or _type_annotation(node, imported):
        return True
    return (
        isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Name)
        and node.value.id == "Annotated"
        and "Annotated" in imported
        and isinstance(node.slice, ast.Tuple)
        and len(node.slice.elts) == 2
        and _type_annotation(node.slice.elts[0], imported)
        and _dependency(node.slice.elts[1], imported)
    )


def _header(function: ast.FunctionDef | ast.AsyncFunctionDef, imported: set[str]) -> bool:
    arguments = function.args
    parameters = [
        *arguments.posonlyargs,
        *arguments.args,
        *arguments.kwonlyargs,
        arguments.vararg,
        arguments.kwarg,
    ]
    return (
        not function.type_params
        and all(_annotation(item.annotation, imported) for item in parameters if item is not None)
        and (function.returns is None or _type_annotation(function.returns, imported))
        and all(
            value is None or _literal(value) or _dependency(value, imported)
            for value in [*arguments.defaults, *arguments.kw_defaults]
        )
    )


def _owner(tree: ast.Module, routes: tuple[Route, ...]) -> str | None:
    """Require one canonical constructor binding and explicit, alias-free headers.

    Deliberately excludes routers/includes, conditional registrations, custom
    decorators, imported/string annotation aliases and arbitrary module statements.
    Function bodies are never executed; nested route inventories are rejected.
    """
    imported: set[str] = set()
    owners = []
    functions = []
    for statement in tree.body:
        if isinstance(statement, ast.ImportFrom):
            allowed = (
                {"FastAPI", *_FACTORIES}
                if statement.level == 0 and statement.module == "fastapi"
                else {"Annotated", "Any"}
                if statement.level == 0 and statement.module in {"typing", "typing_extensions"}
                else set()
            )
            for alias in statement.names:
                if alias.asname is not None or alias.name not in allowed or alias.name in imported:
                    return None
                imported.add(alias.name)
        elif isinstance(statement, (ast.Assign, ast.AnnAssign)):
            targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
            if (
                len(targets) != 1
                or not isinstance(targets[0], ast.Name)
                or not isinstance(statement.value, ast.Call)
                or not isinstance(statement.value.func, ast.Name)
                or statement.value.func.id != "FastAPI"
                or "FastAPI" not in imported
                or statement.value.args
                or not _arguments(statement.value, imported)
                or (
                    isinstance(statement, ast.AnnAssign)
                    and not (
                        isinstance(statement.annotation, ast.Name)
                        and statement.annotation.id == "FastAPI"
                    )
                )
            ):
                return None
            owners.append(targets[0].id)
        elif isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not _header(statement, imported):
                return None
            functions.append(statement)
        elif not (
            isinstance(statement, ast.Pass)
            or isinstance(statement, ast.Expr)
            and isinstance(statement.value, ast.Constant)
            and isinstance(statement.value.value, str)
        ):
            return None
    if len(owners) != 1:
        return None
    owner = owners[0]
    reserved = imported | _PRIMITIVES | _GENERICS | {owner}
    if owner in imported | _PRIMITIVES | _GENERICS or any(
        function.name in reserved for function in functions
    ):
        return None
    declarations = set()
    for function in functions:
        for decorator in function.decorator_list:
            if not (
                isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Attribute)
                and isinstance(decorator.func.value, ast.Name)
                and decorator.func.value.id == owner
                and decorator.func.attr in HTTP_METHODS
                and len(decorator.args) == 1
                and isinstance(decorator.args[0], ast.Constant)
                and isinstance(decorator.args[0].value, str)
                and not any(keyword.arg == "path" for keyword in decorator.keywords)
                and _arguments(decorator, imported)
            ):
                return None
            declarations.add((decorator.lineno, decorator.col_offset + 1))
    inventoried = set()
    for route in routes:
        registration = route.registration
        if (
            registration is None
            or registration.owner.kind != "FastAPI"
            or registration.application != registration.owner
            or registration.include_chain
            or registration.execution_scope != "module"
            or any(
                dependency.resolution != "reference" or dependency.unresolved_reasons
                for dependency in route.effective_dependencies
            )
        ):
            return None
        inventoried.add((registration.declaration.line, registration.declaration.column))
    # A supported-looking decorator that the parser could not bind is not zero evidence.
    if len(routes) != len(declarations) or inventoried != declarations:
        return None
    return owner


def _snapshot(path: str, source: str, phase: str) -> _Snapshot:
    if type(source) is not str or len(source) > _SOURCE_LIMIT:
        return _Snapshot(reason="source-limit")
    try:
        # Parse once per snapshot; reuse this AST for inventory and the conservative gate.
        tree = ast.parse(source, filename=path)
        parsed = FastAPIRouteParser().parse_tree(tree, Path(path))
        if parsed.diagnostics:
            return _Snapshot(reason=f"{phase}-analysis-partial")
        owner = _owner(tree, parsed.routes)
    except (SyntaxError, UnicodeError, ValueError, RecursionError):
        return _Snapshot(reason=f"{phase}-parse-error")
    if owner is None:
        return _Snapshot(reason="unsupported-source-form")
    return _Snapshot(routes=parsed.routes, owner=owner)


def _key(route: Route, owner: str | None) -> tuple:
    return owner, route.function, route.methods, route.path


def _declaration_evidence(route: Route) -> dict:
    # Bundle source labels are logical POSIX paths on every host. Keep the legacy
    # scan report's native display paths unchanged, but match prepare_request's
    # wire normalization here. Locations and registration IDs already use POSIX.
    evidence = route.to_dict()
    evidence["file"] = route.file.as_posix()
    return evidence


def _observe(route: Route, observation: str) -> dict | None:
    if observation == "dependency-declarations":
        return {"count": len(route.effective_dependencies)}
    if observation == "scope-declarations":
        scopes = set()
        for dependency in route.effective_dependencies:
            if dependency.kind == "Security":
                if dependency.scopes is None:
                    return None
                scopes.update(dependency.scopes)
        return {"scopes": sorted(scopes)}
    return None


def compare_declarations(
    *, path: str, before_text: str, after_text: str, targets: list[DeclarationTarget]
) -> list[dict]:
    """Compare supplied snapshots, not filesystem freshness, runtime or enforcement.

    Caller validates artifact relationships and the single-file/bounded-report scope.
    This core independently requires exact baseline inventory evidence and a unique
    line-independent correspondence. Policy intent is never inferred from declarations.
    """
    before = _snapshot(path, before_text, "baseline")
    after = _snapshot(path, after_text, "after")
    results = []
    for target in targets:
        if target.observation == "policy-intent":
            results.append(_result("not-evaluated", "policy-intent-not-checkable"))
            continue
        if target.observation not in {"dependency-declarations", "scope-declarations"}:
            results.append(_result("unknown", "unsupported-observation"))
            continue
        if before.reason or after.reason:
            results.append(_result("unknown", before.reason or after.reason))
            continue
        baseline = [
            route for route in before.routes if _declaration_evidence(route) == target.baseline
        ]
        if len(baseline) != 1:
            results.append(_result("unknown", "baseline-evidence-mismatch"))
            continue
        route = baseline[0]
        key = _key(route, before.owner)
        peers = [item for item in before.routes if _key(item, before.owner) == key]
        candidates = [item for item in after.routes if _key(item, after.owner) == key]
        if len(peers) != 1 or len(candidates) > 1:
            results.append(_result("unknown", "ambiguous-registration"))
            continue
        if not candidates:
            results.append(_result("unknown", "after-registration-missing"))
            continue
        observed = _observe(candidates[0], target.observation)
        prior = _observe(route, target.observation)
        if observed is None or prior is None:
            results.append(_result("unknown", "unresolved-declarations"))
            continue
        expected = target.expected
        if target.observation == "scope-declarations":
            expected = {"scopes": sorted(set(expected["scopes"]))}
        matched = expected == observed
        results.append(
            _result(
                "matched" if matched else "mismatched",
                "declaration-match" if matched else "declaration-mismatch",
                before=prior,
                observed=observed,
                registration_id=_declaration_evidence(candidates[0])["registration_id"],
            )
        )
    return results
