from pathlib import Path
from textwrap import dedent

import pytest

from authzest.parser import FastAPIRouteParser
from authzest.runner import ScanRunner


def write_sources(root: Path, sources: dict[str, str]) -> None:
    for name, source in sources.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(dedent(source).lstrip("\n"), encoding="utf-8")


def test_direct_decorators_preserve_owner_and_exact_declaration(tmp_path: Path) -> None:
    write_sources(
        tmp_path,
        {
            "main.py": """
                from fastapi import FastAPI
                app = FastAPI()
                @app.get("/same")
                @app.get("/same")
                def endpoint(): pass
                """,
        },
    )

    report = ScanRunner().run(tmp_path)
    routes = report.to_dict()["routes"]

    assert report.diagnostics == ()
    assert report.analysis_status == "bounded"
    assert len({route["registration_id"] for route in routes}) == 2
    assert [route["line"] for route in routes] == [5, 5]
    assert [route["registration"]["declaration"]["line"] for route in routes] == [3, 4]
    for route in routes:
        evidence = route["registration"]
        assert evidence["declaration"]["column"] == 2
        assert (
            evidence["owner"]
            == evidence["application"]
            == {
                "kind": "FastAPI",
                "location": {"file": "main.py", "line": 2, "column": 7},
            }
        )
        assert evidence["include_chain"] == []
        assert evidence["execution_scope"] == "module"


def test_repeated_mounts_and_applications_have_distinct_stable_ids(tmp_path: Path) -> None:
    source = """
        from fastapi import APIRouter, FastAPI
        router = APIRouter()
        @router.get("/items")
        def items(): pass
        first = FastAPI(); second = FastAPI()
        first.include_router(router); first.include_router(router)
        second.include_router(router)
        """
    first_root, second_root = tmp_path / "one", tmp_path / "two"
    for root in (first_root, second_root):
        write_sources(root, {"main.py": source})

    first = ScanRunner().run(first_root).to_dict()["routes"]
    repeat = ScanRunner().run(first_root).to_dict()["routes"]
    relocated = ScanRunner().run(second_root).to_dict()["routes"]

    assert first == repeat == relocated
    assert [route["path"] for route in first] == ["/items"] * 3
    assert len({route["registration_id"] for route in first}) == 3
    sites = [route["registration"]["include_chain"][0]["location"] for route in first]
    assert [site["line"] for site in sites] == [6, 6, 7]
    assert sites[0]["column"] != sites[1]["column"]
    applications = [route["registration"]["application"] for route in first]
    assert applications[0] == applications[1]
    assert applications[1] != applications[2]


def test_cross_file_nested_mounts_preserve_outer_to_inner_chain(tmp_path: Path) -> None:
    write_sources(
        tmp_path,
        {
            "users.py": """
                from fastapi import APIRouter
                router = APIRouter(prefix="/users")
                @router.get("/me")
                def me(): pass
                """,
            "group.py": """
                from fastapi import APIRouter
                from users import router as users
                router = APIRouter(prefix="/group")
                router.include_router(users, prefix="/members")
                """,
            "main.py": """
                from fastapi import FastAPI
                from group import router
                app = FastAPI()
                app.include_router(router, prefix="/v1")
                """,
        },
    )

    report = ScanRunner().run(tmp_path)
    route = report.to_dict()["routes"][0]
    registration = route["registration"]
    chain = registration["include_chain"]

    assert report.diagnostics == ()
    assert route["path"] == "/v1/group/members/users/me"
    assert registration["declaration"] == {"file": "users.py", "line": 3, "column": 2}
    assert registration["owner"]["location"]["file"] == "users.py"
    assert registration["application"]["location"]["file"] == "main.py"
    assert [site["location"]["file"] for site in chain] == ["main.py", "group.py"]
    assert [site["location"]["line"] for site in chain] == [4, 4]
    assert [site["prefix"] for site in chain] == ["/v1", "/members"]
    assert chain[0]["router"] == chain[1]["parent"]
    assert chain[1]["router"] == registration["owner"]


def test_deferred_inventory_preserves_original_owner_without_runtime_claim(tmp_path: Path) -> None:
    write_sources(
        tmp_path,
        {
            "main.py": """
                from fastapi import APIRouter
                router = APIRouter()
                def configure():
                    @router.get("/later")
                    def later(): pass
                """,
        },
    )

    report = ScanRunner().run(tmp_path)
    registration = report.to_dict()["routes"][0]["registration"]

    assert registration["execution_scope"] == "deferred"
    assert registration["application"] is None
    assert registration["owner"]["location"] == {"file": "main.py", "line": 2, "column": 10}
    assert registration["declaration"] == {"file": "main.py", "line": 4, "column": 6}


@pytest.mark.parametrize(
    ("statement", "code"),
    [
        ("app.include_router(router, prefix=PREFIX)", "dynamic-include-prefix"),
        ("app.include_router(router, **options)", "unsupported-include-arguments"),
        ("app.include_router(router, router)", "unsupported-include-arguments"),
        ("app.include_router(missing)", "unresolved-include-owner"),
        ("missing.include_router(router)", "unresolved-include-owner"),
        ("if enabled:\n    app.include_router(router)", "unsupported-include-context"),
        ("router.include_router(router)", "include-cycle"),
    ],
)
def test_known_unresolved_includes_have_source_diagnostics(
    tmp_path: Path, statement: str, code: str
) -> None:
    write_sources(
        tmp_path,
        {
            "main.py": (
                "from fastapi import FastAPI, APIRouter\n"
                "app = FastAPI()\nrouter = APIRouter()\n" + statement + "\n"
            ),
        },
    )

    report = ScanRunner().run(tmp_path)

    assert report.routes == ()
    assert report.parse_errors == ()
    assert report.analysis_status == "partial"
    assert len(report.diagnostics) == 1
    diagnostic = report.diagnostics[0]
    assert diagnostic.code == code
    assert diagnostic.severity == "warning"
    assert diagnostic.location.file == tmp_path / "main.py"
    assert diagnostic.location.line == (5 if statement.startswith("if") else 4)


@pytest.mark.parametrize(
    ("statement", "code"),
    [
        ("@app.get(PATH)\ndef endpoint(): pass", "dynamic-route-path"),
        ('@app.get(path="/items")\ndef endpoint(): pass', "unsupported-route-arguments"),
        ('@app.api_route("/items")\ndef endpoint(): pass', "unsupported-route-arguments"),
        (
            '@app.get("/items", tags=(value := []))\ndef endpoint(): pass',
            "unsupported-route-expression",
        ),
        (
            'if enabled:\n    @app.get("/items")\n    def endpoint(): pass',
            "conditional-registration",
        ),
    ],
)
def test_known_unresolved_routes_have_source_diagnostics(
    tmp_path: Path, statement: str, code: str
) -> None:
    write_sources(
        tmp_path,
        {"main.py": "from fastapi import FastAPI\napp = FastAPI()\n" + statement + "\n"},
    )

    result = FastAPIRouteParser().parse_file(tmp_path / "main.py")

    assert result.routes == ()
    assert result.error is None
    assert len(result.diagnostics) == 1
    assert result.diagnostics[0].code == code


def test_unknown_receivers_do_not_generate_framework_diagnostics(tmp_path: Path) -> None:
    write_sources(
        tmp_path,
        {"main.py": "@client.get(PATH)\ndef endpoint(): pass\nclient.include_router(value)\n"},
    )

    report = ScanRunner().run(tmp_path)

    assert report.routes == ()
    assert report.diagnostics == ()
    assert report.analysis_status == "bounded"


def test_dynamic_owner_constructor_is_not_silently_complete(tmp_path: Path) -> None:
    write_sources(
        tmp_path,
        {"main.py": "from fastapi import APIRouter\nrouter = APIRouter(prefix=PREFIX)\n"},
    )

    report = ScanRunner().run(tmp_path)

    assert [diagnostic.code for diagnostic in report.diagnostics] == [
        "unsupported-owner-construction"
    ]
    assert report.diagnostics[0].location.line == 2


def test_parse_error_keeps_legacy_text_and_structured_location(tmp_path: Path) -> None:
    write_sources(tmp_path, {"broken.py": "def broken(:\n"})
    path = tmp_path / "broken.py"

    direct = FastAPIRouteParser().parse_file(path)
    report = ScanRunner().run(tmp_path)

    assert report.parse_errors == (direct.error,)
    assert report.diagnostics == direct.diagnostics
    assert report.diagnostics[0].code == "source-parse-error"
    assert report.diagnostics[0].severity == "error"
    assert report.diagnostics[0].location.file == path
    assert report.diagnostics[0].location.line == 1
    assert report.diagnostics[0].location.column == 12
    assert report.analysis_status == "partial"


def test_unreadable_source_has_unknown_position_and_is_read_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_sources(tmp_path, {"main.py": "pass\n"})
    path = tmp_path / "main.py"
    reads: list[Path] = []

    def unreadable(source: Path) -> bytes:
        reads.append(source)
        raise PermissionError("fixture read denied")

    monkeypatch.setattr(Path, "read_bytes", unreadable)

    report = ScanRunner().run(tmp_path)

    assert reads == [path]
    assert report.parse_errors == (f"{path}: fixture read denied",)
    diagnostic = report.diagnostics[0]
    assert diagnostic.code == "source-read-error"
    assert diagnostic.location.line is None
    assert diagnostic.location.column is None


def test_columns_are_utf8_offsets_not_character_offsets(tmp_path: Path) -> None:
    write_sources(
        tmp_path,
        {
            "main.py": (
                "from fastapi import FastAPI\n한글 = 1; app = FastAPI()\n"
                '@app.get("/")\ndef root(): pass\n'
            ),
        },
    )

    report = ScanRunner().run(tmp_path)
    evidence = report.to_dict()["routes"][0]["registration"]

    assert evidence["owner"]["location"]["column"] == len("한글 = 1; app = ".encode()) + 1


def test_import_cycle_reports_the_known_unresolved_include_not_guessed_mount(
    tmp_path: Path,
) -> None:
    write_sources(
        tmp_path,
        {
            "router.py": """
                import group
                from fastapi import APIRouter
                router = APIRouter()
                @router.get("/items")
                def items(): pass
                """,
            "group.py": "from router import router\n",
            "main.py": """
                from fastapi import FastAPI
                from group import router
                app = FastAPI()
                app.include_router(router, prefix="/unknown")
                """,
        },
    )

    first = ScanRunner().run(tmp_path)
    second = ScanRunner().run(tmp_path)

    assert first == second
    assert [route.path for route in first.routes] == ["/items"]
    assert [diagnostic.code for diagnostic in first.diagnostics] == ["unresolved-include-owner"]
    assert first.diagnostics[0].location.file == tmp_path / "main.py"
    assert first.diagnostics[0].location.line == 4


def test_router_composition_cycle_preserves_diagnostic_site(tmp_path: Path) -> None:
    write_sources(
        tmp_path,
        {
            "main.py": """
                from fastapi import APIRouter
                first = APIRouter()
                second = APIRouter()
                first.include_router(second)
                second.include_router(first)
                """,
        },
    )

    report = ScanRunner().run(tmp_path)

    assert [diagnostic.code for diagnostic in report.diagnostics] == ["include-cycle"]
    assert report.diagnostics[0].location.line == 5


def test_local_sources_are_only_parsed_and_each_read_once_with_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_sources(
        tmp_path,
        {
            "router.py": """
                from fastapi import APIRouter
                raise RuntimeError("The target source must never execute")
                router = APIRouter()
                @router.get("/items")
                def items(): pass
                """,
            "main.py": """
                from fastapi import FastAPI
                from router import router
                app = FastAPI()
                app.include_router(router)
                app.include_router(router)
                """,
        },
    )
    original_read = Path.read_bytes
    reads: list[Path] = []

    def counted_read(path: Path) -> bytes:
        reads.append(path)
        return original_read(path)

    monkeypatch.setattr(Path, "read_bytes", counted_read)

    report = ScanRunner().run(tmp_path)

    assert sorted(reads) == [tmp_path / "main.py", tmp_path / "router.py"]
    assert [route.path for route in report.routes] == ["/items", "/items"]
    assert all(route.registration is not None for route in report.routes)
