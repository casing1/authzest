from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from authzest.models import Route

HTTP_METHODS = {"delete", "get", "head", "options", "patch", "post", "put"}
CONSTRUCTORS = {"FastAPI", "APIRouter"}
Binding = Literal["module", "constructor", "owner"]


@dataclass(frozen=True, slots=True)
class ParseResult:
    routes: tuple[Route, ...]
    error: str | None = None


class _BoundNames(ast.NodeVisitor):
    """Collect writes in one scope, without leaking child-scope locals."""

    def __init__(self) -> None:
        self.names: set[str] = set()
        self.wildcard = False
        self.external: set[str] = set()

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, (ast.Store, ast.Del)):
            self.names.add(node.id)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if isinstance(node.ctx, (ast.Store, ast.Del)):
            root: ast.expr = node.value
            while isinstance(root, (ast.Attribute, ast.Subscript)):
                root = root.value
            if isinstance(root, ast.Name):
                self.names.add(root.id)
        self.generic_visit(node)

    visit_Subscript = visit_Attribute

    def visit_Import(self, node: ast.Import) -> None:
        self.names.update(alias.asname or alias.name.split(".")[0] for alias in node.names)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        self.names.update(alias.asname or alias.name for alias in node.names)
        self.wildcard |= any(alias.name == "*" for alias in node.names)

    def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self.names.add(node.name)
        for expression in [*node.decorator_list, *node.args.defaults, *node.args.kw_defaults]:
            if expression is not None:
                self.visit(expression)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.names.add(node.name)
        for expression in [*node.decorator_list, *node.bases, *node.keywords]:
            self.visit(expression)
        # Class bodies execute immediately; explicit external writes affect their parent.
        external = _bound_names(node.body).external
        self.names.update(external)
        self.external.update(external)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        # Lambda locals cannot establish route owners in the containing scope.
        for expression in [*node.args.defaults, *node.args.kw_defaults]:
            if expression is not None:
                self.visit(expression)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.name is not None:
            self.names.add(node.name)
        self.generic_visit(node)

    def visit_MatchAs(self, node: ast.MatchAs | ast.MatchStar) -> None:
        if node.name is not None:
            self.names.add(node.name)
        self.generic_visit(node)

    visit_MatchStar = visit_MatchAs

    def visit_MatchMapping(self, node: ast.MatchMapping) -> None:
        if node.rest is not None:
            self.names.add(node.rest)
        self.generic_visit(node)

    def visit_Global(self, node: ast.Global | ast.Nonlocal) -> None:
        self.external.update(node.names)

    visit_Nonlocal = visit_Global


def _bound_names(body: list[ast.stmt]) -> _BoundNames:
    collector = _BoundNames()
    for statement in body:
        collector.visit(statement)
    return collector


class FastAPIRouteParser:
    """Discover common FastAPI/APIRouter decorators without importing target code."""

    def parse_file(self, path: Path) -> ParseResult:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError, UnicodeError) as exc:
            return ParseResult(routes=(), error=f"{path}: {exc}")

        routes: list[Route] = []
        self._parse_body(tree.body, {}, path, routes)
        return ParseResult(routes=tuple(routes))

    def _parse_body(
        self,
        body: list[ast.stmt],
        bindings: dict[str, Binding],
        file_path: Path,
        routes: list[Route],
    ) -> None:
        # A function executes later: do not inherit names changed later in its outer scope.
        later_writes: list[tuple[set[str], bool]] = []
        collector = _BoundNames()
        for statement in reversed(body):
            later_writes.append((collector.names.copy(), collector.wildcard))
            collector.visit(statement)

        for statement, (later_names, later_wildcard) in zip(
            body, reversed(later_writes), strict=True
        ):
            written = _bound_names([statement])
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Decorator/default expressions with assignment can change other receivers.
                expressions = [
                    *statement.decorator_list,
                    *statement.args.defaults,
                    *statement.args.kw_defaults,
                ]
                dynamic = any(
                    isinstance(node, ast.NamedExpr)
                    for expression in expressions
                    if expression is not None
                    for node in ast.walk(expression)
                )
                for decorator in statement.decorator_list:
                    if dynamic:
                        break
                    route = self._route_from_decorator(decorator, statement, file_path, bindings)
                    if route is not None:
                        routes.append(route)

                local = _bound_names(statement.body)
                arguments = statement.args
                parameters = [
                    *arguments.posonlyargs,
                    *arguments.args,
                    *arguments.kwonlyargs,
                    arguments.vararg,
                    arguments.kwarg,
                ]
                local.names.update(argument.arg for argument in parameters if argument is not None)
                inherited = {
                    name: kind
                    for name, kind in bindings.items()
                    if name not in local.names | written.names | later_names
                }
                if local.wildcard or later_wildcard:
                    inherited.clear()
                if not local.external:
                    self._parse_body(statement.body, inherited, file_path, routes)

            constructor = False
            if isinstance(statement, (ast.Assign, ast.AnnAssign)):
                constructor = self._is_constructor_call(statement.value, bindings)

            # Annotation-only statements do not overwrite an existing module/local value.
            if isinstance(statement, ast.AnnAssign) and statement.value is None:
                continue
            if written.wildcard:
                bindings.clear()
            else:
                for name in written.names:
                    bindings.pop(name, None)

            if isinstance(statement, ast.Import):
                for alias in statement.names:
                    name = alias.asname or alias.name.split(".")[0]
                    bindings.pop(name, None)
                    if alias.name == "fastapi":
                        bindings[name] = "module"
            elif isinstance(statement, ast.ImportFrom):
                for alias in statement.names:
                    name = alias.asname or alias.name
                    bindings.pop(name, None)
                    if (
                        statement.level == 0
                        and statement.module == "fastapi"
                        and alias.name in CONSTRUCTORS
                    ):
                        bindings[name] = "constructor"
            elif constructor:
                targets = (
                    statement.targets if isinstance(statement, ast.Assign) else [statement.target]
                )
                for target in targets:
                    if isinstance(target, ast.Name):
                        bindings[target.id] = "owner"

    @staticmethod
    def _is_constructor_call(value: ast.expr | None, bindings: dict[str, Binding]) -> bool:
        if not isinstance(value, ast.Call) or any(
            isinstance(node, ast.NamedExpr) for node in ast.walk(value)
        ):
            return False
        if isinstance(value.func, ast.Name):
            return bindings.get(value.func.id) == "constructor"
        return (
            isinstance(value.func, ast.Attribute)
            and isinstance(value.func.value, ast.Name)
            and bindings.get(value.func.value.id) == "module"
            and value.func.attr in CONSTRUCTORS
        )

    @staticmethod
    def _route_from_decorator(
        decorator: ast.expr,
        function: ast.FunctionDef | ast.AsyncFunctionDef,
        file_path: Path,
        bindings: dict[str, Binding],
    ) -> Route | None:
        if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
            return None

        receiver = decorator.func.value
        if not isinstance(receiver, ast.Name) or bindings.get(receiver.id) != "owner":
            return None
        if any(isinstance(node, ast.NamedExpr) for node in ast.walk(decorator)):
            return None

        method = decorator.func.attr
        if method not in HTTP_METHODS or not decorator.args:
            return None

        route_path = decorator.args[0]
        if not isinstance(route_path, ast.Constant) or not isinstance(route_path.value, str):
            return None

        return Route(
            path=route_path.value,
            methods=(method.upper(),),
            function=function.name,
            file=file_path,
            line=function.lineno,
        )
