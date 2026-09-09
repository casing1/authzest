from __future__ import annotations

import ast
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Literal, Protocol

from authzest.models import Route

HTTP_METHODS = {"delete", "get", "head", "options", "patch", "post", "put"}
CONSTRUCTORS = {"FastAPI", "APIRouter"}
Constructor = Literal["FastAPI", "APIRouter"]


@dataclass(eq=False, slots=True)
class _Owner:
    kind: Constructor
    prefix: str | None
    source: Path | None = None
    routes: list[Route] = field(default_factory=list)
    included: bool = False
    inherited: bool = False
    origin: _Owner | None = None
    children: set[_Owner] = field(default_factory=set)


@dataclass(slots=True)
class _ModuleRef:
    name: str
    inherited_owners: dict[_Owner, _Owner] | None = None
    imported_modules: frozenset[str] = frozenset()


Binding = Literal["module", "FastAPI", "APIRouter"] | _Owner | _ModuleRef


class _ImportResolver(Protocol):
    def imports(self, statement: ast.Import | ast.ImportFrom, path: Path) -> dict[str, Binding]: ...

    def attribute(self, module: _ModuleRef, name: str) -> Binding | None: ...


@dataclass(slots=True)
class _Registrations:
    entries: list[tuple[_Owner, Route]] = field(default_factory=list)

    def add(self, owner: _Owner, route: Route) -> None:
        owner.routes.append(route)
        self.entries.append((owner, route))

    def result(self) -> tuple[Route, ...]:
        return tuple(
            route
            for owner, route in self.entries
            if owner.kind == "FastAPI"
            or not (owner.included or (owner.origin is not None and owner.origin.included))
        )


@dataclass(frozen=True, slots=True)
class ParseResult:
    routes: tuple[Route, ...]
    error: str | None = None


@dataclass(frozen=True, slots=True)
class RepositoryParseResult:
    routes: tuple[Route, ...]
    errors: tuple[str, ...] = ()


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


class _IncludeCalls(ast.NodeVisitor):
    """Find attempted includes, without assuming conditional calls execute."""

    def __init__(self) -> None:
        self.calls: list[ast.Call] = []

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Attribute) and node.func.attr == "include_router":
            self.calls.append(node)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        for expression in [*node.decorator_list, *node.args.defaults, *node.args.kw_defaults]:
            if expression is not None:
                self.visit(expression)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        # Class-body names belong to an unsupported scope, not the enclosing bindings.
        for expression in [*node.decorator_list, *node.bases, *node.keywords]:
            self.visit(expression)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        for expression in [*node.args.defaults, *node.args.kw_defaults]:
            if expression is not None:
                self.visit(expression)


class FastAPIRouteParser:
    """Discover common FastAPI/APIRouter decorators without importing target code."""

    def parse_file(self, path: Path) -> ParseResult:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError, UnicodeError) as exc:
            return ParseResult(routes=(), error=f"{path}: {exc}")

        registrations = _Registrations()
        self._parse_body(tree.body, {}, path, registrations)
        return ParseResult(routes=registrations.result())

    def parse_repository(self, root: Path, paths: list[Path]) -> RepositoryParseResult:
        from authzest.parser.repository import _RepositoryParser

        return _RepositoryParser(self, root, paths).parse()

    def _parse_body(
        self,
        body: list[ast.stmt],
        bindings: dict[str, Binding],
        file_path: Path,
        registrations: _Registrations,
        resolver: _ImportResolver | None = None,
        deferred: bool = False,
    ) -> None:
        # Function bodies are inventoried independently, not executed at their definition.
        # Preserve stable names without allowing an inner include to mutate an outer graph.
        inherited_owners: dict[_Owner, _Owner] = {}
        for name, binding in bindings.items():
            bindings[name] = self._inherit(binding, inherited_owners)

        # A function executes later: do not inherit names changed later in its outer scope.
        later_writes: list[tuple[set[str], bool]] = []
        collector = _BoundNames()
        for statement in reversed(body):
            later_writes.append((collector.names.copy(), collector.wildcard))
            collector.visit(statement)

        for statement, (later_names, later_wildcard) in zip(
            body, reversed(later_writes), strict=True
        ):
            prior_bindings = bindings.copy()
            written = _bound_names([statement])
            attempts = _IncludeCalls()
            attempts.visit(statement)
            for call in attempts.calls:
                self._suppress_included_declarations(call, bindings, resolver)
            if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call):
                self._include_router(statement.value, bindings, registrations, file_path, resolver)

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
                    found = self._route_from_decorator(
                        decorator, statement, file_path, bindings, resolver
                    )
                    if found is not None:
                        owner, route = found
                        registrations.add(owner, route)

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
                    self._parse_body(
                        statement.body, inherited, file_path, registrations, resolver, deferred=True
                    )

            owner = None
            if isinstance(statement, (ast.Assign, ast.AnnAssign)):
                owner = self._constructor_owner(statement.value, bindings)
                if owner is not None:
                    owner.source = file_path

            # Annotation-only statements do not overwrite an existing module/local value.
            if isinstance(statement, ast.AnnAssign) and statement.value is None:
                continue
            if written.wildcard:
                bindings.clear()
            else:
                for name in written.names:
                    bindings.pop(name, None)

            if isinstance(statement, (ast.Import, ast.ImportFrom)) and resolver is not None:
                imported = resolver.imports(statement, file_path)
                if isinstance(statement, ast.Import):
                    for name, binding in imported.items():
                        previous = prior_bindings.get(name)
                        if (
                            isinstance(binding, _ModuleRef)
                            and isinstance(previous, _ModuleRef)
                            and binding.name == previous.name
                        ):
                            binding.imported_modules |= previous.imported_modules
                bindings.update(
                    {
                        name: self._inherit(binding, inherited_owners) if deferred else binding
                        for name, binding in imported.items()
                    }
                )
            elif isinstance(statement, ast.Import):
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
                        bindings[name] = alias.name
            elif owner is not None:
                targets = (
                    statement.targets if isinstance(statement, ast.Assign) else [statement.target]
                )
                for target in targets:
                    if isinstance(target, ast.Name):
                        bindings[target.id] = owner

    @staticmethod
    def _inherit(binding: Binding, owners: dict[_Owner, _Owner]) -> Binding:
        if isinstance(binding, _Owner):
            return owners.setdefault(
                binding,
                _Owner(
                    binding.kind,
                    binding.prefix,
                    source=binding.source,
                    inherited=True,
                    origin=binding.origin or binding,
                ),
            )
        if isinstance(binding, _ModuleRef):
            return _ModuleRef(binding.name, owners, binding.imported_modules)
        return binding

    @staticmethod
    def _binding(
        expression: ast.expr,
        bindings: dict[str, Binding],
        resolver: _ImportResolver | None,
    ) -> Binding | None:
        if isinstance(expression, ast.Name):
            return bindings.get(expression.id)
        if isinstance(expression, ast.Attribute) and resolver is not None:
            module = FastAPIRouteParser._binding(expression.value, bindings, resolver)
            if isinstance(module, _ModuleRef):
                found = resolver.attribute(module, expression.attr)
                if found is not None and module.inherited_owners is not None:
                    return FastAPIRouteParser._inherit(found, module.inherited_owners)
                return found
        return None

    @staticmethod
    def _constructor_owner(value: ast.expr | None, bindings: dict[str, Binding]) -> _Owner | None:
        if not isinstance(value, ast.Call) or any(
            isinstance(node, ast.NamedExpr) for node in ast.walk(value)
        ):
            return None
        kind: Binding | None = None
        if isinstance(value.func, ast.Name):
            kind = bindings.get(value.func.id)
        elif (
            isinstance(value.func, ast.Attribute)
            and isinstance(value.func.value, ast.Name)
            and bindings.get(value.func.value.id) == "module"
            and value.func.attr in CONSTRUCTORS
        ):
            kind = value.func.attr
        if kind not in ("FastAPI", "APIRouter"):
            return None
        prefix = FastAPIRouteParser._literal_prefix(value) if kind == "APIRouter" else ""
        if value.args or any(keyword.arg is None for keyword in value.keywords):
            prefix = None
        return _Owner(kind, prefix)

    @staticmethod
    def _literal_prefix(call: ast.Call) -> str | None:
        values = [keyword.value for keyword in call.keywords if keyword.arg == "prefix"]
        if not values:
            return ""
        if len(values) != 1:
            return None
        value = values[0]
        if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
            return None
        prefix = value.value
        if prefix and (not prefix.startswith("/") or prefix.endswith("/")):
            return None
        return prefix

    @staticmethod
    def _suppress_included_declarations(
        call: ast.Call, bindings: dict[str, Binding], resolver: _ImportResolver | None = None
    ) -> None:
        # Even an unresolved mount must not turn into a guessed unprefixed endpoint.
        arguments = [
            *call.args,
            *(keyword.value for keyword in call.keywords if keyword.arg in ("router", None)),
        ]
        for argument in arguments:
            for node in ast.walk(argument):
                if isinstance(node, (ast.Name, ast.Attribute)):
                    child = FastAPIRouteParser._binding(node, bindings, resolver)
                    if isinstance(child, _Owner) and child.kind == "APIRouter":
                        child.included = True

    @staticmethod
    def _include_router(
        call: ast.Call,
        bindings: dict[str, Binding],
        registrations: _Registrations,
        file_path: Path,
        resolver: _ImportResolver | None = None,
    ) -> None:
        if (
            not isinstance(call.func, ast.Attribute)
            or call.func.attr != "include_router"
            or any(keyword.arg is None for keyword in call.keywords)
            or any(isinstance(node, ast.NamedExpr) for node in ast.walk(call))
        ):
            return
        parent = FastAPIRouteParser._binding(call.func.value, bindings, resolver)
        arguments = [
            *call.args,
            *(keyword.value for keyword in call.keywords if keyword.arg == "router"),
        ]
        if len(arguments) != 1:
            return
        child = FastAPIRouteParser._binding(arguments[0], bindings, resolver)
        prefix = FastAPIRouteParser._literal_prefix(call)
        if (
            not isinstance(parent, _Owner)
            or not isinstance(child, _Owner)
            or child.kind != "APIRouter"
            or parent is child
            or parent.inherited
            or child.inherited
            or parent.source != file_path
            or parent.prefix is None
            or child.prefix is None
            or prefix is None
        ):
            return
        # Supported composition uses declarations already present at this statement.
        # Later additions differ between FastAPI versions and remain out of scope.
        if not prefix and any(not route.path for route in child.routes):
            return
        pending = [child]
        seen: set[_Owner] = set()
        while pending:
            descendant = pending.pop()
            if descendant is parent:
                return
            if descendant not in seen:
                seen.add(descendant)
                pending.extend(descendant.children)
        parent.children.add(child)
        for route in tuple(child.routes):
            registrations.add(parent, replace(route, path=parent.prefix + prefix + route.path))

    @staticmethod
    def _route_from_decorator(
        decorator: ast.expr,
        function: ast.FunctionDef | ast.AsyncFunctionDef,
        file_path: Path,
        bindings: dict[str, Binding],
        resolver: _ImportResolver | None = None,
    ) -> tuple[_Owner, Route] | None:
        if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
            return None

        receiver = decorator.func.value
        owner = FastAPIRouteParser._binding(receiver, bindings, resolver)
        if not isinstance(owner, _Owner) or owner.prefix is None or owner.source != file_path:
            return None
        if any(isinstance(node, ast.NamedExpr) for node in ast.walk(decorator)):
            return None

        method = decorator.func.attr
        if (
            method not in HTTP_METHODS
            or len(decorator.args) != 1
            or any(keyword.arg in (None, "path") for keyword in decorator.keywords)
        ):
            return None

        route_path = decorator.args[0]
        if not isinstance(route_path, ast.Constant) or not isinstance(route_path.value, str):
            return None

        return owner, Route(
            path=owner.prefix + route_path.value,
            methods=(method.upper(),),
            function=function.name,
            file=file_path,
            line=function.lineno,
        )
