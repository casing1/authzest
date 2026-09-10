from __future__ import annotations

import ast
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Literal, Protocol

from authzest.models import (
    DependencyEvidence,
    Diagnostic,
    IncludeSite,
    OwnerEvidence,
    RegistrationEvidence,
    Route,
    SourceLocation,
)
from authzest.parser.dependencies import (
    ANNOTATED_ALIAS,
    DEPENDENCY_FACTORIES,
    TYPING_MODULES,
    _RouteDependencies,
)

HTTP_METHODS = {"delete", "get", "head", "options", "patch", "post", "put"}
CONSTRUCTORS = {"FastAPI", "APIRouter"}
FASTAPI_EXPORTS = CONSTRUCTORS | DEPENDENCY_FACTORIES
Constructor = Literal["FastAPI", "APIRouter"]


@dataclass(eq=False, slots=True)
class _Owner:
    kind: Constructor
    prefix: str | None
    source: Path | None = None
    location: SourceLocation | None = None
    routes: list[Route] = field(default_factory=list)
    included: bool = False
    inherited: bool = False
    origin: _Owner | None = None
    children: set[_Owner] = field(default_factory=set)
    dependencies: tuple[DependencyEvidence, ...] = ()


@dataclass(slots=True)
class _ModuleRef:
    name: str
    inherited_owners: dict[_Owner, _Owner] | None = None
    imported_modules: frozenset[str] = frozenset()


Binding = (
    Literal[
        "module",
        "FastAPI",
        "APIRouter",
        "Depends",
        "Security",
        "typing-module",
        "Annotated",
        "dependency-annotation-alias",
    ]
    | _Owner
    | _ModuleRef
)


class _ImportResolver(Protocol):
    def imports(self, statement: ast.Import | ast.ImportFrom, path: Path) -> dict[str, Binding]: ...

    def attribute(self, module: _ModuleRef, name: str) -> Binding | None: ...


@dataclass(slots=True)
class _Registrations:
    entries: list[tuple[_Owner, Route]] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)

    def diagnose(self, code: str, message: str, path: Path, node: ast.AST) -> None:
        diagnostic = Diagnostic(code=code, message=message, location=_location(path, node))
        if diagnostic not in self.diagnostics:
            self.diagnostics.append(diagnostic)

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
    diagnostics: tuple[Diagnostic, ...] = ()


@dataclass(frozen=True, slots=True)
class RepositoryParseResult:
    routes: tuple[Route, ...]
    errors: tuple[str, ...] = ()
    diagnostics: tuple[Diagnostic, ...] = ()


def _location(path: Path, node: ast.AST) -> SourceLocation:
    return SourceLocation(file=path, line=node.lineno, column=node.col_offset + 1)


def _owner_evidence(owner: _Owner) -> OwnerEvidence:
    assert owner.location is not None
    return OwnerEvidence(kind=owner.kind, location=owner.location)


def _source_diagnostic(path: Path, exc: OSError | SyntaxError | UnicodeError) -> Diagnostic:
    line = None
    column = None
    if isinstance(exc, SyntaxError):
        code = "source-parse-error"
        line = exc.lineno if exc.lineno and exc.lineno > 0 else None
        if line is not None and exc.text and exc.offset and exc.offset > 0:
            column = len(exc.text[: exc.offset - 1].encode("utf-8")) + 1
    else:
        code = "source-read-error" if isinstance(exc, OSError) else "source-decode-error"
    return Diagnostic(
        code=code,
        message=str(exc),
        location=SourceLocation(file=path, line=line, column=column),
        severity="error",
    )


def _function_expressions(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[ast.expr | None]:
    arguments = function.args
    return [
        *function.decorator_list,
        *arguments.defaults,
        *arguments.kw_defaults,
        *(
            argument.annotation
            for argument in [
                *arguments.posonlyargs,
                *arguments.args,
                *arguments.kwonlyargs,
                arguments.vararg,
                arguments.kwarg,
            ]
            if argument is not None
        ),
        function.returns,
    ]


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
        for expression in _function_expressions(node):
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
        for expression in _function_expressions(node):
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


class _ConditionalDecorators(_IncludeCalls):
    """Inspect known-owner decorators in unsupported control flow, not function bodies."""

    def visit_Call(self, node: ast.Call) -> None:
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self.calls.extend(
            decorator for decorator in node.decorator_list if isinstance(decorator, ast.Call)
        )

    visit_AsyncFunctionDef = visit_FunctionDef


class FastAPIRouteParser:
    """Discover common FastAPI/APIRouter decorators without importing target code."""

    def parse_file(self, path: Path) -> ParseResult:
        try:
            tree = ast.parse(path.read_bytes(), filename=str(path))
        except (OSError, SyntaxError, UnicodeError) as exc:
            return ParseResult(
                routes=(), error=f"{path}: {exc}", diagnostics=(_source_diagnostic(path, exc),)
            )

        registrations = _Registrations()
        self._parse_body(tree.body, {}, path, registrations)
        return ParseResult(
            routes=registrations.result(), diagnostics=tuple(registrations.diagnostics)
        )

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
                if not (
                    isinstance(statement, ast.Expr) and call is statement.value
                ) and self._has_include_owner(call, bindings, resolver):
                    registrations.diagnose(
                        "unsupported-include-context",
                        "Include outside a standalone statement; execution is not assumed.",
                        file_path,
                        call,
                    )
            if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call):
                self._include_router(statement.value, bindings, registrations, file_path, resolver)

            if not isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
                conditional = _ConditionalDecorators()
                conditional.visit(statement)
                for decorator in conditional.calls:
                    if self._known_route_owner(decorator, bindings, resolver) is not None:
                        registrations.diagnose(
                            "conditional-registration",
                            "Route declaration is outside the supported sequential scope.",
                            file_path,
                            decorator,
                        )

            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Header assignments can change receivers; postponed evaluation is not inferred.
                expressions = _function_expressions(statement)
                dynamic = any(
                    isinstance(node, ast.NamedExpr)
                    for expression in expressions
                    if expression is not None
                    for node in ast.walk(expression)
                )
                for decorator in statement.decorator_list:
                    if dynamic:
                        if self._known_route_owner(decorator, bindings, resolver) is not None:
                            registrations.diagnose(
                                "unsupported-route-expression",
                                "Assignment expressions make the route owner uncertain.",
                                file_path,
                                decorator,
                            )
                        continue
                    found = self._route_from_decorator(
                        decorator, statement, file_path, bindings, registrations, resolver, deferred
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
                local.names.update(parameter.name for parameter in statement.type_params)
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
            annotation_alias = False
            if isinstance(statement, (ast.Assign, ast.AnnAssign)):
                owner = self._constructor_owner(statement.value, bindings)
                if owner is not None:
                    owner.source = file_path
                    owner.location = _location(file_path, statement.value)
                    owner.dependencies = self._dependency_collector(
                        bindings, registrations, file_path, resolver
                    ).collect_declared(
                        statement.value, "application" if owner.kind == "FastAPI" else "router"
                    )
                    if owner.prefix is None:
                        registrations.diagnose(
                            "unsupported-owner-construction",
                            "Owner arguments or prefix cannot be resolved by the bounded parser.",
                            file_path,
                            statement.value,
                        )
            if isinstance(statement, (ast.Assign, ast.AnnAssign, ast.TypeAlias)):
                dependency_collector = self._dependency_collector(
                    bindings, registrations, file_path, resolver
                )
                if isinstance(statement, ast.TypeAlias):
                    dependency_collector = dependency_collector.without_names(
                        {parameter.name for parameter in statement.type_params}
                    )
                annotation_alias = dependency_collector.is_annotation_alias(statement.value)

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
                    elif alias.name in TYPING_MODULES:
                        bindings[name] = "typing-module"
            elif isinstance(statement, ast.ImportFrom):
                for alias in statement.names:
                    name = alias.asname or alias.name
                    bindings.pop(name, None)
                    if (
                        statement.level == 0
                        and statement.module == "fastapi"
                        and alias.name in FASTAPI_EXPORTS
                    ):
                        bindings[name] = alias.name
                    elif (
                        statement.level == 0
                        and statement.module in TYPING_MODULES
                        and alias.name == "Annotated"
                    ):
                        bindings[name] = "Annotated"
            elif owner is not None:
                targets = (
                    statement.targets if isinstance(statement, ast.Assign) else [statement.target]
                )
                for target in targets:
                    if isinstance(target, ast.Name):
                        bindings[target.id] = owner
            elif annotation_alias:
                if isinstance(statement, ast.Assign):
                    targets = statement.targets
                elif isinstance(statement, ast.AnnAssign):
                    targets = [statement.target]
                else:
                    targets = [statement.name]
                for target in targets:
                    if isinstance(target, ast.Name):
                        bindings[target.id] = ANNOTATED_ALIAS

    @staticmethod
    def _inherit(binding: Binding, owners: dict[_Owner, _Owner]) -> Binding:
        if isinstance(binding, _Owner):
            return owners.setdefault(
                binding,
                _Owner(
                    binding.kind,
                    binding.prefix,
                    source=binding.source,
                    location=binding.location,
                    dependencies=binding.dependencies,
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
        if isinstance(expression, ast.Attribute):
            module = FastAPIRouteParser._binding(expression.value, bindings, resolver)
            if module == "module" and expression.attr in FASTAPI_EXPORTS:
                return expression.attr
            if module == "typing-module" and expression.attr == "Annotated":
                return "Annotated"
            if isinstance(module, _ModuleRef) and resolver is not None:
                found = resolver.attribute(module, expression.attr)
                if found is not None and module.inherited_owners is not None:
                    return FastAPIRouteParser._inherit(found, module.inherited_owners)
                return found
        return None

    @staticmethod
    def _dependency_collector(
        bindings: dict[str, Binding],
        registrations: _Registrations,
        file_path: Path,
        resolver: _ImportResolver | None,
    ) -> _RouteDependencies:
        def binding(expression: ast.expr) -> str | None:
            value = FastAPIRouteParser._binding(expression, bindings, resolver)
            return value if isinstance(value, str) else None

        return _RouteDependencies(
            file_path,
            binding,
            lambda code, message, node: registrations.diagnose(code, message, file_path, node),
        )

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
    def _has_include_owner(
        call: ast.Call, bindings: dict[str, Binding], resolver: _ImportResolver | None
    ) -> bool:
        if not isinstance(call.func, ast.Attribute) or call.func.attr != "include_router":
            return False
        candidates = [
            call.func.value,
            *call.args,
            *(keyword.value for keyword in call.keywords if keyword.arg in ("router", None)),
        ]
        return any(
            isinstance(FastAPIRouteParser._binding(node, bindings, resolver), _Owner)
            for candidate in candidates
            for node in ast.walk(candidate)
            if isinstance(node, (ast.Name, ast.Attribute))
        )

    @staticmethod
    def _include_router(
        call: ast.Call,
        bindings: dict[str, Binding],
        registrations: _Registrations,
        file_path: Path,
        resolver: _ImportResolver | None = None,
    ) -> None:
        if not isinstance(call.func, ast.Attribute) or call.func.attr != "include_router":
            return
        if not FastAPIRouteParser._has_include_owner(call, bindings, resolver):
            return

        def unresolved(code: str, message: str) -> None:
            registrations.diagnose(code, message, file_path, call)

        if any(keyword.arg is None for keyword in call.keywords) or any(
            isinstance(node, ast.NamedExpr) for node in ast.walk(call)
        ):
            unresolved("unsupported-include-arguments", "Expanded or assigning include arguments.")
            return
        parent = FastAPIRouteParser._binding(call.func.value, bindings, resolver)
        arguments = [
            *call.args,
            *(keyword.value for keyword in call.keywords if keyword.arg == "router"),
        ]
        if len(arguments) != 1:
            unresolved("unsupported-include-arguments", "Expected exactly one router argument.")
            return
        child = FastAPIRouteParser._binding(arguments[0], bindings, resolver)
        prefix = FastAPIRouteParser._literal_prefix(call)
        if (
            not isinstance(parent, _Owner)
            or not isinstance(child, _Owner)
            or child.kind != "APIRouter"
        ):
            unresolved("unresolved-include-owner", "Parent or child router could not be resolved.")
            return
        if parent is child:
            unresolved("include-cycle", "Self-inclusion is not composed.")
            return
        if parent.inherited or child.inherited or parent.source != file_path:
            unresolved("unsupported-include-context", "Cross-scope owner mutation is not composed.")
            return
        if parent.prefix is None or child.prefix is None or prefix is None:
            unresolved("dynamic-include-prefix", "Include or owner prefix is not a valid literal.")
            return
        # Supported composition uses declarations already present at this statement.
        # Later additions differ between FastAPI versions and remain out of scope.
        if not prefix and any(not route.path for route in child.routes):
            unresolved("unsupported-include-arguments", "Empty prefix and path are not composed.")
            return
        pending = [child]
        seen: set[_Owner] = set()
        while pending:
            descendant = pending.pop()
            if descendant is parent:
                unresolved("include-cycle", "Cyclic router inclusion is not composed.")
                return
            if descendant not in seen:
                seen.add(descendant)
                pending.extend(descendant.children)
        parent.children.add(child)
        include_dependencies = FastAPIRouteParser._dependency_collector(
            bindings, registrations, file_path, resolver
        ).collect_declared(call, "include")
        for route in tuple(child.routes):
            registration = route.registration
            assert registration is not None
            include = IncludeSite(
                location=_location(file_path, call),
                parent=_owner_evidence(parent),
                router=_owner_evidence(child),
                prefix=prefix,
            )
            registration = replace(
                registration,
                application=_owner_evidence(parent) if parent.kind == "FastAPI" else None,
                include_chain=(include, *registration.include_chain),
            )
            registrations.add(
                parent,
                replace(
                    route,
                    path=parent.prefix + prefix + route.path,
                    registration=registration,
                    inherited_dependencies=(
                        *parent.dependencies,
                        *include_dependencies,
                        *route.inherited_dependencies,
                    ),
                ),
            )

    @staticmethod
    def _known_route_owner(
        decorator: ast.expr, bindings: dict[str, Binding], resolver: _ImportResolver | None
    ) -> _Owner | None:
        if (
            isinstance(decorator, ast.Call)
            and isinstance(decorator.func, ast.Attribute)
            and decorator.func.attr in HTTP_METHODS | {"api_route"}
        ):
            owner = FastAPIRouteParser._binding(decorator.func.value, bindings, resolver)
            if isinstance(owner, _Owner):
                return owner
        return None

    @staticmethod
    def _route_from_decorator(
        decorator: ast.expr,
        function: ast.FunctionDef | ast.AsyncFunctionDef,
        file_path: Path,
        bindings: dict[str, Binding],
        registrations: _Registrations,
        resolver: _ImportResolver | None = None,
        deferred: bool = False,
    ) -> tuple[_Owner, Route] | None:
        if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
            return None

        owner = FastAPIRouteParser._known_route_owner(decorator, bindings, resolver)
        if owner is None:
            return None
        if owner.prefix is None or owner.source != file_path:
            registrations.diagnose(
                "unsupported-route-owner",
                "Route owner prefix or cross-file mutation cannot be resolved.",
                file_path,
                decorator,
            )
            return None
        if any(isinstance(node, ast.NamedExpr) for node in ast.walk(decorator)):
            registrations.diagnose(
                "unsupported-route-expression",
                "Assignment expressions make the route declaration uncertain.",
                file_path,
                decorator,
            )
            return None

        method = decorator.func.attr
        if (
            method not in HTTP_METHODS
            or len(decorator.args) != 1
            or any(keyword.arg in (None, "path") for keyword in decorator.keywords)
        ):
            registrations.diagnose(
                "unsupported-route-arguments",
                "Expected a supported HTTP decorator with one positional literal path.",
                file_path,
                decorator,
            )
            return None

        route_path = decorator.args[0]
        if not isinstance(route_path, ast.Constant) or not isinstance(route_path.value, str):
            registrations.diagnose(
                "dynamic-route-path",
                "Route path is not a string literal.",
                file_path,
                decorator,
            )
            return None

        return owner, Route(
            path=owner.prefix + route_path.value,
            methods=(method.upper(),),
            function=function.name,
            file=file_path,
            line=function.lineno,
            registration=RegistrationEvidence(
                declaration=_location(file_path, decorator),
                owner=_owner_evidence(owner),
                application=_owner_evidence(owner) if owner.kind == "FastAPI" else None,
                execution_scope="deferred" if deferred else "module",
            ),
            dependencies=FastAPIRouteParser._dependency_collector(
                bindings, registrations, file_path, resolver
            ).collect(function, decorator),
            inherited_dependencies=owner.dependencies,
        )
