"""Launcher tests never start a server, provider, daemon or generated guest."""

from __future__ import annotations

import os
import re
import subprocess
import sys

import pytest
import uvicorn
from typer.testing import CliRunner

from authzest.cli import app


@pytest.fixture(autouse=True)
def selected_workspace_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("AUTHZEST_SCAN_ROOT", str(tmp_path))


def test_default_ui_remains_read_only(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setenv("AUTHZEST_SCAN_ROOT", str(tmp_path))
    monkeypatch.setattr(uvicorn, "run", lambda *args, **kw: calls.append((args, kw)))
    result = CliRunner().invoke(app, ["ui", "--workspace", str(tmp_path)])
    assert result.exit_code == 0
    assert calls == [
        (("authzest.api.app:app",), {"host": "127.0.0.1", "port": 8000, "reload": False})
    ]
    assert "authzest-ai=" not in result.stdout


@pytest.mark.skipif(os.name != "posix", reason="Active source UI is POSIX-only")
@pytest.mark.parametrize(
    "flags",
    [
        ["--host", "0.0.0.0"],
        ["--host", "localhost"],
        ["--reload"],
        ["--port", "0"],
        ["--port", "65536"],
    ],
)
def test_active_ui_refuses_other_bindings_and_reload_before_loading_runtime(monkeypatch, flags):
    def unexpected(*args, **kw):
        raise AssertionError("No server should start")

    monkeypatch.setattr(uvicorn, "run", unexpected)
    result = CliRunner().invoke(app, ["ui", "--ai-runtime-config", "/PRIVATE-DO-NOT-READ", *flags])
    assert result.exit_code == 2
    assert "source install" in result.stderr and "PRIVATE-DO-NOT-READ" not in result.output


@pytest.mark.skipif(os.name != "posix", reason="Active source UI is POSIX-only")
def test_active_ui_refuses_frozen_installation(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    result = CliRunner().invoke(app, ["ui", "--ai-runtime-config", "/PRIVATE-DO-NOT-READ"])
    assert result.exit_code == 2 and "authzest-ai=" not in result.output


@pytest.mark.skipif(os.name != "posix", reason="Active source UI is POSIX-only")
def test_active_ui_uses_explicit_app_and_new_private_fragment_without_starting_job(
    monkeypatch, tmp_path
):
    from authzest.api import _owner_read_controller as module
    from authzest.runner import _owner_read_runtime as runtime_module

    calls, profiles, controllers = [], [], []

    class Runtime:
        def __init__(self, path):
            profiles.append(path)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    class Controller:
        def __init__(self, path):
            self.path, self.closed = path, 0
            controllers.append(self)

        def close(self):
            self.closed += 1
            return True

    monkeypatch.setattr(runtime_module, "OwnerReadRuntime", Runtime)
    monkeypatch.setattr(module, "OwnerReadUIController", Controller)
    monkeypatch.setattr(uvicorn, "run", lambda *args, **kw: calls.append((args, kw)))
    path = tmp_path / "private-runtime.json"
    args = ["ui", "--ai-runtime-config", str(path), "--workspace", str(tmp_path), "--port", "8769"]
    outputs = [CliRunner().invoke(app, args) for _ in range(2)]
    assert all(result.exit_code == 0 for result in outputs)
    tokens = []
    for result in outputs:
        matched = re.search(r"http://127\.0\.0\.1:8769/#authzest-ai=([\w-]{43})", result.stdout)
        assert matched is not None
        tokens.append(matched[1])
    assert tokens[0] != tokens[1]
    assert profiles == [path, path]
    assert len(calls) == 2
    for (positional, options), controller in zip(calls, controllers, strict=True):
        application = positional[0]
        assert not isinstance(application, str)
        assert "/api/ai/runs" in application.openapi()["paths"]
        assert options == {"host": "127.0.0.1", "port": 8769, "reload": False, "workers": 1}
        assert controller.path == path and controller.closed == 1


@pytest.mark.skipif(os.name != "posix", reason="Active source UI is POSIX-only")
def test_invalid_runtime_refuses_startup_without_disclosing_path(monkeypatch):
    from authzest.runner import _owner_read_runtime as module

    def unavailable(path):
        raise OSError("PRIVATE-DO-NOT-DISPLAY")

    monkeypatch.setattr(module, "OwnerReadRuntime", unavailable)
    result = CliRunner().invoke(app, ["ui", "--ai-runtime-config", "/PRIVATE-DO-NOT-READ"])
    assert result.exit_code == 2
    assert "configuration is unavailable" in result.stderr
    assert "PRIVATE-DO-NOT" not in result.output


@pytest.mark.skipif(os.name != "posix", reason="Active source UI is POSIX-only")
def test_fresh_active_launch_uses_selected_workspace_before_api_import(tmp_path):
    script = """
import json,sys
from typer.testing import CliRunner
from authzest.cli import app
r=CliRunner().invoke(app,['ui','--workspace',sys.argv[1],
    '--ai-runtime-config','/private/tmp/authzest-inert-missing-runtime.json'])
print(json.dumps({'exit_code':r.exit_code,'output':r.output}))
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path)],
        env={**os.environ, "AUTHZEST_SCAN_ROOT": str(tmp_path / "missing-old-workspace")},
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    )
    import json

    value = json.loads(result.stdout)
    assert value["exit_code"] == 2
    assert "configuration is unavailable" in value["output"]
    assert "missing-old-workspace" not in value["output"]
