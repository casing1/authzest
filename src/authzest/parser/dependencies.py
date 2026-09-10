from __future__ import annotations

import ast
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Literal

from authzest.models import DependencyEvidence, DependencyLevel, SourceLocation

DEPENDENCY_FACTORIES = {"Depends", "Security"}
TYPING_MODULES = {"typing", "typing_extensions"}
ANNOTATED_ALIAS = "dependency-annotation-alias"


class _RouteDependencies:
    """Collect declared dependency syntax; never resolve or execute a callable."""

    def __init__(
        self,
        path: Path,
        binding: Callable[[ast.expr], str | None],
        diagnose: Callable[[str, str, ast.AST], None],
    ) -> None:
        self.path = path
        self.binding = binding
        self.diagnose = diagnose

    def _kind(self, expression: ast.expr) -> Literal["Depends", "Security"] | None:
        kind = self.binding(expression)
        return kind if kind in ("Depends", "Security") else None

    def _known_call(self, expression: ast.expr) -> bool:
        return isinstance(expression, ast.Call) and self._kind(expression.func) is not None

    def _contains_call(self, expression: ast.expr) -> bool:
        return any(
            isinstance(node, ast.Call) and self._kind(node.func) is not None
            for node in ast.walk(expression)
        )

    def without_names(self, names: set[str]) -> _RouteDependencies:
        def binding(expression: ast.expr) -> str | None:
            root = expression
            while isinstance(root, ast.Attribute):
                root = root.value
            if isinstance(root, ast.Name) and root.id in names:
                return None
            return self.binding(expression)

        return _RouteDependencies(self.path, binding, self.diagnose)

    def is_annotation_alias(self, expression: ast.expr | None) -> bool:
        if expression is None:
            return False
        if self.binding(expression) == ANNOTATED_ALIAS:
            return True
        if (
            isinstance(expression, ast.Subscript)
            and self.binding(expression.value) == "Annotated"
            and isinstance(expression.slice, ast.Tuple)
        ):
            return any(self._contains_call(metadata) for metadata in expression.slice.elts[1:])
        return False

    def collect(
        self, function: ast.FunctionDef | ast.AsyncFunctionDef, decorator: ast.Call
    ) -> tuple[DependencyEvidence, ...]:
        found = list(self.collect_declared(decorator, "decorator"))
        parameter_collector = self.without_names(
            {parameter.name for parameter in function.type_params}
        )
        arguments = function.args
        positional = [*arguments.posonlyargs, *arguments.args]
        defaults = dict(
            zip(
                (
                    parameter.arg
                    for parameter in positional[len(positional) - len(arguments.defaults) :]
                ),
                arguments.defaults,
                strict=True,
            )
        )
        defaults.update(
            (parameter.arg, default)
            for parameter, default in zip(arguments.kwonlyargs, arguments.kw_defaults, strict=True)
            if default is not None
        )
        for parameter in [*positional, *arguments.kwonlyargs, arguments.vararg, arguments.kwarg]:
            if parameter is None:
                continue
            evidence = parameter_collector._annotation(parameter.annotation, parameter.arg)
            default = defaults.get(parameter.arg)
            if default is not None:
                # PEP 695 type parameters scope annotations, not defaults or decorators.
                if self._known_call(default):
                    evidence.append(self._call(default, "parameter-default", parameter.arg))
                elif self._contains_call(default):
                    self.diagnose(
                        "unsupported-dependency-expression",
                        "A nested dependency call is not a direct parameter default.",
                        default,
                    )
            if len(evidence) > 1:
                reason = "ambiguous-dependency-declaration"
                self.diagnose(
                    reason,
                    "Multiple dependency declarations for one parameter are not interpreted.",
                    parameter,
                )
                evidence = [
                    replace(
                        item,
                        resolution="unresolved",
                        unresolved_reasons=tuple(dict.fromkeys((*item.unresolved_reasons, reason))),
                    )
                    for item in evidence
                ]
            found.extend(evidence)
        return tuple(
            sorted(found, key=lambda item: (item.location.line or 0, item.location.column or 0))
        )

    def _annotation(self, annotation: ast.expr | None, parameter: str) -> list[DependencyEvidence]:
        if annotation is None:
            return []
        if self.binding(annotation) == ANNOTATED_ALIAS:
            self.diagnose(
                "unsupported-dependency-annotation",
                "A known dependency-bearing Annotated alias is not expanded.",
                annotation,
            )
            return []
        if not (
            isinstance(annotation, ast.Subscript)
            and self.binding(annotation.value) == "Annotated"
            and isinstance(annotation.slice, ast.Tuple)
        ):
            if any(
                isinstance(node, ast.expr) and self.is_annotation_alias(node)
                for node in ast.walk(annotation)
            ):
                self.diagnose(
                    "unsupported-dependency-annotation",
                    "A dependency-bearing annotation is nested in an unsupported expression.",
                    annotation,
                )
            return []
        found = []
        if not annotation.slice.elts:
            return found
        # The first item is the type, never dependency metadata.
        if any(
            isinstance(node, ast.expr) and self.is_annotation_alias(node)
            for node in ast.walk(annotation.slice.elts[0])
        ):
            self.diagnose(
                "unsupported-dependency-annotation",
                "A dependency-bearing type argument is nested; it is not expanded.",
                annotation.slice.elts[0],
            )
        for metadata in annotation.slice.elts[1:]:
            if self._known_call(metadata):
                found.append(self._call(metadata, "parameter-annotation", parameter))
            elif self._contains_call(metadata) or self._kind(metadata) is not None:
                self.diagnose(
                    "unsupported-dependency-metadata",
                    "Dependency metadata must be a direct Depends or Security call.",
                    metadata,
                )
        return found

    def collect_declared(
        self,
        call: ast.Call,
        level: Literal["decorator", "application", "router", "include"],
    ) -> tuple[DependencyEvidence, ...]:
        declarations = [keyword.value for keyword in call.keywords if keyword.arg == "dependencies"]
        if len(declarations) > 1:
            self.diagnose(
                "unsupported-dependency-list",
                f"The {level} declaration has repeated dependencies arguments.",
                call,
            )
        found = []
        for declaration in declarations:
            if isinstance(declaration, ast.Constant) and declaration.value is None:
                continue
            if not isinstance(declaration, ast.List):
                self.diagnose(
                    "unsupported-dependency-list",
                    "Declared dependencies must be a literal list or None.",
                    declaration,
                )
                continue
            for entry in declaration.elts:
                if self._known_call(entry):
                    evidence = self._call(entry, level, None)
                    if len(declarations) > 1:
                        evidence = replace(
                            evidence,
                            resolution="unresolved",
                            unresolved_reasons=tuple(
                                dict.fromkeys(
                                    (*evidence.unresolved_reasons, "unsupported-dependency-list")
                                )
                            ),
                        )
                    found.append(evidence)
                else:
                    self.diagnose(
                        "unsupported-dependency-entry",
                        "A declared dependency entry is not a recognized direct dependency call.",
                        entry,
                    )
        return tuple(found)

    def _call(
        self,
        call: ast.Call,
        level: DependencyLevel,
        parameter: str | None,
    ) -> DependencyEvidence:
        kind = self._kind(call.func)
        assert kind is not None
        reasons: list[str] = []

        def unresolved(code: str, message: str) -> None:
            if code not in reasons:
                reasons.append(code)
                self.diagnose(code, message, call)

        allowed = {"dependency", "use_cache", "scope" if kind == "Depends" else "scopes"}
        keywords = [keyword.arg for keyword in call.keywords]
        expanded = None in keywords or any(
            isinstance(argument, ast.Starred) for argument in call.args
        )
        if (
            expanded
            or len(call.args) > 1
            or len(set(keywords)) != len(keywords)
            or any(keyword not in allowed for keyword in keywords)
        ):
            unresolved(
                "unsupported-dependency-arguments",
                "Expanded, repeated, extra positional, or unknown dependency arguments.",
            )
        targets = [
            *call.args,
            *(keyword.value for keyword in call.keywords if keyword.arg == "dependency"),
        ]
        target = (
            targets[0] if len(targets) == 1 and not isinstance(targets[0], ast.Starred) else None
        )
        if len(targets) > 1:
            unresolved("unsupported-dependency-arguments", "The dependency target is ambiguous.")
        target_text = None
        if target is not None and not (isinstance(target, ast.Constant) and target.value is None):
            target_text = ast.unparse(target)
        if target_text is None or not self._reference(target):
            unresolved(
                "unresolved-dependency-target",
                "The dependency target is implicit or is not a plain name/dotted-name reference.",
            )
        scopes: tuple[str, ...] | None = None
        if kind == "Security":
            values = [keyword.value for keyword in call.keywords if keyword.arg == "scopes"]
            if None in keywords or len(values) > 1:
                unresolved(
                    "dynamic-security-scopes", "Expanded or repeated Security scopes are unknown."
                )
            elif not values or (isinstance(values[0], ast.Constant) and values[0].value is None):
                scopes = ()
            elif isinstance(values[0], ast.List) and all(
                isinstance(value, ast.Constant) and isinstance(value.value, str)
                for value in values[0].elts
            ):
                scopes = tuple(value.value for value in values[0].elts)
            else:
                unresolved(
                    "dynamic-security-scopes", "Security scopes are not a literal list of strings."
                )
        return DependencyEvidence(
            kind=kind,
            target=target_text,
            location=SourceLocation(file=self.path, line=call.lineno, column=call.col_offset + 1),
            declaration_level=level,
            parameter=parameter,
            resolution="unresolved" if reasons else "reference",
            scopes=scopes,
            unresolved_reasons=tuple(reasons),
        )

    @staticmethod
    def _reference(expression: ast.expr | None) -> bool:
        while isinstance(expression, ast.Attribute):
            expression = expression.value
        return isinstance(expression, ast.Name)
