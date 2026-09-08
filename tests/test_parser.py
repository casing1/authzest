from pathlib import Path
from textwrap import dedent

import pytest

from authzest.parser import FastAPIRouteParser


@pytest.mark.parametrize(
    "setup",
    [
        "from fastapi import FastAPI\nrouter = FastAPI()",
        "from fastapi import APIRouter\nrouter = APIRouter()",
        "from fastapi import FastAPI as Application\nrouter = Application()",
        "from fastapi import APIRouter as Router\nrouter = Router()",
        "import fastapi\nrouter = fastapi.FastAPI()",
        "import fastapi as fa\nrouter = fa.APIRouter()",
        "from fastapi import APIRouter\nrouter: APIRouter = APIRouter()",
        "from fastapi import APIRouter\nrouter = APIRouter()\nrouter: APIRouter",
    ],
)
def test_parser_discovers_known_route_owners(tmp_path: Path, setup: str) -> None:
    module = tmp_path / "api.py"
    source = (
        setup
        + """
@router.get("/users/{user_id}")
async def read_user(user_id: int):
    return {"user_id": user_id}
"""
    )
    module.write_text(source, encoding="utf-8")

    result = FastAPIRouteParser().parse_file(module)

    assert result.error is None
    assert len(result.routes) == 1
    assert result.routes[0].path == "/users/{user_id}"
    assert result.routes[0].methods == ("GET",)
    assert result.routes[0].function == "read_user"
    assert result.routes[0].file == module
    assert (
        result.routes[0].line == source.splitlines().index("async def read_user(user_id: int):") + 1
    )


@pytest.mark.parametrize(
    "setup",
    [
        "router = object()",
        "router = APIRouter()",
        "def APIRouter(): pass\nrouter = APIRouter()",
        "class APIRouter: pass\nrouter = APIRouter()",
        "from unrelated import APIRouter\nrouter = APIRouter()",
        "from .fastapi import APIRouter\nrouter = APIRouter()",
        "from . import fastapi\nrouter = fastapi.APIRouter()",
        "from fastapi import APIRouter\nrouter: APIRouter",
        "from fastapi import APIRouter\noriginal = APIRouter()\nrouter = original",
        "from fastapi import APIRouter\ndef factory(): return APIRouter()\nrouter = factory()",
        "class Namespace:\n    from fastapi import APIRouter\nrouter = APIRouter()",
        "if enabled:\n    from fastapi import APIRouter\nrouter = APIRouter()",
    ],
)
def test_parser_skips_unknown_owners(tmp_path: Path, setup: str) -> None:
    module = tmp_path / "api.py"
    module.write_text(setup + '\n@router.get("/unknown")\ndef endpoint(): pass\n')

    result = FastAPIRouteParser().parse_file(module)

    assert result.error is None
    assert result.routes == ()


@pytest.mark.parametrize(
    "body",
    [
        "router = APIRouter()\nrouter = object()",
        "router = APIRouter()\ndel router",
        "APIRouter = object\nrouter = APIRouter()",
        "del APIRouter\nrouter = APIRouter()",
        "import fastapi\nfastapi = object()\nrouter = fastapi.APIRouter()",
        "import fastapi\ndel fastapi\nrouter = fastapi.APIRouter()",
        "if enabled:\n    router = APIRouter()",
        "router = APIRouter()\nif enabled:\n    router = object()",
        "router = APIRouter()\nfor router in candidates:\n    pass",
        "router = APIRouter()\ntry:\n    router = object()\nexcept Exception:\n    pass",
        "router = APIRouter()\nclass Namespace:\n    global router\n    router = object()",
        "router = APIRouter()\nimport unrelated as router",
        "from unrelated import APIRouter\nrouter = APIRouter()",
    ],
)
def test_parser_invalidates_rebound_or_conditional_owners(tmp_path: Path, body: str) -> None:
    module = tmp_path / "api.py"
    module.write_text(
        "from fastapi import APIRouter\n"
        + body
        + '\n@router.get("/unknown")\ndef endpoint(): pass\n'
    )

    result = FastAPIRouteParser().parse_file(module)

    assert result.error is None
    assert result.routes == ()


@pytest.mark.parametrize(
    ("source", "paths"),
    [
        (
            """
            from fastapi import APIRouter
            def configure():
                router = APIRouter()
                @router.post("/local")
                def endpoint(): pass
            """,
            ["/local"],
        ),
        (
            """
            def configure():
                import fastapi as fa
                router = fa.APIRouter()
                @router.post("/local")
                def endpoint(): pass
            """,
            ["/local"],
        ),
        (
            """
            from fastapi import APIRouter
            router = APIRouter()
            def configure(router):
                @router.get("/parameter")
                def endpoint(): pass
            """,
            [],
        ),
        (
            """
            from fastapi import APIRouter
            router = APIRouter()
            def configure():
                @router.get("/unbound")
                def endpoint(): pass
                router = object()
            """,
            [],
        ),
        (
            """
            from fastapi import APIRouter
            def configure():
                router = APIRouter()
                @router.get("/unbound")
                def endpoint(): pass
                APIRouter = object
            """,
            [],
        ),
        (
            """
            from fastapi import APIRouter
            def configure(APIRouter):
                router = APIRouter()
                @router.get("/parameter")
                def endpoint(): pass
            """,
            [],
        ),
        (
            """
            from fastapi import APIRouter
            router = APIRouter()
            def configure():
                @router.get("/rebound-outer")
                def endpoint(): pass
            router = object()
            """,
            [],
        ),
        (
            """
            from fastapi import APIRouter
            def configure():
                router = APIRouter()
                @router.get("/rebound-constructor")
                def endpoint(): pass
            APIRouter = object
            """,
            [],
        ),
        (
            """
            from fastapi import APIRouter
            class Namespace:
                APIRouter = object
            router = APIRouter()
            @router.get("/module")
            def endpoint(): pass
            """,
            ["/module"],
        ),
        (
            """
            from fastapi import APIRouter
            def configure():
                router = APIRouter()
            @router.get("/leaked-local")
            def endpoint(): pass
            """,
            [],
        ),
        (
            """
            from fastapi import APIRouter
            router = APIRouter()
            if enabled:
                @router.get("/conditional")
                def endpoint(): pass
            """,
            [],
        ),
        (
            """
            from fastapi import APIRouter
            router = APIRouter()
            @decorate(router := object())
            @router.get("/ambiguous-decorator")
            def endpoint(): pass
            @router.get("/rebound-by-decorator")
            def later_endpoint(): pass
            """,
            [],
        ),
    ],
)
def test_parser_respects_lexical_scopes(tmp_path: Path, source: str, paths: list[str]) -> None:
    module = tmp_path / "api.py"
    module.write_text(dedent(source), encoding="utf-8")

    result = FastAPIRouteParser().parse_file(module)

    assert result.error is None
    assert [route.path for route in result.routes] == paths


def test_parser_only_accepts_supported_decorators(tmp_path: Path) -> None:
    module = tmp_path / "api.py"
    module.write_text(
        dedent("""
        from fastapi import FastAPI
        app = FastAPI()
        cache = object()
        @cache.get("/cache")
        def cache_entry(): pass
        @app.GET("/uppercase")
        def uppercase(): pass
        @app.get(path="/keyword")
        def keyword(): pass
        @app.api_route("/generic", methods=["GET"])
        def generic(): pass
        @app.get(dynamic_path)
        def dynamic(): pass
        @app.get("/supported")
        @app.post("/supported")
        def supported(): pass
        """),
        encoding="utf-8",
    )

    result = FastAPIRouteParser().parse_file(module)

    assert result.error is None
    assert [(route.path, route.methods) for route in result.routes] == [
        ("/supported", ("GET",)),
        ("/supported", ("POST",)),
    ]


def test_parser_never_executes_or_imports_target_source(tmp_path: Path) -> None:
    sentinel = tmp_path / "executed.txt"
    module = tmp_path / "api.py"
    module.write_text(
        "from pathlib import Path\n"
        f"Path({str(sentinel)!r}).write_text('target executed')\n"
        "import missing_target_dependency\n"
        "from fastapi import FastAPI\n"
        "app = FastAPI()\n"
        '@app.get("/source-only")\ndef endpoint(): pass\n',
        encoding="utf-8",
    )

    result = FastAPIRouteParser().parse_file(module)

    assert result.error is None
    assert [route.path for route in result.routes] == ["/source-only"]
    assert not sentinel.exists()
