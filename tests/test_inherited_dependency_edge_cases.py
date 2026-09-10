from collections import Counter
from pathlib import Path
from textwrap import dedent

import pytest

from authzest.runner import ScanRunner


def write_sources(root: Path, sources: dict[str, str]) -> None:
    for name, source in sources.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(dedent(source).lstrip("\n"), encoding="utf-8")


def test_cross_file_aliases_preserve_context_order_sources_and_read_once_without_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sources = {
        "api/__init__.py": "from .group import router as public_router\n",
        "api/users.py": """
            from fastapi import APIRouter, Depends, Security
            router = APIRouter(dependencies=[Depends(user_context)])
            @router.get("/users")
            def users(value=Security(local_context, scopes=["read"])): pass
            raise RuntimeError('target source must not be executed')
            """,
        "api/group.py": """
            import fastapi as fa
            from .users import router as users
            router = fa.APIRouter(dependencies=[fa.Depends(group_context)])
            router.include_router(users, dependencies=[fa.Depends(inner_mount)])
            raise RuntimeError('target module must not be imported')
            """,
        "main.py": """
            from fastapi import FastAPI, Depends
            from api import public_router as routes
            app = FastAPI(dependencies=[Depends(application_context)])
            app.include_router(routes, prefix="/api", dependencies=[Depends(outer_mount)])
            app.include_router(routes, prefix="/api", dependencies=[Depends(second_mount)])
            """,
    }
    first_root = tmp_path / "first"
    second_root = tmp_path / "nested" / "second"
    write_sources(first_root, sources)
    write_sources(second_root, sources)
    reads: Counter[Path] = Counter()
    original_read_bytes = Path.read_bytes

    def count_read(path: Path) -> bytes:
        reads[path] += 1
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", count_read)

    first_report = ScanRunner().run(first_root)
    second_report = ScanRunner().run(second_root)
    first, second = first_report.to_dict()["routes"]

    assert first_report.diagnostics == second_report.diagnostics == ()
    assert first_report.to_dict()["routes"] == second_report.to_dict()["routes"]
    assert first["path"] == second["path"] == "/api/users"
    assert first["registration_id"] != second["registration_id"]
    assert first["dependencies"] == second["dependencies"]
    assert [item["target"] for item in first["effective_dependencies"]] == [
        "application_context",
        "outer_mount",
        "group_context",
        "inner_mount",
        "user_context",
        "local_context",
    ]
    assert [item["target"] for item in second["effective_dependencies"]] == [
        "application_context",
        "second_mount",
        "group_context",
        "inner_mount",
        "user_context",
        "local_context",
    ]
    assert [item["declaration_level"] for item in first["effective_dependencies"]] == [
        "application",
        "include",
        "router",
        "include",
        "router",
        "parameter-default",
    ]
    assert [
        (item["location"]["file"], item["location"]["line"])
        for item in first["effective_dependencies"]
    ] == [
        ("main.py", 3),
        ("main.py", 4),
        ("api/group.py", 3),
        ("api/group.py", 4),
        ("api/users.py", 2),
        ("api/users.py", 4),
    ]
    assert first["dependencies"] == [first["effective_dependencies"][-1]]
    assert len(reads) == 8
    assert set(reads.values()) == {1}


def test_owner_evidence_uses_constructor_bindings_not_later_include_bindings(
    tmp_path: Path,
) -> None:
    write_sources(
        tmp_path,
        {
            "main.py": """
                from fastapi import FastAPI, APIRouter, Depends as D
                router = APIRouter(dependencies=[D(constructor_provider)])
                @router.get("/users")
                def users(): pass
                D = replacement
                app = FastAPI()
                app.include_router(router, dependencies=[D(unknown_mount_provider)])
                """,
        },
    )

    report = ScanRunner().run(tmp_path)

    assert len(report.routes) == 1
    route = report.routes[0]
    assert route.dependencies == ()
    assert [item.target for item in route.effective_dependencies] == ["constructor_provider"]
    assert route.effective_dependencies[0].declaration_level == "router"
    assert route.effective_dependencies[0].location.line == 2
    assert report.analysis_status == "partial"
    assert any(item.location.line == 7 for item in report.diagnostics)


def test_dependency_factory_imported_after_constructor_does_not_rewrite_owner_evidence(
    tmp_path: Path,
) -> None:
    write_sources(
        tmp_path,
        {
            "main.py": """
                from fastapi import FastAPI, APIRouter
                from unrelated import Depends as D
                router = APIRouter(dependencies=[D(unknown_constructor_provider)])
                @router.get("/users")
                def users(): pass
                from fastapi import Depends as D
                app = FastAPI()
                app.include_router(router, dependencies=[D(mount_provider)])
                """,
        },
    )

    report = ScanRunner().run(tmp_path)

    assert len(report.routes) == 1
    assert [item.target for item in report.routes[0].effective_dependencies] == ["mount_provider"]
    assert report.routes[0].effective_dependencies[0].declaration_level == "include"
    assert report.analysis_status == "partial"
    assert any(item.location.line == 3 for item in report.diagnostics)


def test_deferred_owner_clone_retains_original_constructor_evidence(tmp_path: Path) -> None:
    write_sources(
        tmp_path,
        {
            "main.py": """
                from fastapi import APIRouter, Depends
                router = APIRouter(dependencies=[Depends(router_context)])
                def configure():
                    @router.get("/later")
                    def later(value=Depends(local_context)): pass
                """,
        },
    )

    report = ScanRunner().run(tmp_path)
    route = report.routes[0]

    assert report.diagnostics == ()
    assert route.registration is not None
    assert route.registration.execution_scope == "deferred"
    assert [item.target for item in route.effective_dependencies] == [
        "router_context",
        "local_context",
    ]
    assert route.inherited_dependencies[0].location.line == 2
    assert route.dependencies[0].location.line == 5


def test_deferred_local_factory_composes_its_own_context_without_runtime_claims(
    tmp_path: Path,
) -> None:
    write_sources(
        tmp_path,
        {
            "main.py": """
                from fastapi import FastAPI, APIRouter, Depends
                def create_app():
                    router = APIRouter(dependencies=[Depends(router_context)])
                    @router.get("/later")
                    def later(value=Depends(local_context)): pass
                    app = FastAPI(dependencies=[Depends(application_context)])
                    app.include_router(router, dependencies=[Depends(mount_context)])
                    return app
                """,
        },
    )

    report = ScanRunner().run(tmp_path)
    route = report.routes[0]

    assert report.diagnostics == ()
    assert route.registration is not None
    assert route.registration.execution_scope == "deferred"
    assert [item.target for item in route.effective_dependencies] == [
        "application_context",
        "mount_context",
        "router_context",
        "local_context",
    ]
    assert len(route.dependencies) == 1


def test_rejected_cycle_does_not_inject_its_dependency_into_a_valid_mount(tmp_path: Path) -> None:
    write_sources(
        tmp_path,
        {
            "main.py": """
                from fastapi import FastAPI, APIRouter, Depends
                first = APIRouter(dependencies=[Depends(first_context)])
                second = APIRouter(dependencies=[Depends(second_context)])
                @first.get("/users")
                def users(value=Depends(local_context)): pass
                second.include_router(first, dependencies=[Depends(inner_context)])
                first.include_router(second, dependencies=[Depends(rejected_cycle_context)])
                app = FastAPI(dependencies=[Depends(application_context)])
                app.include_router(second, dependencies=[Depends(outer_context)])
                """,
        },
    )

    report = ScanRunner().run(tmp_path)

    assert len(report.routes) == 1
    assert [item.code for item in report.diagnostics] == ["include-cycle"]
    assert [item.target for item in report.routes[0].effective_dependencies] == [
        "application_context",
        "outer_context",
        "second_context",
        "inner_context",
        "first_context",
        "local_context",
    ]
    assert report.analysis_status == "partial"
