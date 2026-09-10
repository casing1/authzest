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


@pytest.mark.parametrize(
    "signature_and_body",
    [
        "def endpoint(Depends=Depends(current_user)): pass",
        "def endpoint(user=Depends(current_user)):\n    Depends = object()",
        "def endpoint(user=Depends(current_user)):\n    from unrelated import Depends",
    ],
)
def test_handler_locals_do_not_shadow_the_enclosing_default_expression(
    tmp_path: Path, signature_and_body: str
) -> None:
    write_sources(
        tmp_path,
        {
            "main.py": (
                "from fastapi import FastAPI, Depends\n"
                "app = FastAPI()\n"
                '@app.get("/users")\n' + signature_and_body + "\n"
            ),
        },
    )

    report = ScanRunner().run(tmp_path)

    assert report.diagnostics == ()
    assert len(report.routes) == 1
    assert len(report.routes[0].dependencies) == 1
    assert report.routes[0].dependencies[0].target == "current_user"
    assert report.routes[0].dependencies[0].resolution == "reference"


@pytest.mark.parametrize(
    "shadow",
    [
        "Depends = object()",
        "from unrelated import Depends",
        "del Depends",
    ],
)
def test_containing_function_local_writes_shadow_outer_dependency_aliases(
    tmp_path: Path, shadow: str
) -> None:
    write_sources(
        tmp_path,
        {
            "main.py": (
                "from fastapi import FastAPI, Depends\n"
                "app = FastAPI()\n"
                "def configure():\n"
                '    @app.get("/users")\n'
                "    def endpoint(user=Depends(current_user)): pass\n"
                f"    {shadow}\n"
            ),
        },
    )

    report = ScanRunner().run(tmp_path)

    assert len(report.routes) == 1
    assert report.routes[0].dependencies == ()
    assert report.routes[0].registration is not None
    assert report.routes[0].registration.execution_scope == "deferred"


@pytest.mark.parametrize(
    ("imports", "mutation", "expression"),
    [
        ("from fastapi import Depends", "Depends = replacement", "Depends(current_user)"),
        ("import fastapi as fa", "fa.Depends = replacement", "fa.Depends(current_user)"),
        ("import fastapi as fa", "fa = replacement", "fa.Depends(current_user)"),
        ("from unrelated import Depends", "", "Depends(current_user)"),
        ("import unrelated as fa", "", "fa.Depends(current_user)"),
    ],
)
def test_shadowed_or_unrelated_dependency_lookalikes_are_not_fastapi_evidence(
    tmp_path: Path, imports: str, mutation: str, expression: str
) -> None:
    write_sources(
        tmp_path,
        {
            "main.py": (
                "from fastapi import FastAPI\n"
                f"{imports}\napp = FastAPI()\n{mutation}\n"
                '@app.get("/users")\n'
                f"def endpoint(user={expression}): pass\n"
            ),
        },
    )

    report = ScanRunner().run(tmp_path)

    assert len(report.routes) == 1
    assert report.routes[0].dependencies == ()
    assert report.diagnostics == ()


@pytest.mark.parametrize(
    ("imports", "annotation"),
    [
        ("from typing import Annotated as A", "A[str, Depends(current_user)]"),
        ("from typing_extensions import Annotated as A", "A[str, Depends(current_user)]"),
        ("import typing as t", "t.Annotated[str, Depends(current_user)]"),
        ("import typing_extensions as t", "t.Annotated[str, Depends(current_user)]"),
    ],
)
def test_annotated_import_aliases_keep_parameter_evidence(
    tmp_path: Path, imports: str, annotation: str
) -> None:
    write_sources(
        tmp_path,
        {
            "main.py": (
                "from fastapi import FastAPI, Depends\n"
                f"{imports}\napp = FastAPI()\n"
                '@app.get("/users")\n'
                f"def endpoint(user: {annotation}): pass\n"
            ),
        },
    )

    report = ScanRunner().run(tmp_path)
    evidence = report.routes[0].dependencies[0]

    assert report.diagnostics == ()
    assert evidence.declaration_level == "parameter-annotation"
    assert evidence.parameter == "user"
    assert evidence.target == "current_user"


@pytest.mark.parametrize(
    ("imports", "mutation", "annotation"),
    [
        ("from typing import Annotated as A", "A = replacement", "A[str, Depends(user)]"),
        ("import typing as t", "t.Annotated = replacement", "t.Annotated[str, Depends(user)]"),
        ("from unrelated import Annotated", "", "Annotated[str, Depends(user)]"),
    ],
)
def test_shadowed_annotation_wrappers_are_not_assumed_to_be_typing_annotated(
    tmp_path: Path, imports: str, mutation: str, annotation: str
) -> None:
    write_sources(
        tmp_path,
        {
            "main.py": (
                "from fastapi import FastAPI, Depends\n"
                f"{imports}\napp = FastAPI()\n{mutation}\n"
                '@app.get("/users")\n'
                f"def endpoint(user: {annotation}): pass\n"
            ),
        },
    )

    report = ScanRunner().run(tmp_path)

    assert len(report.routes) == 1
    assert report.routes[0].dependencies == ()


def test_type_aliases_with_dependency_metadata_are_not_silently_expanded(tmp_path: Path) -> None:
    write_sources(
        tmp_path,
        {
            "main.py": """
                from fastapi import FastAPI, Depends
                from typing import Annotated
                app = FastAPI()
                CurrentUser = Annotated[str, Depends(current_user)]
                @app.get("/users")
                def endpoint(user: CurrentUser): pass
                """,
        },
    )

    report = ScanRunner().run(tmp_path)

    assert len(report.routes) == 1
    assert report.routes[0].dependencies == ()
    assert report.analysis_status == "partial"
    assert report.diagnostics
    assert all(item.location.file == tmp_path / "main.py" for item in report.diagnostics)


@pytest.mark.parametrize(
    "header",
    [
        "def first(user: Annotated[str, (Depends := replacement)]): pass",
        "def first() -> (Depends := replacement): pass",
    ],
)
def test_annotation_assignments_invalidate_following_dependency_bindings(
    tmp_path: Path, header: str
) -> None:
    write_sources(
        tmp_path,
        {
            "main.py": (
                "from fastapi import FastAPI, Depends\n"
                "from typing import Annotated\n"
                "app = FastAPI()\n"
                '@app.get("/first")\n'
                f"{header}\n"
                '@app.get("/second")\n'
                "def second(user=Depends(current_user)): pass\n"
            ),
        },
    )

    report = ScanRunner().run(tmp_path)

    assert [route.path for route in report.routes] == ["/second"]
    assert report.routes[0].dependencies == ()
    assert [item.code for item in report.diagnostics] == ["unsupported-route-expression"]
    assert report.analysis_status == "partial"


def test_nested_dependency_bearing_type_is_diagnosed_without_expansion(tmp_path: Path) -> None:
    write_sources(
        tmp_path,
        {
            "main.py": """
                from fastapi import FastAPI, Depends
                from typing import Annotated
                app = FastAPI()
                @app.get("/users")
                def endpoint(user: Annotated[Annotated[str, Depends(current_user)], "note"]): pass
                """,
        },
    )

    report = ScanRunner().run(tmp_path)

    assert len(report.routes) == 1
    assert report.routes[0].dependencies == ()
    assert [item.code for item in report.diagnostics] == ["unsupported-dependency-annotation"]
    assert report.analysis_status == "partial"


def test_empty_annotated_tuple_does_not_crash_source_inventory(tmp_path: Path) -> None:
    write_sources(
        tmp_path,
        {
            "main.py": """
                from fastapi import FastAPI
                from typing import Annotated
                app = FastAPI()
                @app.get("/users")
                def endpoint(user: Annotated[()]): pass
                """,
        },
    )

    report = ScanRunner().run(tmp_path)

    assert report.parse_errors == ()
    assert len(report.routes) == 1
    assert report.routes[0].dependencies == ()


@pytest.mark.parametrize("module_name", ["typing", "typing_extensions"])
def test_repository_local_annotation_modules_do_not_impersonate_known_markers(
    tmp_path: Path, module_name: str
) -> None:
    write_sources(
        tmp_path,
        {
            f"{module_name}.py": "Annotated = unrelated\n",
            "main.py": (
                "from fastapi import FastAPI, Depends\n"
                f"from {module_name} import Annotated\n"
                "app = FastAPI()\n"
                '@app.get("/users")\n'
                "def endpoint(user: Annotated[str, Depends(current_user)]): pass\n"
            ),
        },
    )

    report = ScanRunner().run(tmp_path)

    assert len(report.routes) == 1
    assert report.routes[0].dependencies == ()


def test_parameter_default_alignment_handles_positional_only_and_required_keywords(
    tmp_path: Path,
) -> None:
    write_sources(
        tmp_path,
        {
            "main.py": """
                from fastapi import FastAPI, Depends
                app = FastAPI()
                @app.get("/users")
                def endpoint(required, user=Depends(current_user), /, *, required_kw,
                             ordinary=None, auditor=Depends(policies.audit)): pass
                """,
        },
    )

    report = ScanRunner().run(tmp_path)

    assert report.diagnostics == ()
    assert [(item.parameter, item.target) for item in report.routes[0].dependencies] == [
        ("user", "current_user"),
        ("auditor", "policies.audit"),
    ]


def test_generic_type_parameters_shadow_annotations_and_nested_bodies_only(tmp_path: Path) -> None:
    write_sources(
        tmp_path,
        {
            "main.py": """
                from fastapi import FastAPI, Depends
                from typing import Annotated
                app = FastAPI()
                @app.get("/generic", dependencies=[Depends(audit)])
                def generic[Depends](user: Annotated[str, Depends(annotation_provider)]
                                     = Depends(default_provider)): pass
                def configure[Depends]():
                    @app.get("/nested")
                    def nested(user=Depends(nested_provider)): pass
                @app.get("/after")
                def after(user=Depends(module_provider)): pass
                """,
        },
    )

    report = ScanRunner().run(tmp_path)
    generic, nested, after = report.routes

    assert report.diagnostics == ()
    assert [(item.target, item.declaration_level) for item in generic.dependencies] == [
        ("audit", "decorator"),
        ("default_provider", "parameter-default"),
    ]
    assert nested.dependencies == ()
    assert nested.registration is not None
    assert nested.registration.execution_scope == "deferred"
    assert [item.target for item in after.dependencies] == ["module_provider"]


def test_dependency_coordinates_use_utf8_bytes_not_character_indices(tmp_path: Path) -> None:
    source = (
        "from fastapi import FastAPI, Depends\n"
        "app = FastAPI()\n"
        '@app.get("/users")\n'
        "def endpoint(사용자=Depends(policies.current_user)): pass\n"
    )
    write_sources(tmp_path, {"main.py": source})

    evidence = ScanRunner().run(tmp_path).routes[0].dependencies[0]
    expected_column = len("def endpoint(사용자=".encode()) + 1

    assert evidence.location.file == tmp_path / "main.py"
    assert evidence.location.line == 4
    assert evidence.location.column == expected_column
    assert evidence.parameter == "사용자"
    assert evidence.target == "policies.current_user"


def test_reference_targets_do_not_assert_existence_or_callability(tmp_path: Path) -> None:
    write_sources(
        tmp_path,
        {
            "main.py": """
                from fastapi import FastAPI, Depends
                app = FastAPI()
                not_callable = 42
                @app.get("/users", dependencies=[Depends(unknown.guard)])
                def endpoint(user=Depends(not_callable)): pass
                """,
        },
    )

    report = ScanRunner().run(tmp_path)
    evidence = report.routes[0].dependencies

    assert report.diagnostics == ()
    assert {item.target for item in evidence} == {"unknown.guard", "not_callable"}
    assert all(item.resolution == "reference" for item in evidence)


def test_repeated_cross_file_mounts_preserve_dependency_sources_without_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sources = {
        "api/__init__.py": "raise RuntimeError('source must not be imported')\n",
        "api/users.py": """
            from fastapi import APIRouter, Depends, Security
            from .policy import current_user
            router = APIRouter()
            @router.get("/users", dependencies=[Security(policy.audit, scopes=["read"])])
            def endpoint(user=Depends(current_user)): pass
            raise RuntimeError('source must not be executed')
            """,
        "api/policy.py": """
            raise RuntimeError('dependency source must not be imported')
            def current_user():
                raise RuntimeError('dependency callable must not run')
            """,
        "main.py": """
            from fastapi import FastAPI
            from api.users import router
            app = FastAPI()
            app.include_router(router, prefix="/v1")
            app.include_router(router, prefix="/v1")
            """,
    }
    first_root, second_root = tmp_path / "first", tmp_path / "second"
    write_sources(first_root, sources)
    write_sources(second_root, sources)
    reads: Counter[Path] = Counter()
    original_read_bytes = Path.read_bytes

    def count_read(path: Path) -> bytes:
        reads[path] += 1
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", count_read)

    first = ScanRunner().run(first_root)
    second = ScanRunner().run(second_root)
    routes = first.to_dict()["routes"]

    assert first.diagnostics == second.diagnostics == ()
    assert routes == second.to_dict()["routes"]
    assert len(routes) == 2
    assert routes[0]["registration_id"] != routes[1]["registration_id"]
    assert routes[0]["dependencies"] == routes[1]["dependencies"]
    assert {item["location"]["file"] for item in routes[0]["dependencies"]} == {"api/users.py"}
    assert len(routes[0]["dependencies"]) == 2
    assert len(reads) == 8
    assert set(reads.values()) == {1}
