"""Runtime setup script with fake network/Docker collaborators only."""

from __future__ import annotations

import io
import os
import stat
from hashlib import sha256
from types import SimpleNamespace

import pytest
from scripts import repository_http_runtime_setup as setup

from authzest.runner._repository_http_runtime_profile import validate_runtime_profile


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _wheels(monkeypatch, data=b"wheel"):
    plan = [
        {
            "filename": "demo-1.0-py3-none-any.whl",
            "url": "https://files.pythonhosted.org/packages/demo-1.0-py3-none-any.whl",
            "size": len(data),
            "sha256": sha256(data).hexdigest(),
        }
    ]
    monkeypatch.setattr(setup, "wheel_plan", lambda root=None, role="A": plan)
    monkeypatch.setattr(
        setup.inputs, "verify_wheelhouse", lambda *a: {"kind": "repository-http-wheelhouse-check"}
    )
    return plan


def test_wheels_are_written_privately_after_exact_verification(tmp_path, monkeypatch):
    _wheels(monkeypatch)
    seen = []

    def opener(url, timeout):
        seen.append(url)
        return Response(b"wheel")

    report = setup.download_wheels(tmp_path / "wheels", opener=opener)
    assert report["kind"] == "repository-http-wheelhouse-check" and len(seen) == 1
    path = tmp_path / "wheels" / "demo-1.0-py3-none-any.whl"
    assert path.read_bytes() == b"wheel"
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
    assert stat.S_IMODE(os.stat(tmp_path / "wheels").st_mode) == 0o700


def test_changed_wheel_bytes_are_refused(tmp_path, monkeypatch):
    _wheels(monkeypatch)
    with pytest.raises(setup.SetupError, match="differs"):
        setup.download_wheels(tmp_path / "w", opener=lambda *_a, **_k: Response(b"other"))
    assert list((tmp_path / "w").iterdir()) == []


def test_unpinned_host_and_existing_output_are_refused(tmp_path, monkeypatch):
    plan = _wheels(monkeypatch)
    plan[0]["url"] = "http://example.invalid/demo.whl"
    with pytest.raises(setup.SetupError, match="files.pythonhosted.org"):
        setup.download_wheels(tmp_path / "w", opener=lambda *_a, **_k: Response(b"wheel"))
    with pytest.raises(setup.SetupError, match="must not exist"):
        setup.download_wheels(tmp_path / "w")


def test_real_plan_pins_fourteen_application_wheels_and_no_relay_wheels():
    plan = setup.wheel_plan()
    assert len(plan) == 14 and setup.wheel_plan(role="B") == []
    assert all(item["url"].startswith("https://files.pythonhosted.org/") for item in plan)


def _runner(calls, *, endpoint="unix:///owned/run/docker.sock"):
    def run(argv, **_kwargs):
        calls.append(argv)
        joined = " ".join(argv)
        if "image inspect" in joined:
            role = "a" if "-a:" in joined else "b"
            out = "sha256:" + ("7" if role == "a" else "8") * 64 + "\n"
        elif "context inspect" in joined:
            out = endpoint + "\n"
        elif " version " in joined + " ":
            out = "1.56 1.52\n"
        elif " info " in joined + " ":
            out = "synthetic-engine-id\n"
        else:
            out = ""
        return SimpleNamespace(returncode=0, stdout=out)

    return run


def test_build_uses_fresh_contexts_without_attestations(tmp_path, monkeypatch):
    monkeypatch.setattr(setup.inputs, "verify_wheelhouse", lambda *a: {})
    prepared = []

    def prepare(root, wheels, work, role, platform):
        prepared.append((role, wheels))
        return SimpleNamespace(context_path=work / ("context-" + role))

    monkeypatch.setattr(setup.contexts, "prepare_image_context", prepare)
    monkeypatch.setattr(setup.contexts, "check_prepared_context", lambda root, value: {})
    calls = []
    images = setup.build_images(tmp_path / "wheels", tmp_path / "work", runner=_runner(calls))
    assert [role for role, _ in prepared] == ["A", "B"]
    assert prepared[1][1] == tmp_path / "work" / "empty-wheelhouse"
    builds = [argv for argv in calls if argv[1] == "build"]
    assert all("--provenance=false" in a and "--sbom=false" in a for a in builds)
    assert all("--platform=linux/arm64" in a and "--pull=false" in a for a in builds)
    assert images["A"]["image_id"] == "sha256:" + "7" * 64


def test_profile_pins_private_client_copy_and_validates(tmp_path):
    docker = tmp_path / "docker"
    docker.write_bytes(b"#!/bin/sh\n")
    docker.chmod(0o755)
    images = {role: {"image_id": "sha256:" + d * 64} for role, d in (("A", "7"), ("B", "8"))}
    calls = []
    state = tmp_path / "state"
    path = setup.write_profile(images, state=state, docker=str(docker), runner=_runner(calls))
    profile = validate_runtime_profile(path.read_text().strip()).to_dict()
    engine = profile["engine"]
    assert engine["executable"] == str(state / "bin" / "docker")
    assert engine["executable_sha256"] == sha256(b"#!/bin/sh\n").hexdigest()
    assert engine["api_version"] == "1.52" and engine["endpoint"].startswith("unix://")
    assert (state / "docker-config" / "config.json").read_bytes() == b"{}\n"
    for item, mode in ((state, 0o700), (state / "bin", 0o700), (path, 0o600)):
        assert stat.S_IMODE(os.stat(item).st_mode) == mode
    assert stat.S_IMODE(os.stat(state / "bin" / "docker").st_mode) == 0o755
    with pytest.raises(setup.SetupError, match="already exists"):
        setup.write_profile(images, state=state, docker=str(docker), runner=_runner([]))


def test_profile_refuses_remote_endpoint(tmp_path):
    docker = tmp_path / "docker"
    docker.write_bytes(b"x")
    images = {role: {"image_id": "sha256:" + "7" * 64} for role in "AB"}
    with pytest.raises(setup.SetupError, match="unix"):
        setup.write_profile(
            images,
            state=tmp_path / "s",
            docker=str(docker),
            runner=_runner([], endpoint="tcp://203.0.113.1:2376"),
        )


def test_main_reports_failures_without_traceback(tmp_path, capsys):
    (tmp_path / "exists").mkdir()
    assert setup.main(["wheels", "--output", str(tmp_path / "exists")]) == 1
    assert "HTTP runtime setup failed" in capsys.readouterr().err
