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
    assert scenario.build_scenario_context()["source"]["text"] == scenario.SOURCE


@pytest.mark.parametrize("source", ["def broken(", "app = object()\n"])
def test_changed_or_unparseable_scenario_fails_closed(monkeypatch, source):
    monkeypatch.setattr(scenario, "SOURCE", source)
    with pytest.raises(ValueError, match="scenario mismatch"):
        scenario.build_scenario_context()
