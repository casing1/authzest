from pathlib import Path
from textwrap import dedent

import pytest

from authzest.models import Route, ScanReport
from authzest.runner import ScanRunner


def scan_source(tmp_path: Path, source: str) -> ScanReport:
    (tmp_path / "main.py").write_text(dedent(source).lstrip("\n"), encoding="utf-8")
    return ScanRunner().run(tmp_path)


def targets(route: Route) -> list[str | None]:
    return [item.target for item in route.effective_dependencies]


@pytest.mark.parametrize(
    ("constructor", "level"), [("FastAPI", "application"), ("APIRouter", "router")]
)
def test_direct_routes_inherit_owner_declarations_without_changing_local_evidence(
    tmp_path: Path, constructor: str, level: str
) -> None:
    report = scan_source(
        tmp_path,
        "from fastapi import FastAPI, APIRouter, Depends, Security\n"
        f'owner = {constructor}(dependencies=[Security(owner_guard, scopes=["read"])])\n'
        '@owner.get("/items", dependencies=[Depends(route_guard)])\n'
        "def endpoint(user=Depends(load)): pass\n",
    )
    route = report.routes[0]

    assert report.diagnostics == ()
    assert [item.target for item in route.dependencies] == ["route_guard", "load"]
    assert targets(route) == ["owner_guard", "route_guard", "load"]
    assert [item.declaration_level for item in route.effective_dependencies] == [
        level,
        "decorator",
        "parameter-default",
    ]
    inherited = route.inherited_dependencies[0]
    assert inherited.scopes == ("read",)
    assert inherited.parameter is None
    assert inherited.location.line == 2


def test_nested_mounts_preserve_context_sequence_not_global_source_order(tmp_path: Path) -> None:
    report = scan_source(
        tmp_path,
        """
        from fastapi import FastAPI, APIRouter, Depends
        child = APIRouter(prefix="/child", dependencies=[Depends(child_guard)])
        @child.get("/items", dependencies=[Depends(route_guard)])
        def endpoint(user=Depends(load)): pass
        parent = APIRouter(prefix="/parent", dependencies=[Depends(parent_guard)])
        parent.include_router(child, dependencies=[Depends(inner_mount)])
        app = FastAPI(dependencies=[Depends(app_guard)])
        app.include_router(parent, prefix="/v1", dependencies=[Depends(outer_mount)])
        """,
    )
    route = report.routes[0]

    assert report.diagnostics == ()
    assert route.path == "/v1/parent/child/items"
    assert targets(route) == [
        "app_guard",
        "outer_mount",
        "parent_guard",
        "inner_mount",
        "child_guard",
        "route_guard",
        "load",
    ]
    assert [item.declaration_level for item in route.effective_dependencies] == [
        "application",
        "include",
        "router",
        "include",
        "router",
        "decorator",
        "parameter-default",
    ]
    assert [item.location.line for item in route.effective_dependencies] == [7, 8, 5, 6, 2, 3, 4]
    assert [item.target for item in route.dependencies] == ["route_guard", "load"]


def test_repeated_mounts_keep_distinct_include_contexts_and_original_route_dependencies(
    tmp_path: Path,
) -> None:
    report = scan_source(
        tmp_path,
        """
        from fastapi import FastAPI, APIRouter, Depends
        router = APIRouter(dependencies=[Depends(router_guard)])
        @router.get("/items")
        def endpoint(user=Depends(load)): pass
        app = FastAPI(dependencies=[Depends(app_guard)])
        app.include_router(router, dependencies=[Depends(first_mount)])
        app.include_router(router, dependencies=[Depends(second_mount)])
        """,
    )
    first, second = report.routes

    assert report.diagnostics == ()
    assert first.path == second.path == "/items"
    assert first.to_dict()["registration_id"] != second.to_dict()["registration_id"]
    assert targets(first) == ["app_guard", "first_mount", "router_guard", "load"]
    assert targets(second) == ["app_guard", "second_mount", "router_guard", "load"]
    assert first.dependencies == second.dependencies
    assert first.inherited_dependencies[1].location.line == 6
    assert second.inherited_dependencies[1].location.line == 7
    assert first.inherited_dependencies[2] == second.inherited_dependencies[2]


def test_multiple_applications_do_not_leak_application_or_mount_dependencies(
    tmp_path: Path,
) -> None:
    report = scan_source(
        tmp_path,
        """
        from fastapi import FastAPI, APIRouter, Depends, Security
        router = APIRouter(dependencies=[Depends(router_guard)])
        @router.get("/items")
        def endpoint(): pass
        first = FastAPI(dependencies=[Depends(first_app)])
        second = FastAPI(dependencies=[Depends(second_app)])
        first.include_router(router, dependencies=[Security(guard, scopes=["read"])])
        second.include_router(router, dependencies=[Security(guard, scopes=["write"])])
        """,
    )
    first, second = report.routes

    assert report.diagnostics == ()
    assert targets(first) == ["first_app", "guard", "router_guard"]
    assert targets(second) == ["second_app", "guard", "router_guard"]
    assert first.effective_dependencies[1].scopes == ("read",)
    assert second.effective_dependencies[1].scopes == ("write",)
    assert first.dependencies == second.dependencies == ()


def test_repeated_equal_references_are_not_deduplicated_across_declaration_levels(
    tmp_path: Path,
) -> None:
    report = scan_source(
        tmp_path,
        """
        from fastapi import FastAPI, APIRouter, Depends
        app = FastAPI(dependencies=[Depends(guard), Depends(guard)])
        router = APIRouter(dependencies=[Depends(guard)])
        @router.get("/items", dependencies=[Depends(guard)])
        def endpoint(user=Depends(guard)): pass
        app.include_router(router, dependencies=[Depends(guard)])
        """,
    )
    route = report.routes[0]

    assert report.diagnostics == ()
    assert targets(route) == ["guard"] * 6
    assert len(route.inherited_dependencies) == 4
    assert len({item.location for item in route.effective_dependencies}) == 6
    assert (
        route.effective_dependencies[0].location.line
        == route.effective_dependencies[1].location.line
    )
    assert (
        route.effective_dependencies[0].location.column
        != route.effective_dependencies[1].location.column
    )


def test_parent_direct_route_and_mounted_child_get_only_their_own_inherited_contexts(
    tmp_path: Path,
) -> None:
    report = scan_source(
        tmp_path,
        """
        from fastapi import FastAPI, APIRouter, Depends
        parent = APIRouter(dependencies=[Depends(parent_guard)])
        @parent.get("/parent")
        def parent_route(): pass
        child = APIRouter(dependencies=[Depends(child_guard)])
        @child.get("/child")
        def child_route(): pass
        parent.include_router(child, dependencies=[Depends(inner_mount)])
        app = FastAPI(dependencies=[Depends(app_guard)])
        app.include_router(parent, dependencies=[Depends(outer_mount)])
        """,
    )
    routes = {route.path: route for route in report.routes}

    assert report.diagnostics == ()
    assert targets(routes["/parent"]) == ["app_guard", "outer_mount", "parent_guard"]
    assert targets(routes["/child"]) == [
        "app_guard",
        "outer_mount",
        "parent_guard",
        "inner_mount",
        "child_guard",
    ]


@pytest.mark.parametrize("level", ["application", "router", "include"])
@pytest.mark.parametrize(
    ("value", "code", "known"),
    [
        ("configured", "unsupported-dependency-list", []),
        ("make_dependencies()", "unsupported-dependency-list", []),
        ("(Depends(known_guard),)", "unsupported-dependency-list", []),
        ("[Depends(known_guard), *extra]", "unsupported-dependency-entry", ["known_guard"]),
        ("[ordinary(known_guard)]", "unsupported-dependency-entry", []),
    ],
)
def test_unresolved_inherited_lists_retain_routes_and_any_known_literal_entries(
    tmp_path: Path, level: str, value: str, code: str, known: list[str]
) -> None:
    application = value if level == "application" else "[]"
    router = value if level == "router" else "[]"
    include = value if level == "include" else "[]"
    report = scan_source(
        tmp_path,
        "from fastapi import FastAPI, APIRouter, Depends\n"
        f"app = FastAPI(dependencies={application})\n"
        f"router = APIRouter(dependencies={router})\n"
        '@router.get("/items")\ndef endpoint(user=Depends(load)): pass\n'
        f"app.include_router(router, dependencies={include})\n",
    )
    route = report.routes[0]

    assert report.analysis_status == "partial"
    assert targets(route) == [*known, "load"]
    assert [item.declaration_level for item in route.inherited_dependencies] == [level] * len(known)
    assert code in {item.code for item in report.diagnostics}


@pytest.mark.parametrize("empty", ["None", "[]"])
def test_known_empty_inherited_dependency_lists_are_not_unknown(tmp_path: Path, empty: str) -> None:
    report = scan_source(
        tmp_path,
        "from fastapi import FastAPI, APIRouter\n"
        f"app = FastAPI(dependencies={empty})\nrouter = APIRouter(dependencies={empty})\n"
        '@router.get("/items")\ndef endpoint(): pass\n'
        f"app.include_router(router, dependencies={empty})\n",
    )

    assert report.diagnostics == ()
    assert report.routes[0].dependencies == ()
    assert report.routes[0].inherited_dependencies == ()
    assert report.routes[0].effective_dependencies == ()


@pytest.mark.parametrize("level", ["application", "router", "include"])
def test_repeated_inherited_dependencies_keywords_do_not_claim_resolved_declarations(
    tmp_path: Path, level: str
) -> None:
    repeated = "dependencies=[Depends(first)], dependencies=[Depends(second)]"
    app_arguments = repeated if level == "application" else ""
    router_arguments = repeated if level == "router" else ""
    include_arguments = ", " + repeated if level == "include" else ""
    report = scan_source(
        tmp_path,
        "from fastapi import FastAPI, APIRouter, Depends\n"
        f"app = FastAPI({app_arguments})\nrouter = APIRouter({router_arguments})\n"
        '@router.get("/items")\ndef endpoint(): pass\n'
        f"app.include_router(router{include_arguments})\n",
    )
    route = report.routes[0]

    assert report.analysis_status == "partial"
    assert targets(route) == ["first", "second"]
    assert all(item.declaration_level == level for item in route.effective_dependencies)
    assert all(item.resolution == "unresolved" for item in route.effective_dependencies)
    assert all(
        "unsupported-dependency-list" in item.unresolved_reasons
        for item in route.effective_dependencies
    )


def test_unresolved_targets_and_security_scopes_preserve_original_declaration_evidence(
    tmp_path: Path,
) -> None:
    report = scan_source(
        tmp_path,
        """
        from fastapi import FastAPI, APIRouter, Depends, Security
        app = FastAPI(dependencies=[Depends()])
        router = APIRouter(dependencies=[Security(router_guard, scopes=ROUTER_SCOPES)])
        @router.get("/items")
        def endpoint(): pass
        app.include_router(router, dependencies=[Depends(factory())])
        """,
    )
    route = report.routes[0]
    application, include, router = route.effective_dependencies

    assert report.analysis_status == "partial"
    assert application.target is None
    assert application.location.line == 2
    assert "unresolved-dependency-target" in application.unresolved_reasons
    assert include.target == "factory()"
    assert include.location.line == 6
    assert "unresolved-dependency-target" in include.unresolved_reasons
    assert router.target == "router_guard"
    assert router.scopes is None
    assert router.location.line == 3
    assert "dynamic-security-scopes" in router.unresolved_reasons
    assert {item.location for item in report.diagnostics} == {
        item.location for item in route.effective_dependencies
    }


def test_rejected_dynamic_include_prefix_does_not_emit_a_guessed_effective_route(
    tmp_path: Path,
) -> None:
    report = scan_source(
        tmp_path,
        """
        from fastapi import FastAPI, APIRouter, Depends
        app = FastAPI(dependencies=[Depends(app_guard)])
        router = APIRouter(dependencies=[Depends(router_guard)])
        @router.get("/items")
        def endpoint(): pass
        app.include_router(router, prefix=PREFIX, dependencies=[Depends(mount_guard)])
        """,
    )

    assert report.routes == ()
    assert report.analysis_status == "partial"
    assert "dynamic-include-prefix" in {item.code for item in report.diagnostics}
