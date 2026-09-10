from collections import Counter
from pathlib import Path
from textwrap import dedent

import pytest

from authzest.runner import ScanRunner

USER_ROUTES = """\
from fastapi import APIRouter
router = APIRouter(prefix="/users")
@router.get("/me")
def read_me(): pass
"""


def write_sources(root: Path, sources: dict[str, str]) -> None:
    for name, source in sources.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(dedent(source), encoding="utf-8")


@pytest.mark.parametrize(
    ("statement", "receiver"),
    [
        ("from users import router", "router"),
        ("from users import router as people", "people"),
        ("import users", "users.router"),
        ("import users as people", "people.router"),
    ],
)
def test_absolute_local_import_forms(tmp_path: Path, statement: str, receiver: str) -> None:
    write_sources(
        tmp_path,
        {
            "users.py": USER_ROUTES,
            "main.py": f"""
                from fastapi import FastAPI
                {statement}
                app = FastAPI()
                app.include_router({receiver}, prefix="/api")
                """,
        },
    )

    report = ScanRunner().run(tmp_path)

    assert report.parse_errors == ()
    assert report.python_files == 2
    assert [route.path for route in report.routes] == ["/api/users/me"]
    route = report.routes[0]
    assert (route.file, route.line, route.function, route.methods) == (
        tmp_path / "users.py",
        4,
        "read_me",
        ("GET",),
    )


@pytest.mark.parametrize("layout", ["", "src/"])
@pytest.mark.parametrize(
    ("statement", "receiver"),
    [
        ("from api.users import router as people", "people"),
        ("from api import users", "users.router"),
        ("from api import users as people", "people.router"),
        ("import api.users", "api.users.router"),
        ("import api.users as people", "people.router"),
        ("from .users import router", "router"),
        ("from . import users", "users.router"),
    ],
)
def test_package_import_forms_in_root_and_src_layouts(
    tmp_path: Path, layout: str, statement: str, receiver: str
) -> None:
    write_sources(
        tmp_path,
        {
            f"{layout}api/__init__.py": "",
            f"{layout}api/users.py": USER_ROUTES,
            f"{layout}api/main.py": f"""
                from fastapi import FastAPI
                {statement}
                app = FastAPI()
                app.include_router({receiver}, prefix="/api")
                """,
        },
    )

    report = ScanRunner().run(tmp_path)

    assert report.parse_errors == ()
    assert [route.path for route in report.routes] == ["/api/users/me"]
    assert report.routes[0].file == tmp_path / layout / "api/users.py"


def test_parent_relative_import_and_nested_mounts(tmp_path: Path) -> None:
    write_sources(
        tmp_path,
        {
            "api/__init__.py": "",
            "api/users.py": USER_ROUTES,
            "api/routes/__init__.py": "",
            "api/routes/group.py": """
                from fastapi import APIRouter
                from ..users import router as users
                router = APIRouter(prefix="/group")
                router.include_router(users, prefix="/members")
                """,
            "main.py": """
                from fastapi import FastAPI
                from api.routes import group
                app = FastAPI()
                app.include_router(group.router, prefix="/v1")
                app.include_router(group.router, prefix="/v2")
                """,
        },
    )

    report = ScanRunner().run(tmp_path)

    assert report.parse_errors == ()
    assert [route.path for route in report.routes] == [
        "/v1/group/members/users/me",
        "/v2/group/members/users/me",
    ]
    assert all(route.file == tmp_path / "api/users.py" for route in report.routes)
    assert all(route.line == 4 for route in report.routes)


@pytest.mark.parametrize(
    ("statement", "receiver"),
    [
        ("from api.routes import users", "users.router"),
        ("import api.routes.users", "api.routes.users.router"),
    ],
)
def test_namespace_package_routers_are_resolved_from_indexed_sources(
    tmp_path: Path, statement: str, receiver: str
) -> None:
    write_sources(
        tmp_path,
        {
            "api/routes/users.py": USER_ROUTES,
            "main.py": f"""
                from fastapi import FastAPI
                {statement}
                app = FastAPI()
                app.include_router({receiver}, prefix="/api")
                """,
        },
    )

    report = ScanRunner().run(tmp_path)

    assert report.parse_errors == ()
    assert report.python_files == 2
    assert [route.path for route in report.routes] == ["/api/users/me"]
    assert report.routes[0].file == tmp_path / "api/routes/users.py"


def test_package_initializers_can_reexport_imported_routers(tmp_path: Path) -> None:
    write_sources(
        tmp_path,
        {
            "api/routes/users.py": USER_ROUTES,
            "api/routes/__init__.py": "from .users import router as users_router\n",
            "api/__init__.py": "from .routes import users_router as public_router\n",
            "main.py": """
                from fastapi import FastAPI
                from api import public_router
                app = FastAPI()
                app.include_router(public_router, prefix="/api")
                """,
        },
    )

    report = ScanRunner().run(tmp_path)

    assert report.parse_errors == ()
    assert [route.path for route in report.routes] == ["/api/users/me"]
    assert report.routes[0].file == tmp_path / "api/routes/users.py"


@pytest.mark.parametrize(
    ("statement", "receiver"),
    [("from api import users", "users.router"), ("import api", "api.users.router")],
)
def test_package_initializer_can_reexport_a_module_using_a_relative_import(
    tmp_path: Path, statement: str, receiver: str
) -> None:
    write_sources(
        tmp_path,
        {
            "api/__init__.py": "from . import users\n",
            "api/users.py": USER_ROUTES,
            "main.py": f"""
                from fastapi import FastAPI
                {statement}
                app = FastAPI()
                app.include_router({receiver}, prefix="/api")
                """,
        },
    )

    report = ScanRunner().run(tmp_path)

    assert report.parse_errors == ()
    assert [route.path for route in report.routes] == ["/api/users/me"]
    assert report.routes[0].file == tmp_path / "api/users.py"


def test_unknown_package_attribute_does_not_fall_back_to_a_same_named_module(
    tmp_path: Path,
) -> None:
    write_sources(
        tmp_path,
        {
            "api/__init__.py": "users = object()\n",
            "api/users.py": USER_ROUTES,
            "main.py": """
                from fastapi import FastAPI
                from api import users
                app = FastAPI()
                app.include_router(users.router, prefix="/incorrect")
                """,
        },
    )

    report = ScanRunner().run(tmp_path)

    assert report.parse_errors == ()
    assert all(not route.path.startswith("/incorrect") for route in report.routes)


def test_repeated_identical_cross_file_mounts_remain_distinct(tmp_path: Path) -> None:
    write_sources(
        tmp_path,
        {
            "users.py": USER_ROUTES,
            "main.py": """
                from fastapi import FastAPI
                from users import router
                app = FastAPI()
                app.include_router(router, prefix="/api")
                app.include_router(router=router, prefix="/api")
                """,
        },
    )

    report = ScanRunner().run(tmp_path)

    assert [route.path for route in report.routes] == ["/api/users/me", "/api/users/me"]


def test_shared_modules_are_read_once_per_scan_and_refreshed_on_the_next_scan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_sources(
        tmp_path,
        {
            "users.py": USER_ROUTES,
            "z_app.py": """
                from fastapi import FastAPI
                import users
                app = FastAPI()
                app.include_router(users.router, prefix="/z")
                """,
            "a_app.py": """
                from fastapi import FastAPI
                from users import router
                app = FastAPI()
                app.include_router(router, prefix="/a")
                """,
        },
    )
    reads: Counter[Path] = Counter()
    read_bytes = Path.read_bytes

    def counted_read(path: Path) -> bytes:
        if path.suffix == ".py" and path.is_relative_to(tmp_path):
            reads[path] += 1
        return read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", counted_read)
    runner = ScanRunner()

    first = runner.run(tmp_path)
    second = runner.run(tmp_path)

    assert first == second
    assert {route.path for route in first.routes} == {"/a/users/me", "/z/users/me"}
    assert len(first.routes) == 2
    assert reads == Counter({tmp_path / name: 2 for name in ("users.py", "z_app.py", "a_app.py")})

    (tmp_path / "users.py").write_text(USER_ROUTES.replace('"/me"', '"/profile"'))
    refreshed = runner.run(tmp_path)
    assert {route.path for route in refreshed.routes} == {"/a/users/profile", "/z/users/profile"}


def test_report_order_does_not_depend_on_file_creation_order(tmp_path: Path) -> None:
    sources = {
        "z_users.py": USER_ROUTES,
        "m_app.py": """
            from fastapi import FastAPI
            from z_users import router
            app = FastAPI()
            app.include_router(router, prefix="/m")
            """,
        "a_app.py": """
            from fastapi import FastAPI
            from z_users import router
            app = FastAPI()
            app.include_router(router, prefix="/a")
            """,
    }
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    write_sources(first_root, sources)
    write_sources(second_root, dict(reversed(list(sources.items()))))

    first = ScanRunner().run(first_root).to_dict()
    second = ScanRunner().run(second_root).to_dict()

    assert first["routes"] == second["routes"]
    assert len(first["routes"]) == 2


@pytest.mark.parametrize(
    "registration",
    [
        "app.include_router(users.router, prefix=dynamic_prefix)",
        'if enabled:\n    app.include_router(users.router, prefix="/api")',
        "app.include_router(users.router, **options)",
    ],
)
def test_unresolved_cross_file_mount_does_not_emit_raw_declarations(
    tmp_path: Path, registration: str
) -> None:
    write_sources(
        tmp_path,
        {
            "users.py": USER_ROUTES,
            "main.py": "from fastapi import FastAPI\nimport users\napp = FastAPI()\n"
            + registration
            + "\n",
        },
    )

    assert ScanRunner().run(tmp_path).routes == ()


@pytest.mark.parametrize(
    ("statement", "receiver", "shadow"),
    [
        ("from users import router", "router", "router = object()"),
        ("import users", "users.router", "users = object()"),
        ("import users", "users.router", "users.router = object()"),
    ],
)
def test_reassigned_imports_are_not_used_as_router_owners(
    tmp_path: Path, statement: str, receiver: str, shadow: str
) -> None:
    write_sources(
        tmp_path,
        {
            "users.py": USER_ROUTES,
            "main.py": f"""
                from fastapi import FastAPI
                {statement}
                app = FastAPI()
                {shadow}
                app.include_router({receiver}, prefix="/incorrect")
                """,
        },
    )

    report = ScanRunner().run(tmp_path)

    assert all(not route.path.startswith("/incorrect") for route in report.routes)


@pytest.mark.parametrize(
    ("outer_import", "inner_import", "receiver"),
    [
        ("import users", "", "users.router"),
        ("from users import router", "", "router"),
        ("import users", "import users", "users.router"),
        ("from users import router", "from users import router", "router"),
    ],
)
def test_deferred_cross_file_mounts_cannot_mutate_the_module_registration_graph(
    tmp_path: Path, outer_import: str, inner_import: str, receiver: str
) -> None:
    write_sources(
        tmp_path,
        {
            "users.py": USER_ROUTES,
            "main.py": f"""
                from fastapi import FastAPI
                {outer_import}
                def configure():
                    {inner_import or "pass"}
                    inner = FastAPI()
                    inner.include_router({receiver}, prefix="/deferred")
                app = FastAPI()
                app.include_router({receiver}, prefix="/api")
                """,
        },
    )

    assert [route.path for route in ScanRunner().run(tmp_path).routes] == ["/api/users/me"]


@pytest.mark.parametrize(
    "source",
    [
        """
        import users
        def configure(users):
            @users.router.get("/incorrect")
            def endpoint(): pass
        """,
        """
        import users
        def configure():
            @users.router.get("/incorrect")
            def endpoint(): pass
            users = object()
        """,
        """
        import users
        def configure():
            @users.router.get("/incorrect")
            def endpoint(): pass
        users = object()
        """,
    ],
)
def test_shadowed_or_unstable_module_names_are_not_inherited_by_functions(
    tmp_path: Path, source: str
) -> None:
    write_sources(tmp_path, {"users.py": USER_ROUTES, "main.py": source})

    report = ScanRunner().run(tmp_path)

    assert [route.path for route in report.routes] == ["/users/me"]


@pytest.mark.parametrize(
    "candidates",
    [
        {"users.py": USER_ROUTES, "src/users.py": USER_ROUTES},
        {"users.py": USER_ROUTES, "users/__init__.py": USER_ROUTES},
    ],
)
def test_ambiguous_local_module_names_are_not_guessed(
    tmp_path: Path, candidates: dict[str, str]
) -> None:
    write_sources(
        tmp_path,
        {
            **candidates,
            "main.py": """
                from fastapi import FastAPI
                from users import router
                app = FastAPI()
                app.include_router(router, prefix="/incorrect")
                """,
        },
    )

    report = ScanRunner().run(tmp_path)

    assert report.parse_errors == ()
    assert all(not route.path.startswith("/incorrect") for route in report.routes)


def test_cyclic_imports_do_not_expose_partially_initialized_routers(tmp_path: Path) -> None:
    write_sources(
        tmp_path,
        {
            "users.py": "import group\n" + USER_ROUTES,
            "group.py": "from users import router\n",
            "main.py": """
                from fastapi import FastAPI
                from group import router
                app = FastAPI()
                app.include_router(router, prefix="/incorrect")
                """,
        },
    )

    report = ScanRunner().run(tmp_path)

    assert report.parse_errors == ()
    assert all(not route.path.startswith("/incorrect") for route in report.routes)


def test_local_fastapi_module_does_not_masquerade_as_the_framework(tmp_path: Path) -> None:
    write_sources(
        tmp_path,
        {
            "fastapi.py": """
                class FastAPI: pass
                class APIRouter: pass
                """,
            "users.py": USER_ROUTES,
            "main.py": """
                from fastapi import FastAPI
                from users import router
                app = FastAPI()
                @app.get("/incorrect")
                def endpoint(): pass
                app.include_router(router, prefix="/api")
                """,
        },
    )

    assert ScanRunner().run(tmp_path).routes == ()


def test_missing_external_imports_do_not_execute_any_target_source(tmp_path: Path) -> None:
    sentinel = tmp_path / "executed.txt"
    write_sources(
        tmp_path,
        {
            "users.py": f"from pathlib import Path\nPath({str(sentinel)!r}).touch()\n"
            "import unavailable_target_dependency\n" + USER_ROUTES,
            "main.py": """
                from fastapi import FastAPI
                from nonexistent_package import unknown_router
                from users import router
                app = FastAPI()
                app.include_router(unknown_router, prefix="/unknown")
                app.include_router(router, prefix="/api")
                """,
        },
    )

    report = ScanRunner().run(tmp_path)

    assert [route.path for route in report.routes] == ["/api/users/me"]
    assert report.parse_errors == ()
    assert not sentinel.exists()


@pytest.mark.parametrize("failure", ["syntax", "encoding", "read"])
def test_broken_imported_module_is_reported_once_and_other_files_are_scanned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    write_sources(
        tmp_path,
        {
            "broken.py": "this is not valid Python!!!\n" if failure == "syntax" else "",
            "users.py": USER_ROUTES,
            "main.py": """
                from fastapi import FastAPI
                from broken import router as broken_router
                import broken
                from users import router
                app = FastAPI()
                app.include_router(broken_router, prefix="/broken")
                app.include_router(router, prefix="/api")
                """,
        },
    )
    broken = tmp_path / "broken.py"
    if failure == "encoding":
        broken.write_bytes(b"\xff")
    if failure == "read":
        read_bytes = Path.read_bytes

        def unreadable(path: Path) -> bytes:
            if path == broken:
                raise PermissionError("unreadable fixture")
            return read_bytes(path)

        monkeypatch.setattr(Path, "read_bytes", unreadable)

    report = ScanRunner().run(tmp_path)

    assert [route.path for route in report.routes] == ["/api/users/me"]
    assert report.python_files == 3
    assert len(report.parse_errors) == 1
    assert "broken.py" in report.parse_errors[0]


@pytest.mark.parametrize("link_kind", ["file", "directory"])
def test_symlinks_cannot_read_python_sources_outside_the_scan_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, link_kind: str
) -> None:
    root = tmp_path / "repository"
    outside = tmp_path / "outside"
    write_sources(outside, {"__init__.py": "", "users.py": USER_ROUTES})
    write_sources(
        root,
        {
            "main.py": """
                from fastapi import FastAPI
                from users import router
                from external.users import router as external_router
                app = FastAPI()
                app.include_router(router, prefix="/incorrect")
                app.include_router(external_router, prefix="/incorrect")
                """,
        },
    )
    try:
        if link_kind == "file":
            (root / "users.py").symlink_to(outside / "users.py")
        else:
            (root / "external").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Symbolic link creation is unavailable on this platform")
    read_bytes = Path.read_bytes

    def confined_read(path: Path) -> bytes:
        assert path.resolve().is_relative_to(root), f"Read outside the scan root: {path}"
        return read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", confined_read)

    report = ScanRunner().run(root)

    assert report.python_files == 1
    assert report.routes == ()
    assert report.parse_errors == ()


def test_relative_imports_cannot_escape_the_scan_root(tmp_path: Path) -> None:
    root = tmp_path / "repository"
    write_sources(tmp_path, {"users.py": USER_ROUTES})
    write_sources(
        root,
        {
            "main.py": """
                from fastapi import FastAPI
                from ..users import router
                app = FastAPI()
                app.include_router(router, prefix="/incorrect")
                """,
        },
    )

    report = ScanRunner().run(root)

    assert report.python_files == 1
    assert report.routes == ()
