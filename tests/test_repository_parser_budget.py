"""Bounded parsing of owned source text; no import, execution or unbounded load run."""

import ast
from pathlib import Path

import pytest

from authzest.parser import fastapi
from authzest.parser.fastapi import FastAPIRouteParser, ParseBudgetExceeded


def flat_source(count):
    return "from fastapi import FastAPI\napp = FastAPI()\n" + "".join(
        f"@app.get('/items/{index}')\ndef read_{index}():\n    return {index}\n"
        for index in range(count)
    )


def composed_source(layers):
    source = (
        "from fastapi import FastAPI, APIRouter\n"
        "app = FastAPI()\nr0 = APIRouter()\n"
        "@r0.get('/item')\ndef read_item():\n    return 1\n"
    )
    for index in range(1, layers + 1):
        source += (
            f"r{index} = APIRouter()\n"
            f"r{index}.include_router(r{index - 1})\n"
            f"r{index}.include_router(r{index - 1})\n"
        )
    return source + f"app.include_router(r{layers})\n"


@pytest.mark.parametrize("source", [flat_source(3), composed_source(2)])
def test_inventory_below_budgets_matches_the_unchanged_default(source):
    tree, path = ast.parse(source), Path("source.py")
    parser = FastAPIRouteParser()
    expected = parser.parse_tree(tree, path)
    assert parser.parse_tree(tree, path, max_registrations=64, max_diagnostics=64) == expected
    assert parser.parse_tree(tree, path, max_registrations=None, max_diagnostics=None) == expected
    assert expected.routes


def test_direct_declarations_stop_before_allocating_an_over_budget_route(monkeypatch):
    original = fastapi.Route
    created = []

    def route(*args, **kwargs):
        created.append(kwargs["path"])
        return original(*args, **kwargs)

    monkeypatch.setattr(fastapi, "Route", route)
    with pytest.raises(ParseBudgetExceeded, match="registration budget"):
        FastAPIRouteParser().parse_tree(
            ast.parse(flat_source(3)), Path("private-label.py"), max_registrations=2
        )
    assert created == ["/items/0", "/items/1"]


def test_doubling_router_graph_stops_before_the_over_budget_batch_is_copied(monkeypatch):
    # The old unbounded parser is deliberately never run on this owned graph.
    # Every later layer would double its child's copies; the selected 64 limit
    # must stop construction after the small prefix, independent of the tail.
    original_add, original_replace = fastapi._Registrations.add, fastapi.replace
    added, copies = [], []

    def add(self, owner, route):
        original_add(self, owner, route)
        added.append(route)
        assert len(self.entries) <= 64

    def replace(value, **changes):
        copies.append(type(value).__name__)
        return original_replace(value, **changes)

    monkeypatch.setattr(fastapi._Registrations, "add", add)
    monkeypatch.setattr(fastapi, "replace", replace)
    with pytest.raises(ParseBudgetExceeded, match="registration budget"):
        FastAPIRouteParser().parse_tree(
            ast.parse(composed_source(24)), Path("private-label.py"), max_registrations=64
        )
    assert len(added) == 63
    assert copies.count("Route") == copies.count("RegistrationEvidence") == len(added) - 1


def test_diagnostics_are_bounded_without_publishing_a_partial_inventory():
    source = flat_source(4).replace("@app.get('/items/", "@app.get(dynamic_prefix + '/items/")
    tree, path = ast.parse(source), Path("source.py")
    parser = FastAPIRouteParser()
    with pytest.raises(ParseBudgetExceeded, match="diagnostic budget"):
        parser.parse_tree(tree, path, max_diagnostics=2)
    # This is a tiny normal diagnostic case, not an unbounded load reproduction.
    expected = parser.parse_tree(tree, path)
    assert len(expected.diagnostics) == 4
    assert parser.parse_tree(tree, path, max_diagnostics=4) == expected


@pytest.mark.parametrize("name", ["max_registrations", "max_diagnostics"])
@pytest.mark.parametrize("value", [False, True, 0, -1, 1.5, "64", [], {}])
def test_invalid_budgets_fail_before_ast_inventory(name, value):
    with pytest.raises(ValueError, match="positive integers"):
        FastAPIRouteParser().parse_tree(None, Path("unused.py"), **{name: value})


def test_exact_positive_registration_limit_is_usable():
    result = FastAPIRouteParser().parse_tree(
        ast.parse(flat_source(2)), Path("source.py"), max_registrations=2
    )
    assert [route.path for route in result.routes] == ["/items/0", "/items/1"]
