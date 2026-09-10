from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from authzest.parser.dependencies import TYPING_MODULES
from authzest.parser.fastapi import (
    FASTAPI_EXPORTS,
    Binding,
    FastAPIRouteParser,
    RepositoryParseResult,
    _bound_names,
    _ModuleRef,
    _Registrations,
    _source_diagnostic,
)


def is_local_source(path: Path, root: Path) -> bool:
    """Accept only regular files reached without a symlink inside the scan root."""
    if not path.is_relative_to(root) or ".." in path.relative_to(root).parts:
        return False
    if any(part.is_symlink() for part in (path, *path.parents) if part.is_relative_to(root)):
        return False
    return path.is_file()


@dataclass(frozen=True, slots=True)
class _Location:
    path: Path
    package: bool
    namespace: bool = False


class _RepositoryParser:
    """Resolve a bounded source-only import graph, never Python's runtime search path."""

    def __init__(self, parser: FastAPIRouteParser, root: Path, paths: list[Path]) -> None:
        self.parser = parser
        self.root = root
        self.paths = sorted({path for path in paths if is_local_source(path, root)})
        self.trees: dict[Path, ast.Module] = {}
        self.errors: list[str] = []
        self.locations: dict[str, dict[Path, _Location]] = {}
        self.packages: dict[Path, str] = {}
        self.exports: dict[Path, dict[str, Binding]] = {}
        self.loading: set[Path] = set()
        self.registrations = _Registrations()
        for path in self.paths:
            try:
                self.trees[path] = ast.parse(path.read_bytes(), filename=str(path))
            except (OSError, SyntaxError, UnicodeError) as exc:
                self.errors.append(f"{path}: {exc}")
                self.registrations.diagnostics.append(_source_diagnostic(path, exc))
        self._index()
        self.cyclic = self._cyclic_modules()

    def parse(self) -> RepositoryParseResult:
        for path in self.paths:
            self._load(path)
        return RepositoryParseResult(
            self.registrations.result(), tuple(self.errors), tuple(self.registrations.diagnostics)
        )

    def _index(self) -> None:
        roots = [self.root, self.root / "src"]
        for source_root in roots:
            for path in self.paths:
                if not path.is_relative_to(source_root):
                    continue
                relative = path.relative_to(source_root)
                package = path.name == "__init__.py"
                parts = relative.parts[:-1] if package else (*relative.parts[:-1], path.stem)
                if not parts or not all(part.isidentifier() for part in parts):
                    continue
                name = ".".join(parts)
                key = path.parent if package else path
                self.locations.setdefault(name, {})[key] = _Location(path, package)
                self.packages[path] = ".".join(parts if package else parts[:-1])
                for length in range(1, len(parts)):
                    parent_name = ".".join(parts[:length])
                    directory = source_root.joinpath(*parts[:length])
                    self.locations.setdefault(parent_name, {}).setdefault(
                        directory, _Location(directory, package=True, namespace=True)
                    )

    def _location(self, name: str) -> _Location | None:
        parts = name.split(".")
        for length in range(1, len(parts) + 1):
            candidates = self.locations.get(".".join(parts[:length]), {})
            if len(candidates) != 1:
                return None
            location = next(iter(candidates.values()))
            if length < len(parts) and not location.package:
                return None
        return location

    def _base(self, statement: ast.ImportFrom, path: Path) -> str | None:
        if not statement.level:
            return statement.module or None
        package = self.packages.get(path, "").split(".")
        if not package[0] or statement.level > len(package):
            return None
        components = package[: len(package) - statement.level + 1]
        if statement.module:
            components.extend(statement.module.split("."))
        return ".".join(components)

    def _dependencies(self, path: Path, tree: ast.Module) -> set[Path]:
        dependencies: set[Path] = set()
        for statement in tree.body:
            names: list[str] = []
            if isinstance(statement, ast.Import):
                names = [alias.name for alias in statement.names]
            elif isinstance(statement, ast.ImportFrom):
                base = self._base(statement, path)
                if base:
                    names = [f"{base}.{alias.name}" for alias in statement.names]
                    location = self._location(base)
                    if location is None or location.path != path or not location.package:
                        names.append(base)
            for name in names:
                location = self._location(name)
                if location is not None and not location.namespace:
                    dependencies.add(location.path)
        return dependencies

    def _cyclic_modules(self) -> set[Path]:
        # Find strongly connected components before exposing any exports. A cycle must not
        # produce a different mounted path depending on which source file is scanned first.
        graph = {path: self._dependencies(path, tree) for path, tree in self.trees.items()}
        reverse: dict[Path, set[Path]] = {path: set() for path in graph}
        for source, targets in graph.items():
            for target in targets:
                reverse.setdefault(target, set()).add(source)
        order: list[Path] = []
        seen: set[Path] = set()
        for path in graph:
            stack = [(path, False)]
            while stack:
                current, leaving = stack.pop()
                if leaving:
                    order.append(current)
                elif current not in seen:
                    seen.add(current)
                    stack.append((current, True))
                    stack.extend((target, False) for target in sorted(graph.get(current, ())))
        visited: set[Path] = set()
        cyclic: set[Path] = set()
        for path in reversed(order):
            if path in visited:
                continue
            component: set[Path] = set()
            pending = [path]
            while pending:
                current = pending.pop()
                if current not in visited:
                    visited.add(current)
                    component.add(current)
                    pending.extend(reverse.get(current, ()))
            if len(component) > 1 or path in graph.get(path, ()):
                cyclic.update(component)
        return cyclic

    def _load(self, path: Path) -> dict[str, Binding]:
        if path in self.exports:
            return self.exports[path]
        if path in self.loading or path not in self.trees:
            return {}
        self.loading.add(path)
        bindings: dict[str, Binding] = {}
        self.parser._parse_body(self.trees[path].body, bindings, path, self.registrations, self)
        self.loading.remove(path)
        self.exports[path] = bindings
        return bindings

    def _module(self, name: str, imported: frozenset[str] = frozenset()) -> _ModuleRef | None:
        location = self._location(name)
        if location is None:
            return None
        if not location.namespace:
            if (
                location.path in self.cyclic
                or location.path in self.loading
                or location.path not in self.trees
            ):
                return None
            self._load(location.path)
        return _ModuleRef(name, imported_modules=imported)

    def _export(self, module: _ModuleRef, name: str, allow_submodule: bool) -> Binding | None:
        location = self._location(module.name)
        if location is None:
            return None
        if not location.namespace:
            if location.path in self.cyclic or location.path in self.loading:
                return None
            exports = self._load(location.path)
            if name in exports:
                return exports[name]
            tree = self.trees.get(location.path)
            if tree is None:
                return None
            written = _bound_names(tree.body)
            if name in written.names or written.wildcard:
                return None
        child = f"{module.name}.{name}"
        explicitly_imported = any(
            imported == child or imported.startswith(child + ".")
            for imported in module.imported_modules
        )
        if location.package and (allow_submodule or explicitly_imported):
            return self._module(child, module.imported_modules)
        return None

    def attribute(self, module: _ModuleRef, name: str) -> Binding | None:
        return self._export(module, name, allow_submodule=False)

    def imports(self, statement: ast.Import | ast.ImportFrom, path: Path) -> dict[str, Binding]:
        bindings: dict[str, Binding] = {}
        if isinstance(statement, ast.Import):
            for alias in statement.names:
                name = alias.asname or alias.name.split(".")[0]
                if alias.name == "fastapi" and "fastapi" not in self.locations:
                    bindings[name] = "module"
                    continue
                if alias.name in TYPING_MODULES and alias.name not in self.locations:
                    bindings[name] = "typing-module"
                    continue
                module = self._module(alias.name)
                if module is not None:
                    imported = frozenset({alias.name})
                    binding_name = alias.name if alias.asname else alias.name.split(".")[0]
                    existing = bindings.get(name)
                    if isinstance(existing, _ModuleRef) and existing.name == binding_name:
                        imported |= existing.imported_modules
                    bindings[name] = _ModuleRef(binding_name, imported_modules=imported)
            return bindings
        base = self._base(statement, path)
        if base is None or any(alias.name == "*" for alias in statement.names):
            return bindings
        if statement.level == 0 and base == "fastapi" and "fastapi" not in self.locations:
            return {
                alias.asname or alias.name: alias.name
                for alias in statement.names
                if alias.name in FASTAPI_EXPORTS
            }
        if statement.level == 0 and base in TYPING_MODULES and base not in self.locations:
            return {
                alias.asname or alias.name: "Annotated"
                for alias in statement.names
                if alias.name == "Annotated"
            }
        location = self._location(base)
        if location is not None and location.path == path and location.package:
            # A package initializer may import a child without reading its own partial exports.
            # Prior writes to that name make this form ambiguous, so do not infer a submodule.
            body = self.trees[path].body
            if statement not in body:
                return bindings
            written = _bound_names(body[: body.index(statement)])
            for alias in statement.names:
                if alias.name not in written.names and not written.wildcard:
                    child = self._module(f"{base}.{alias.name}")
                    if child is not None:
                        bindings[alias.asname or alias.name] = child
            return bindings
        module = self._module(base)
        if module is not None:
            for alias in statement.names:
                binding = self._export(module, alias.name, allow_submodule=True)
                if binding is not None:
                    bindings[alias.asname or alias.name] = binding
        return bindings
