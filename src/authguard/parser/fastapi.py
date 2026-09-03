from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from authguard.models import Route

HTTP_METHODS = {"delete", "get", "head", "options", "patch", "post", "put"}


@dataclass(frozen=True, slots=True)
class ParseResult:
    routes: tuple[Route, ...]
    error: str | None = None


class FastAPIRouteParser:
    """Discover common FastAPI/APIRouter decorators without importing target code."""

    def parse_file(self, path: Path) -> ParseResult:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError, UnicodeError) as exc:
            return ParseResult(routes=(), error=f"{path}: {exc}")

        routes: list[Route] = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                route = self._route_from_decorator(decorator, node, path)
                if route is not None:
                    routes.append(route)
        return ParseResult(routes=tuple(routes))

    @staticmethod
    def _route_from_decorator(
        decorator: ast.expr,
        function: ast.FunctionDef | ast.AsyncFunctionDef,
        file_path: Path,
    ) -> Route | None:
        if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
            return None

        method = decorator.func.attr.lower()
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
