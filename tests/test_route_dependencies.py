from pathlib import Path
from textwrap import dedent

import pytest

from authzest.models import ScanReport
from authzest.parser import FastAPIRouteParser
from authzest.runner import ScanRunner


def scan_source(tmp_path: Path, source: str) -> ScanReport:
    (tmp_path / "main.py").write_text(dedent(source).lstrip("\n"), encoding="utf-8")
    return ScanRunner().run(tmp_path)


def scan_default(tmp_path: Path, default: str) -> ScanReport:
    return scan_source(
        tmp_path,
        "from fastapi import FastAPI, Depends, Security\n"
        "app = FastAPI()\n"
        '@app.get("/items")\n'
        f"def endpoint(user={default}): pass\n",
    )


@pytest.mark.parametrize(
    ("imports", "expression", "kind", "target"),
    [
        ("from fastapi import Depends", "Depends(load)", "Depends", "load"),
        ("from fastapi import Depends as D", "D(dependency=auth.load)", "Depends", "auth.load"),
        ("import fastapi", "fastapi.Depends(load)", "Depends", "load"),
        ("import fastapi as fa", "fa.Depends(auth.load)", "Depends", "auth.load"),
        ("from fastapi import Security", "Security(load)", "Security", "load"),
        ("from fastapi import Security as S", "S(dependency=auth.load)", "Security", "auth.load"),
        ("import fastapi", "fastapi.Security(load)", "Security", "load"),
        ("import fastapi as fa", "fa.Security(auth.load)", "Security", "auth.load"),
    ],
)
def test_known_fastapi_factory_imports_and_aliases(
    tmp_path: Path, imports: str, expression: str, kind: str, target: str
) -> None:
    report = scan_source(
        tmp_path,
        f"from fastapi import FastAPI\n{imports}\napp = FastAPI()\n"
        '@app.get("/items")\n'
        f"def endpoint(user={expression}): pass\n",
    )

    assert report.analysis_status == "bounded"
    assert report.diagnostics == ()
    evidence = report.routes[0].dependencies[0]
    assert evidence.kind == kind
    assert evidence.target == target
    assert evidence.parameter == "user"
    assert evidence.declaration_level == "parameter-default"
    assert evidence.resolution == "reference"
    assert evidence.unresolved_reasons == ()


def test_each_supported_declaration_keeps_source_order_and_parameter_context(
    tmp_path: Path,
) -> None:
    report = scan_source(
        tmp_path,
        """
        from fastapi import FastAPI, Depends, Security
        from typing import Annotated
        app = FastAPI()
        @app.get("/items", dependencies=[Security(auth.audit, scopes=["read"]), Depends(log)])
        async def endpoint(user: Annotated[str, Depends(auth.load)], other=Depends(extra)): pass
        """,
    )

    evidence = report.routes[0].dependencies
    assert report.diagnostics == ()
    assert [
        (item.kind, item.target, item.declaration_level, item.parameter) for item in evidence
    ] == [
        ("Security", "auth.audit", "decorator", None),
        ("Depends", "log", "decorator", None),
        ("Depends", "auth.load", "parameter-annotation", "user"),
        ("Depends", "extra", "parameter-default", "other"),
    ]
    assert [(item.location.line, item.location.column) for item in evidence] == sorted(
        (item.location.line, item.location.column) for item in evidence
    )
    assert evidence[0].scopes == ("read",)


@pytest.mark.parametrize(
    ("suffix", "expected", "partial"),
    [
        ("", (), False),
        (", scopes=None", (), False),
        (", scopes=[]", (), False),
        (', scopes=["read", "write", "read"]', ("read", "write", "read"), False),
        (", scopes=SCOPES", None, True),
        (', scopes=("read",)', None, True),
        (", scopes=[1]", None, True),
        (', scopes=["read", *extra]', None, True),
        (', scopes=[f"{scope}"]', None, True),
        (", scopes=[name for name in names]", None, True),
        (', scopes=["read"], scopes=[]', None, True),
        (", **options", None, True),
    ],
)
def test_security_scopes_distinguish_known_empty_from_unknown(
    tmp_path: Path, suffix: str, expected: tuple[str, ...] | None, partial: bool
) -> None:
    report = scan_default(tmp_path, f"Security(load{suffix})")
    evidence = report.routes[0].dependencies[0]

    assert evidence.scopes == expected
    assert (report.analysis_status == "partial") is partial
    assert (evidence.resolution == "unresolved") is partial
    assert ("dynamic-security-scopes" in evidence.unresolved_reasons) is partial
    assert ("dynamic-security-scopes" in {item.code for item in report.diagnostics}) is partial


@pytest.mark.parametrize(
    ("expression", "target"),
    [
        ("Depends()", None),
        ("Depends(None)", None),
        ("Depends(dependency=None)", None),
        ("Depends(factory())", "factory()"),
        ('Depends(registry["load"])', "registry['load']"),
        ("Depends(lambda: load)", "lambda: load"),
        ("Depends(3)", "3"),
        ("Depends(factory().load)", "factory().load"),
        ("Depends(*targets)", None),
        ("Depends(**options)", None),
    ],
)
def test_implicit_dynamic_and_expanded_targets_remain_unresolved(
    tmp_path: Path, expression: str, target: str | None
) -> None:
    report = scan_default(tmp_path, expression)
    evidence = report.routes[0].dependencies[0]

    assert len(report.routes) == 1
    assert report.analysis_status == "partial"
    assert evidence.target == target
    assert evidence.resolution == "unresolved"
    assert evidence.scopes is None
    assert "unresolved-dependency-target" in evidence.unresolved_reasons
    assert "unresolved-dependency-target" in {item.code for item in report.diagnostics}
    assert all(item.location == evidence.location for item in report.diagnostics)


@pytest.mark.parametrize(
    "expression",
    [
        "Depends(load, other)",
        "Depends(load, dependency=other)",
        "Depends(dependency=load, dependency=other)",
        "Depends(load, use_cache=True, use_cache=False)",
        "Depends(load, unknown=True)",
        'Security(load, scope="request")',
    ],
)
def test_unsupported_arguments_do_not_claim_a_resolved_declaration(
    tmp_path: Path, expression: str
) -> None:
    report = scan_default(tmp_path, expression)
    evidence = report.routes[0].dependencies[0]

    assert report.analysis_status == "partial"
    assert evidence.resolution == "unresolved"
    assert "unsupported-dependency-arguments" in evidence.unresolved_reasons
    assert "unsupported-dependency-arguments" in {item.code for item in report.diagnostics}


@pytest.mark.parametrize(
    "expression",
    [
        "Depends(load, use_cache=cache_option)",
        "Depends(load, scope=scope_option)",
        "Security(load, use_cache=cache_option)",
    ],
)
def test_known_noncollected_options_do_not_infer_runtime_semantics(
    tmp_path: Path, expression: str
) -> None:
    report = scan_default(tmp_path, expression)

    assert report.diagnostics == ()
    assert report.routes[0].dependencies[0].resolution == "reference"


@pytest.mark.parametrize(
    ("value", "code", "targets"),
    [
        ("configured", "unsupported-dependency-list", []),
        ("make_dependencies()", "unsupported-dependency-list", []),
        ("(Depends(load),)", "unsupported-dependency-list", []),
        ("[Depends(load) for item in items]", "unsupported-dependency-list", []),
        ("[Depends(load), *extra]", "unsupported-dependency-entry", ["load"]),
        ("[Depends(load), unknown]", "unsupported-dependency-entry", ["load"]),
        ("[ordinary(load)]", "unsupported-dependency-entry", []),
        ("[Depends]", "unsupported-dependency-entry", []),
        ("[None]", "unsupported-dependency-entry", []),
    ],
)
def test_unsupported_decorator_dependencies_keep_known_routes_and_literal_entries(
    tmp_path: Path, value: str, code: str, targets: list[str]
) -> None:
    report = scan_source(
        tmp_path,
        "from fastapi import FastAPI, Depends\napp = FastAPI()\n"
        f'@app.get("/items", dependencies={value})\n'
        "def endpoint(): pass\n",
    )

    assert len(report.routes) == 1
    assert report.analysis_status == "partial"
    assert [item.target for item in report.routes[0].dependencies] == targets
    assert code in {item.code for item in report.diagnostics}


@pytest.mark.parametrize("value", ["None", "[]"])
def test_explicitly_empty_decorator_dependencies_are_bounded(tmp_path: Path, value: str) -> None:
    report = scan_source(
        tmp_path,
        "from fastapi import FastAPI\napp = FastAPI()\n"
        f'@app.get("/items", dependencies={value})\n'
        "def endpoint(): pass\n",
    )

    assert report.diagnostics == ()
    assert report.routes[0].dependencies == ()


def test_duplicate_decorator_dependency_arguments_are_ambiguous(tmp_path: Path) -> None:
    report = scan_source(
        tmp_path,
        """
        from fastapi import FastAPI, Depends
        app = FastAPI()
        @app.get("/items", dependencies=[Depends(first)], dependencies=[Depends(second)])
        def endpoint(): pass
        """,
    )

    assert report.analysis_status == "partial"
    assert [item.target for item in report.routes[0].dependencies] == ["first", "second"]
    assert all(item.resolution == "unresolved" for item in report.routes[0].dependencies)
    assert all(
        "unsupported-dependency-list" in item.unresolved_reasons
        for item in report.routes[0].dependencies
    )


@pytest.mark.parametrize(
    ("signature", "code"),
    [
        ("user=wrapper(Depends(load))", "unsupported-dependency-expression"),
        ("user: Annotated[str, wrapper(Depends(load))]", "unsupported-dependency-metadata"),
        ("user: Annotated[str, Depends]", "unsupported-dependency-metadata"),
        ("user: list[Annotated[str, Depends(load)]]", "unsupported-dependency-annotation"),
        (
            "user: Annotated[Annotated[str, Depends(load)], 'meta']",
            "unsupported-dependency-annotation",
        ),
    ],
)
def test_known_nested_or_noncall_declarations_are_diagnosed_without_fabricated_evidence(
    tmp_path: Path, signature: str, code: str
) -> None:
    report = scan_source(
        tmp_path,
        "from fastapi import FastAPI, Depends\nfrom typing import Annotated\napp = FastAPI()\n"
        '@app.get("/items")\n'
        f"def endpoint({signature}): pass\n",
    )

    assert len(report.routes) == 1
    assert report.routes[0].dependencies == ()
    assert report.analysis_status == "partial"
    assert code in {item.code for item in report.diagnostics}


@pytest.mark.parametrize(
    "annotation",
    [
        "str",
        "list[str]",
        "Annotated[str, 'description']",
        "Annotated[Depends(load), 'metadata']",
        '"Annotated[str, Depends(load)]"',
    ],
)
def test_ordinary_and_stringized_annotations_do_not_create_dependency_evidence(
    tmp_path: Path, annotation: str
) -> None:
    report = scan_source(
        tmp_path,
        "from fastapi import FastAPI, Depends\nfrom typing import Annotated\napp = FastAPI()\n"
        '@app.get("/items")\n'
        f"def endpoint(user: {annotation}): pass\n",
    )

    assert report.diagnostics == ()
    assert report.routes[0].dependencies == ()


@pytest.mark.parametrize(
    "signature",
    [
        "user: Annotated[str, Depends(first)] = Depends(second)",
        "user: Annotated[str, Depends(first), Security(second)]",
    ],
)
def test_multiple_parameter_declarations_preserve_syntax_but_not_resolution(
    tmp_path: Path, signature: str
) -> None:
    report = scan_source(
        tmp_path,
        "from fastapi import FastAPI, Depends, Security\n"
        "from typing import Annotated\napp = FastAPI()\n"
        '@app.get("/items")\n'
        f"def endpoint({signature}): pass\n",
    )

    assert report.analysis_status == "partial"
    assert [item.target for item in report.routes[0].dependencies] == ["first", "second"]
    assert all(item.resolution == "unresolved" for item in report.routes[0].dependencies)
    assert all(
        "ambiguous-dependency-declaration" in item.unresolved_reasons
        for item in report.routes[0].dependencies
    )


@pytest.mark.parametrize(
    ("alias_declaration", "alias_use"),
    [
        ("CurrentUser = Annotated[str, Depends(load)]", "CurrentUser"),
        ("CurrentUser: TypeAlias = Annotated[str, Depends(load)]", "CurrentUser"),
        ("type CurrentUser = Annotated[str, Depends(load)]", "CurrentUser"),
        ("CurrentUser = Annotated[str, Depends(load)]\nAnotherUser = CurrentUser", "AnotherUser"),
    ],
)
def test_known_dependency_annotation_aliases_are_marked_but_not_expanded(
    tmp_path: Path, alias_declaration: str, alias_use: str
) -> None:
    report = scan_source(
        tmp_path,
        "from fastapi import FastAPI, Depends\nfrom typing import Annotated, TypeAlias\n"
        f"app = FastAPI()\n{alias_declaration}\n"
        '@app.get("/items")\n'
        f"def endpoint(user: {alias_use}): pass\n",
    )

    assert report.routes[0].dependencies == ()
    assert report.analysis_status == "partial"
    assert {item.code for item in report.diagnostics} == {"unsupported-dependency-annotation"}


def test_bounded_local_reexports_keep_factory_markers_and_annotation_alias_diagnostics(
    tmp_path: Path,
) -> None:
    (tmp_path / "declarations.py").write_text(
        "from fastapi import Depends as D\n"
        "from typing import Annotated as A\n"
        "User = A[str, D(load)]\n",
        encoding="utf-8",
    )
    report = scan_source(
        tmp_path,
        """
        from fastapi import FastAPI
        from declarations import D as Dependency
        import declarations as declarations_module
        app = FastAPI()
        @app.get("/items")
        def endpoint(user: declarations_module.User, audit=Dependency(log)): pass
        """,
    )

    assert [item.target for item in report.routes[0].dependencies] == ["log"]
    assert report.analysis_status == "partial"
    assert {item.code for item in report.diagnostics} == {"unsupported-dependency-annotation"}


def test_owner_and_include_dependencies_are_not_inherited_or_mislabelled_as_route_local(
    tmp_path: Path,
) -> None:
    report = scan_source(
        tmp_path,
        """
        from fastapi import FastAPI, APIRouter, Depends
        app = FastAPI(dependencies=[Depends(app_guard)])
        router = APIRouter(dependencies=[Depends(router_guard)])
        @router.get("/items", dependencies=[Depends(route_guard)])
        def endpoint(user=Depends(load)): pass
        app.include_router(router, dependencies=[Depends(include_guard)])
        """,
    )

    assert report.diagnostics == ()
    assert len(report.routes) == 1
    assert [item.target for item in report.routes[0].dependencies] == ["route_guard", "load"]
    assert report.routes[0].registration is not None
    assert len(report.routes[0].registration.include_chain) == 1


def test_nested_dependency_function_graph_is_not_collected_or_executed(tmp_path: Path) -> None:
    report = scan_source(
        tmp_path,
        """
        from fastapi import FastAPI, Depends
        app = FastAPI()
        def load(other=Depends(nested)):
            raise RuntimeError("never execute a dependency")
        @app.get("/items")
        def endpoint(user=Depends(load)): pass
        """,
    )

    assert report.diagnostics == ()
    assert [item.target for item in report.routes[0].dependencies] == ["load"]


def test_generic_type_parameter_does_not_mask_outer_default_or_decorator_scope(
    tmp_path: Path,
) -> None:
    report = scan_source(
        tmp_path,
        """
        from fastapi import FastAPI, Depends
        from typing import Annotated
        app = FastAPI()
        @app.get("/items", dependencies=[Depends(decorator_guard)])
        def endpoint[Depends](
            user: Annotated[str, Depends(annotation_guard)] = Depends(default_guard)
        ):
            @app.get("/nested")
            def nested(user=Depends(body_guard)): pass
        """,
    )

    assert report.diagnostics == ()
    assert len(report.routes) == 2
    assert [item.target for item in report.routes[0].dependencies] == [
        "decorator_guard",
        "default_guard",
    ]
    assert report.routes[1].dependencies == ()


def test_generic_alias_type_parameter_is_not_mistaken_for_an_imported_factory(
    tmp_path: Path,
) -> None:
    report = scan_source(
        tmp_path,
        """
        from fastapi import FastAPI, Depends
        from typing import Annotated
        app = FastAPI()
        type User[Depends] = Annotated[str, Depends(load)]
        @app.get("/items")
        def endpoint(user: User): pass
        """,
    )

    assert report.diagnostics == ()
    assert report.routes[0].dependencies == ()


def test_single_file_parser_uses_the_same_dependency_collection_contract(tmp_path: Path) -> None:
    report = scan_default(tmp_path, 'Security(load, scopes=["read"])')
    parsed = FastAPIRouteParser().parse_file(tmp_path / "main.py")

    assert parsed.error is None
    assert parsed.diagnostics == report.diagnostics == ()
    assert parsed.routes == report.routes
