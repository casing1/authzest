from pathlib import Path
from textwrap import dedent

import pytest
from fastapi import APIRouter, FastAPI

from authzest.models import Route
from authzest.parser import FastAPIRouteParser


def parse_routes(tmp_path: Path, source: str) -> tuple[Route, ...]:
    module = tmp_path / "api.py"
    module.write_text(dedent(source), encoding="utf-8")
    result = FastAPIRouteParser().parse_file(module)
    assert result.error is None
    return result.routes


def test_composed_paths_match_an_independently_constructed_app(tmp_path: Path) -> None:
    routes = parse_routes(
        tmp_path,
        """
        from fastapi import APIRouter, FastAPI
        app = FastAPI()
        users = APIRouter(prefix="/users")
        @users.get("/me")
        def read_me(): pass
        @users.post("/{user_id}")
        def update_user(user_id: int): pass
        app.include_router(users, prefix="/api")
        """,
    )

    # Build a trusted fixture separately: never execute or import the parsed source.
    app = FastAPI()
    users = APIRouter(prefix="/users")

    @users.get("/me")
    def read_me() -> None:
        pass

    @users.post("/{user_id}")
    def update_user(user_id: int) -> None:
        pass

    app.include_router(users, prefix="/api")
    expected = {
        (path, method.upper())
        for path, operations in app.openapi()["paths"].items()
        for method in operations
    }

    assert {(route.path, route.methods[0]) for route in routes} == expected
    assert [route.function for route in routes] == ["read_me", "update_user"]
    assert all(route.file == tmp_path / "api.py" for route in routes)
    assert [route.line for route in routes] == [6, 8]


@pytest.mark.parametrize(
    ("router_prefix", "mount_prefix", "path", "expected"),
    [
        ("", "", "/health", "/health"),
        ("/users", "", "/me", "/users/me"),
        ("", "/api", "/me", "/api/me"),
        ("/users", "/api", "", "/api/users"),
        ("/users", "/api", "/", "/api/users/"),
        ("/users", "/api//v1", "/me", "/api//v1/users/me"),
    ],
)
def test_literal_prefixes_are_concatenated_without_normalization(
    tmp_path: Path, router_prefix: str, mount_prefix: str, path: str, expected: str
) -> None:
    routes = parse_routes(
        tmp_path,
        f"""
        from fastapi import APIRouter, FastAPI
        app = FastAPI()
        router = APIRouter(prefix={router_prefix!r})
        @router.get({path!r})
        def endpoint(): pass
        app.include_router(router, prefix={mount_prefix!r})
        """,
    )

    assert [route.path for route in routes] == [expected]


def test_repeated_registrations_preserve_each_mounted_path(tmp_path: Path) -> None:
    routes = parse_routes(
        tmp_path,
        """
        from fastapi import APIRouter, FastAPI
        app = FastAPI()
        router = APIRouter(prefix="/users")
        @router.get("/me")
        def endpoint(): pass
        app.include_router(router, prefix="/v1")
        app.include_router(router=router, prefix="/v2")
        """,
    )

    assert [route.path for route in routes] == ["/v1/users/me", "/v2/users/me"]
    assert routes[0].function == routes[1].function == "endpoint"
    assert routes[0].line == routes[1].line


def test_repeated_identical_registrations_are_not_deduplicated(tmp_path: Path) -> None:
    routes = parse_routes(
        tmp_path,
        """
        from fastapi import APIRouter, FastAPI
        app = FastAPI()
        router = APIRouter()
        @router.get("/me")
        def endpoint(): pass
        app.include_router(router, prefix="/api")
        app.include_router(router, prefix="/api")
        """,
    )

    assert [route.path for route in routes] == ["/api/me", "/api/me"]


def test_nested_routers_compose_constructor_and_registration_prefixes(tmp_path: Path) -> None:
    routes = parse_routes(
        tmp_path,
        """
        from fastapi import APIRouter, FastAPI
        app = FastAPI()
        parent = APIRouter(prefix="/parent")
        child = APIRouter(prefix="/child")
        @child.get("/item")
        def endpoint(): pass
        parent.include_router(child, prefix="/nested")
        app.include_router(parent, prefix="/api")
        """,
    )

    assert [route.path for route in routes] == ["/api/parent/nested/child/item"]


def test_unmounted_router_keeps_its_prefixed_declarations(tmp_path: Path) -> None:
    routes = parse_routes(
        tmp_path,
        """
        from fastapi import APIRouter
        router = APIRouter(prefix="/users")
        @router.get("/me")
        def endpoint(): pass
        """,
    )

    assert [route.path for route in routes] == ["/users/me"]


def test_class_local_include_does_not_suppress_an_outer_router(tmp_path: Path) -> None:
    routes = parse_routes(
        tmp_path,
        """
        from fastapi import APIRouter, FastAPI
        router = APIRouter(prefix="/outer")
        @router.get("/e")
        def endpoint(): pass
        class Namespace:
            app = FastAPI()
            router = APIRouter(prefix="/inner")
            @router.get("/ignored")
            def class_endpoint(): pass
            app.include_router(router, prefix="/class")
        """,
    )

    assert [route.path for route in routes] == ["/outer/e"]


@pytest.mark.parametrize("prefix", ["dynamic_prefix", 'f"/users"', "None", '"users"', '"/users/"'])
def test_unknown_or_invalid_constructor_prefixes_are_not_guessed(
    tmp_path: Path, prefix: str
) -> None:
    routes = parse_routes(
        tmp_path,
        f"""
        from fastapi import APIRouter, FastAPI
        app = FastAPI()
        router = APIRouter(prefix={prefix})
        @router.get("/me")
        def endpoint(): pass
        app.include_router(router, prefix="/api")
        """,
    )

    assert routes == ()


@pytest.mark.parametrize("prefix", ["dynamic_prefix", 'f"/api"', "None", '"api"', '"/api/"'])
def test_unknown_or_invalid_registration_does_not_fall_back_to_raw_paths(
    tmp_path: Path, prefix: str
) -> None:
    routes = parse_routes(
        tmp_path,
        f"""
        from fastapi import APIRouter, FastAPI
        app = FastAPI()
        router = APIRouter(prefix="/users")
        @router.get("/me")
        def endpoint(): pass
        app.include_router(router, prefix={prefix})
        """,
    )

    assert routes == ()


def test_known_mount_survives_an_additional_unknown_mount(tmp_path: Path) -> None:
    routes = parse_routes(
        tmp_path,
        """
        from fastapi import APIRouter, FastAPI
        app = FastAPI()
        router = APIRouter(prefix="/users")
        @router.get("/me")
        def endpoint(): pass
        app.include_router(router, prefix=dynamic_prefix)
        app.include_router(router, prefix="/api")
        """,
    )

    assert [route.path for route in routes] == ["/api/users/me"]


def test_conditional_mount_is_not_reported_as_a_raw_or_mounted_endpoint(tmp_path: Path) -> None:
    routes = parse_routes(
        tmp_path,
        """
        from fastapi import APIRouter, FastAPI
        app = FastAPI()
        router = APIRouter(prefix="/users")
        @router.get("/me")
        def endpoint(): pass
        if enabled:
            app.include_router(router, prefix="/api")
        """,
    )

    assert routes == ()


@pytest.mark.parametrize(
    ("constructor", "registration"),
    [
        ("APIRouter(**options)", 'app.include_router(router, prefix="/api")'),
        ('APIRouter(prefix="/users")', "app.include_router(router, **options)"),
    ],
)
def test_expanded_keyword_arguments_do_not_guess_a_prefix(
    tmp_path: Path, constructor: str, registration: str
) -> None:
    routes = parse_routes(
        tmp_path,
        f"""
        from fastapi import APIRouter, FastAPI
        app = FastAPI()
        router = {constructor}
        @router.get("/me")
        def endpoint(): pass
        {registration}
        """,
    )

    assert routes == ()


def test_constructor_aliases_and_function_local_mounts(tmp_path: Path) -> None:
    routes = parse_routes(
        tmp_path,
        """
        from fastapi import APIRouter as Router
        import fastapi as fa
        def create_app():
            app = fa.FastAPI()
            router = Router(prefix="/users")
            @router.get("/me")
            def endpoint(): pass
            app.include_router(router=router, prefix="/api")
            return app
        """,
    )

    assert [route.path for route in routes] == ["/api/users/me"]


def test_a_function_include_does_not_mutate_an_outer_router_graph(tmp_path: Path) -> None:
    routes = parse_routes(
        tmp_path,
        """
        from fastapi import APIRouter, FastAPI
        router = APIRouter(prefix="/users")
        @router.get("/me")
        def endpoint(): pass
        def configure():
            inner_app = FastAPI()
            inner_app.include_router(router, prefix="/deferred")
        app = FastAPI()
        app.include_router(router, prefix="/api")
        """,
    )

    assert [route.path for route in routes] == ["/api/users/me"]


def test_including_into_an_inherited_app_is_outside_the_supported_subset(tmp_path: Path) -> None:
    routes = parse_routes(
        tmp_path,
        """
        from fastapi import APIRouter, FastAPI
        app = FastAPI()
        def configure():
            router = APIRouter(prefix="/users")
            @router.get("/me")
            def endpoint(): pass
            app.include_router(router, prefix="/api")
        """,
    )

    assert routes == ()


def test_deferred_outer_router_decorators_do_not_leak_unmounted_paths(tmp_path: Path) -> None:
    routes = parse_routes(
        tmp_path,
        """
        from fastapi import APIRouter, FastAPI
        router = APIRouter(prefix="/users")
        @router.get("/early")
        def early(): pass
        def configure():
            @router.get("/deferred")
            def deferred(): pass
        app = FastAPI()
        app.include_router(router, prefix="/api")
        """,
    )

    assert [route.path for route in routes] == ["/api/users/early"]


def test_same_local_names_in_separate_factories_do_not_share_routes(tmp_path: Path) -> None:
    routes = parse_routes(
        tmp_path,
        """
        from fastapi import APIRouter, FastAPI
        def first_app():
            app = FastAPI()
            router = APIRouter(prefix="/first")
            @router.get("/one")
            def first(): pass
            app.include_router(router, prefix="/api")
        def second_app():
            app = FastAPI()
            router = APIRouter(prefix="/second")
            @router.get("/two")
            def second(): pass
            app.include_router(router, prefix="/api")
        """,
    )

    assert [(route.path, route.function) for route in routes] == [
        ("/api/first/one", "first"),
        ("/api/second/two", "second"),
    ]


def test_rebinding_a_name_does_not_rewrite_previous_registrations(tmp_path: Path) -> None:
    routes = parse_routes(
        tmp_path,
        """
        from fastapi import APIRouter, FastAPI
        app = FastAPI()
        router = APIRouter(prefix="/old")
        @router.get("/one")
        def first(): pass
        app.include_router(router, prefix="/v1")
        router = APIRouter(prefix="/new")
        @router.get("/two")
        def second(): pass
        app.include_router(router, prefix="/v2")
        """,
    )

    assert {(route.path, route.function) for route in routes} == {
        ("/v1/old/one", "first"),
        ("/v2/new/two", "second"),
    }


def test_chained_constructor_targets_share_one_registration_identity(tmp_path: Path) -> None:
    routes = parse_routes(
        tmp_path,
        """
        from fastapi import APIRouter, FastAPI
        app = FastAPI()
        router = same_router = APIRouter(prefix="/users")
        @router.get("/me")
        def endpoint(): pass
        app.include_router(same_router, prefix="/api")
        """,
    )

    assert [route.path for route in routes] == ["/api/users/me"]


def test_routes_declared_after_an_include_are_outside_the_supported_subset(tmp_path: Path) -> None:
    routes = parse_routes(
        tmp_path,
        """
        from fastapi import APIRouter, FastAPI
        app = FastAPI()
        router = APIRouter(prefix="/users")
        @router.get("/early")
        def early(): pass
        app.include_router(router, prefix="/api")
        @router.get("/late")
        def late(): pass
        """,
    )

    # This is a static support boundary, not an assumption about every FastAPI version.
    assert [route.path for route in routes] == ["/api/users/early"]


def test_prefix_resolution_does_not_execute_the_target(tmp_path: Path) -> None:
    sentinel = tmp_path / "executed.txt"
    routes = parse_routes(
        tmp_path,
        f"""
        from pathlib import Path
        Path({str(sentinel)!r}).write_text("target executed")
        import unavailable_target_dependency
        from fastapi import APIRouter, FastAPI
        app = FastAPI()
        router = APIRouter(prefix="/users")
        @router.get("/me")
        def endpoint(): pass
        app.include_router(router, prefix="/api")
        """,
    )

    assert [route.path for route in routes] == ["/api/users/me"]
    assert not sentinel.exists()
