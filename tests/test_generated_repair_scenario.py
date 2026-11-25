"""Static source-context checks, not execution or human policy acceptance."""

import ast
import builtins
import socket
import subprocess
from hashlib import sha256
from pathlib import Path

import pytest

from authzest.codex import generated_repair_scenario as scenario


def test_owned_context_is_detached_and_contains_no_registered_after_solution():
    context = scenario.build_scenario_context()
    assert context["scenario_id"] == "owned-fastapi-document-ownership-v1"
    assert context["source"] == {
        "path": "app.py",
        "text": scenario.SOURCE,
        "sha256": sha256(scenario.SOURCE.encode("utf-8")).hexdigest(),
    }
    assert context["test_path"] == "tests/test_generated_ownership.py"
    assert context["test_before"] == "absent-in-planned-copy"
    assert context["policy_authorship"] == "assistant"
    assert context["policy_review"] == "pending-maintainer-review"
    assert not {"after", "after_text", "repair_template", "expected_cases"} & context.keys()
    assert context["policy"] == list(scenario.POLICY)
    context["policy"].clear()
    context["source"]["text"] = "changed"
    context["declarations"].clear()
    fresh = scenario.build_scenario_context()
    assert fresh["source"]["text"] == scenario.SOURCE
    assert fresh["policy"] and fresh["declarations"]


def test_source_is_parsed_as_data_and_one_route_is_inventoried():
    context = scenario.build_scenario_context()
    ast.parse(context["source"]["text"])
    declaration = context["declarations"][0]
    assert declaration["path"] == "/documents/{document_id}"
    assert declaration["methods"] == ["GET"]
    assert declaration["file"] == "app.py"
    assert declaration["dependencies"][0]["target"] == "current_actor"
    assert "caller-controlled" in " ".join(context["policy"])
    assert "not authentication" in " ".join(context["policy"])


def test_context_building_has_no_io_process_network_or_target_import(monkeypatch):
    original_import = builtins.__import__

    def forbidden(*args, **kwargs):
        pytest.fail("The generation scenario is in-memory source data only")

    def checked_import(name, *args, **kwargs):
        if name.split(".")[0] in {"app", "fastapi", "httpx", "openai", "requests"}:
            forbidden()
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", checked_import)
    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(builtins, "exec", forbidden)
    monkeypatch.setattr(builtins, "eval", forbidden)
    for method in ("open", "read_text", "read_bytes", "write_text", "write_bytes", "resolve"):
        monkeypatch.setattr(Path, method, forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    # Parse inside the guards, not from an inventory cached by an earlier test.
    scenario._declaration_json.cache_clear()
    assert scenario.build_scenario_context()["source"]["text"] == scenario.SOURCE


@pytest.mark.parametrize("source", ["def broken(", "app = object()\n"])
def test_changed_or_unparseable_scenario_fails_closed(monkeypatch, source):
    monkeypatch.setattr(scenario, "SOURCE", source)
    with pytest.raises(ValueError, match="scenario mismatch"):
        scenario.build_scenario_context()


def test_fixed_source_is_inventoried_once_while_every_check_rebuilds_the_context(monkeypatch):
    """Regression: re-parsing per check made the CI cold-start job CPU-bound past 15 min."""
    from authzest.codex.generated_repair import (
        build_generated_repair_request,
        validate_generated_repair_request,
    )

    parses = []
    original = scenario.FastAPIRouteParser.parse_source

    def counted(self, source, path):
        parses.append(source)
        return original(self, source, path)

    monkeypatch.setattr(scenario.FastAPIRouteParser, "parse_source", counted)
    scenario._declaration_json.cache_clear()
    request = build_generated_repair_request()
    for _ in range(20):
        assert validate_generated_repair_request(request.payload_json).request_id
    assert parses == [scenario.SOURCE]

    root = Path("owned-fastapi-document-ownership")
    direct = original(scenario.FastAPIRouteParser(), scenario.SOURCE, root / "app.py")
    first = scenario.build_scenario_context()
    assert first["declarations"] == [direct.routes[0].to_dict(root)]
    first["declarations"][0]["methods"].append("POST")
    first["declarations"][0]["dependencies"].clear()
    assert scenario.build_scenario_context()["declarations"] == [direct.routes[0].to_dict(root)]


def test_changed_source_is_parsed_again_after_a_cached_success(monkeypatch):
    assert scenario.build_scenario_context()["declarations"]
    monkeypatch.setattr(scenario, "SOURCE", "app = object()\n")
    for _ in range(2):  # A failed inventory is never cached as a success.
        with pytest.raises(ValueError, match="scenario mismatch"):
            scenario.build_scenario_context()
    monkeypatch.undo()
    assert scenario.build_scenario_context()["source"]["text"] == scenario.SOURCE
