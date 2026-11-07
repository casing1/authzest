"""Pure static queries calculate syntax on varied sources, never reference labels."""

from __future__ import annotations

import builtins
import io
import socket
import subprocess
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from textwrap import dedent

import pytest
from scripts import evaluation_static_query as engine

from authzest.parser import FastAPIRouteParser

PREFIX = "from fastapi import APIRouter, Depends, FastAPI, Security\napp = FastAPI()\n"


def count(source: str, **extra: str) -> dict:
    return engine.evaluate_query(
        {"main.py": dedent(source), **extra}, engine.Query("source-http-declaration-count")
    )


def scopes(source: str, method: str = "GET", path: str = "/items") -> dict:
    return engine.evaluate_query(
        {"main.py": dedent(source)}, engine.Query("direct-security-scopes", method, path)
    )


def assert_unknown(result: dict, reason: str | None = None) -> None:
    assert set(result) == {"answer", "reason", "evidence"}
    assert result["answer"] is None
    assert result["reason"] in engine.REASONS
    assert result["evidence"] == []
    if reason:
        assert result["reason"] == reason


@pytest.mark.parametrize("number", [0, 1, 2, 4])
def test_source_declaration_count_is_computed_from_varied_owned_source(number):
    source = PREFIX + "\n".join(
        f'@app.get("/item/{index}")\ndef item_{index}(): pass\n' for index in range(number)
    )
    result = count(source)
    assert result["answer"] == str(number)
    assert result["reason"] == "complete-source-declarations"
    assert len(result["evidence"]) == number
    assert all(set(location) == {"file", "line", "column"} for location in result["evidence"])
    assert all(location["file"] == "main.py" for location in result["evidence"])


def test_empty_module_has_known_zero_decorators_not_unknown():
    assert count("")["answer"] == "0"


def test_all_virtual_modules_are_independent_and_keep_file_identity():
    one = PREFIX + '@app.get("/same")\ndef handler(): pass\n'
    result = count(one, **{"api/second.py": one})
    assert result["answer"] == "2"
    assert {entry["file"] for entry in result["evidence"]} == {"main.py", "api/second.py"}


def test_different_applications_with_identical_method_and_path_remain_distinct():
    result = count(
        PREFIX
        + 'other = FastAPI()\n@app.get("/same")\ndef first(): pass\n'
        + '@other.get("/same")\ndef second(): pass\n'
    )
    assert result["answer"] == "2"
    assert len({(entry["line"], entry["column"]) for entry in result["evidence"]}) == 2


def test_duplicate_router_includes_do_not_double_source_declaration_count():
    source = (
        PREFIX
        + 'router = APIRouter()\n@router.get("/item")\ndef item(): pass\n'
        + 'app.include_router(router, prefix="/one")\n'
        + 'app.include_router(router, prefix="/two")\n'
    )
    raw = FastAPIRouteParser().parse_source(source, Path("main.py"))
    assert len(raw.routes) == 2
    assert count(source)["answer"] == "1"


def test_deferred_factory_declaration_counts_without_claiming_execution():
    result = count(
        """
        from fastapi import FastAPI
        def make_app():
            service = FastAPI()
            @service.get("/later")
            def later(): pass
            return service
        """
    )
    assert result["answer"] == "1"
    assert result["evidence"] == [{"file": "main.py", "line": 5, "column": 6}]


@pytest.mark.parametrize(
    "suffix",
    [
        '@app.get(path="/items")\ndef item(): pass\n',
        '@app.api_route("/items", methods=["GET"])\ndef item(): pass\n',
        "@app.get(selected_path)\ndef item(): pass\n",
        '@app.get(f"/{name}")\ndef item(): pass\n',
        '@unknown.get("/items")\ndef item(): pass\n',
        "@decorate\ndef item(): pass\n",
        "@decorate()\ndef item(): pass\n",
        'route = app.get\n@route("/items")\ndef item(): pass\n',
        'if flag:\n    @app.get("/items")\n    def item(): pass\n',
        'for item in things:\n    @app.get("/items")\n    def handler(): pass\n',
        '@app.get("/items", **options)\ndef item(): pass\n',
        '@app.get("/items")\nclass Handler: pass\n',
    ],
)
def test_unsupported_or_incomplete_syntax_never_claims_a_complete_count(suffix):
    assert_unknown(count(PREFIX + suffix))


@pytest.mark.parametrize(
    "source",
    [
        "from fastapi import FastAPI as Application\napp=Application()\n"
        '@app.get("/")\ndef f(): pass',
        'import fastapi as fa\napp=fa.FastAPI()\n@app.get("/")\ndef f(): pass',
        'from fastapi import *\napp=FastAPI()\n@app.get("/")\ndef f(): pass',
    ],
)
def test_aliases_and_wildcard_imports_are_outside_the_query_subset(source):
    assert_unknown(count(source), "unsupported-alias")


@pytest.mark.parametrize("source", ["def broken(:", "(" * 300 + ")" * 300])
def test_parse_failures_are_unknown_not_zero(source):
    assert_unknown(count(source), "parse-error")


def test_missing_core_declaration_cannot_be_replaced_with_partial_len_routes(monkeypatch):
    original = FastAPIRouteParser.parse_source

    def omitted(self, source, path):
        result = original(self, source, path)
        return replace(result, routes=result.routes[:-1])

    monkeypatch.setattr(FastAPIRouteParser, "parse_source", omitted)
    source = PREFIX + '@app.get("/a")\ndef a(): pass\n@app.post("/b")\ndef b(): pass\n'
    assert_unknown(count(source), "incomplete-source-inventory")


def test_route_without_original_declaration_identity_is_unknown(monkeypatch):
    original = FastAPIRouteParser.parse_source

    def missing_identity(self, source, path):
        result = original(self, source, path)
        return replace(
            result, routes=tuple(replace(route, registration=None) for route in result.routes)
        )

    monkeypatch.setattr(FastAPIRouteParser, "parse_source", missing_identity)
    assert_unknown(count(PREFIX + '@app.get("/")\ndef f(): pass'), "incomplete-source-inventory")


@pytest.mark.parametrize(
    "values,expected", [([], ""), (["z", "a", "z"], "a,z"), (["write"], "write")]
)
def test_direct_literal_scopes_are_computed_sorted_and_deduplicated(values, expected):
    source = (
        PREFIX
        + f'@app.get("/items", dependencies=[Security(check, scopes={values!r})])\n'
        + "def items(): pass"
    )
    result = scopes(source)
    assert result["answer"] == expected
    assert result["reason"] == "complete-direct-scopes"
    assert result["evidence"] == [{"file": "main.py", "line": 3, "column": 2}]


def test_direct_scopes_merge_only_selected_decorator_and_parameter_defaults():
    source = (
        PREFIX
        + '@app.get("/items", dependencies=[Security(read, scopes=["get-only"])])\n'
        + '@app.post("/items", dependencies=[Security(write, scopes=["post-only"])])\n'
        + 'def items(context=Security(shared, scopes=["shared"])): pass\n'
    )
    assert scopes(source, "GET")["answer"] == "get-only,shared"
    assert scopes(source, "POST")["answer"] == "post-only,shared"


def test_ordinary_depends_does_not_invent_security_scopes_from_provider_signature():
    source = (
        PREFIX
        + 'def provider(principal=Security(auth, scopes=["hidden:read"])): pass\n'
        + '@app.get("/items")\ndef items(context=Depends(provider)): pass\n'
    )
    assert scopes(source)["answer"] == ""


@pytest.mark.parametrize(
    "binding,call",
    [
        ("Alias = Security", 'Alias(check, scopes=["hidden"])'),
        ("Security = object()", 'Security(check, scopes=["hidden"])'),
    ],
)
def test_assignment_alias_or_rebound_factory_cannot_become_known_empty_scopes(binding, call):
    source = PREFIX + binding + f'\n@app.get("/items")\ndef items(context={call}): pass\n'
    assert_unknown(scopes(source))


def test_inherited_constructor_and_include_security_are_not_direct_scopes():
    source = (
        "from fastapi import APIRouter, FastAPI, Security\n"
        'app=FastAPI(dependencies=[Security(auth, scopes=["application"])])\n'
        'router=APIRouter(dependencies=[Security(auth, scopes=["router"])])\n'
        '@router.get("/items")\ndef items(): pass\n'
        'app.include_router(router, dependencies=[Security(auth, scopes=["include"])])\n'
    )
    assert scopes(source)["answer"] == ""


@pytest.mark.parametrize(
    "call", ["Security(check)", "Security(check, scopes=[])", "Security(check, scopes=None)"]
)
def test_no_scopes_or_literal_empty_scopes_remain_known_empty(call):
    assert scopes(PREFIX + f'@app.get("/items")\ndef items(context={call}): pass')["answer"] == ""


@pytest.mark.parametrize(
    "values",
    [[""], ["a,b"], [" a"], ["a "], ["a\nb"], ["\x00"], ["\ud800"], ["x" * 513]],
)
def test_scope_csv_cannot_silently_lose_identity_or_exceed_answer_contract(values):
    source = (
        PREFIX + f'@app.get("/items")\ndef items(context=Security(check, scopes={values!r})): pass'
    )
    assert_unknown(scopes(source), "unrepresentable-scopes")


@pytest.mark.parametrize(
    "suffix",
    [
        '@app.get("/items")\ndef items(context: Annotated[str, Depends(check)]): pass',
        '@app.get("/items")\ndef items(context: str): pass',
        '@app.get("/items")\ndef items(context=wrap(Depends(check))): pass',
        '@app.get("/items")\ndef items(context=dependency_alias): pass',
        '@app.get("/items")\ndef items(context=0): pass',
        '@app.get("/items", dependencies=declared)\ndef items(): pass',
        '@app.get("/items", dependencies=None)\ndef items(): pass',
        '@app.get("/items", dependencies=[dependency_alias])\ndef items(): pass',
        '@app.get("/items")\ndef items(context=Security(check, scopes=declared)): pass',
        '@app.get("/items")\ndef items(context=Security(factory(), scopes=["a"])): pass',
        '@app.get("/items")\ndef items(context=Security()): pass',
    ],
)
def test_unproved_dependency_syntax_is_unknown_not_known_empty(suffix):
    assert_unknown(scopes(PREFIX + suffix))


def test_missing_or_nonunique_literal_method_path_is_unknown():
    assert_unknown(
        scopes(PREFIX + '@app.get("/other")\ndef other(): pass'), "nonunique-source-declaration"
    )
    source = PREFIX + '@app.get("/items")\ndef a(): pass\n@app.get("/items")\ndef b(): pass'
    assert_unknown(scopes(source), "nonunique-source-declaration")


def test_missing_core_dependency_location_is_not_a_proof_of_empty_scopes(monkeypatch):
    original = FastAPIRouteParser.parse_source

    def omitted(self, source, path):
        result = original(self, source, path)
        return replace(
            result, routes=tuple(replace(route, dependencies=()) for route in result.routes)
        )

    monkeypatch.setattr(FastAPIRouteParser, "parse_source", omitted)
    source = PREFIX + '@app.get("/items")\ndef items(context=Security(check, scopes=["a"])): pass'
    assert_unknown(scopes(source), "incomplete-dependency-inventory")


def test_composed_dependency_count_always_abstains_without_import_graph_expansion():
    result = engine.evaluate_query(
        {"main.py": "from api.router import router\n", "api/router.py": PREFIX},
        engine.Query("composed-dependency-count"),
    )
    assert_unknown(result, "unsupported-composition")


@pytest.mark.parametrize(
    "path", ["../main.py", "/main.py", "main.txt", "a//b.py", "a\\b.py", "a-b/c.py/else", None]
)
def test_virtual_source_labels_are_bounded_safe_python_paths(path):
    with pytest.raises(engine.QueryError, match="virtual source path"):
        engine.evaluate_query({path: PREFIX}, engine.Query("source-http-declaration-count"))


@pytest.mark.parametrize(
    "sources",
    [
        {},
        [],
        {f"a{i}.py": "" for i in range(5)},
        {"main.py": b""},
        {"main.py": "\x00"},
        {"main.py": "\ud800"},
    ],
)
def test_invalid_source_shape_encoding_or_count_raises_query_error(sources):
    with pytest.raises(engine.QueryError):
        engine.evaluate_query(sources, engine.Query("source-http-declaration-count"))


def test_source_limit_counts_utf8_bytes_and_rejects_character_overflow():
    for source in ("#" + "é" * engine.MAX_SOURCE_BYTES, "x" * (engine.MAX_SOURCE_BYTES + 1)):
        with pytest.raises(engine.QueryError, match="byte limit"):
            count(source)
    assert count("#" + "x" * (engine.MAX_SOURCE_BYTES - 1))["answer"] == "0"


@pytest.mark.parametrize(
    "arguments",
    [
        ("policy-intent",),
        (None,),
        ("source-http-declaration-count", "GET", "/items"),
        ("direct-security-scopes",),
        ("direct-security-scopes", "get", "/items"),
        ("direct-security-scopes", "GET", "items"),
        ("direct-security-scopes", "GET", "/\ud800"),
    ],
)
def test_query_contract_is_closed_and_selector_is_explicit(arguments):
    with pytest.raises(engine.QueryError):
        engine.Query(*arguments)


def test_queries_are_frozen_and_revalidated_before_use():
    query = engine.Query("source-http-declaration-count")
    with pytest.raises(FrozenInstanceError):
        query.kind = "different"
    object.__setattr__(query, "kind", "different")
    with pytest.raises(engine.QueryError):
        engine.evaluate_query({"main.py": PREFIX}, query)
    with pytest.raises(engine.QueryError):
        engine.evaluate_query({"main.py": PREFIX}, {})


def test_queries_never_touch_files_processes_or_network_or_import_target(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("source query must not access files, subprocesses, network or parse_file")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(io, "open", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(FastAPIRouteParser, "parse_file", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    source = (
        PREFIX
        + 'raise AssertionError("target must not execute")\n@app.get("/items")\ndef items(): pass'
    )
    assert count(source)["answer"] == "1"
    assert scopes(source)["answer"] == ""
