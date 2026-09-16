"""Offline preview transport tests: only the supplied JSON file may be consumed."""

import asyncio
import builtins
import json
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest
from click import unstyle
from scripts import demo_preview
from scripts.demo_preview import build_demo_bundle
from typer.testing import CliRunner

from authzest.cli import app
from authzest.codex.app_server import CodexAppServerAdapter
from authzest.codex.contracts import MAX_JSON_BYTES, ContractError, canonical, identity
from authzest.codex.preview import preview_bundle, validate_preview_bundle
from authzest.codex.proposals import content_hash
from authzest.runner import ScanRunner
from authzest.runner import proposal_preview as reader

runner = CliRunner()
POSIX_READER = reader.preview_file_supported()


@pytest.fixture
def bundle():
    return build_demo_bundle()


@pytest.fixture
def bundle_file(tmp_path, bundle):
    path = tmp_path / "preview.json"
    path.write_text(bundle.payload_json, encoding="utf-8")
    return path


def assert_invalid(result):
    assert result.exit_code == 2, result.output
    assert result.stdout == ""
    assert result.stderr.isascii()
    error = json.loads(result.stderr)
    assert set(error) == {"status", "detail"}
    assert error["status"] == "invalid-input" and error["detail"]
    return error


@pytest.mark.parametrize("color", [False, True])
def test_help_does_not_read_an_input(monkeypatch, color):
    def forbidden(*args, **kwargs):
        pytest.fail("Help must not read a bundle")

    monkeypatch.setattr(reader, "load_preview", forbidden)
    result = runner.invoke(app, ["proposal-preview", "--help"], color=color)
    assert result.exit_code == 0
    assert "--json" in unstyle(result.stdout)
    assert "proposal-preview" in unstyle(runner.invoke(app, ["--help"], color=color).stdout)


@pytest.mark.skipif(not POSIX_READER, reason="Bounded POSIX preview reader")
@pytest.mark.parametrize("as_json", [False, True])
def test_preview_is_offline_and_reads_only_one_supplied_file(
    bundle_file, bundle, monkeypatch, as_json
):
    expected = preview_bundle(bundle)
    real_open = os.open
    opened = []

    def selected_open(path, flags, *args, **kwargs):
        assert Path(path) == bundle_file
        assert flags & os.O_NOFOLLOW and flags & os.O_NONBLOCK
        assert flags & os.O_ACCMODE == os.O_RDONLY
        opened.append(Path(path))
        return real_open(path, flags, *args, **kwargs)

    def forbidden(*args, **kwargs):
        pytest.fail("Preview must not rescan, execute, connect or read other inputs")

    monkeypatch.setattr(os, "open", selected_open)
    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(Path, "read_text", forbidden)
    monkeypatch.setattr(Path, "read_bytes", forbidden)
    monkeypatch.setattr(ScanRunner, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    result = runner.invoke(
        app, ["proposal-preview", str(bundle_file), *(["--json"] if as_json else [])]
    )
    assert result.exit_code == 0, result.output
    assert result.stderr == "" and result.stdout.isascii()
    assert opened == [bundle_file]
    if as_json:
        assert json.loads(result.stdout) == expected
    else:
        for heading in ("Request", "Review", "Evidence", "Proposal", "Expectations", "Limitations"):
            assert heading in result.stdout
        assert "Exact diff" in result.stdout
        for value in ("draft", "not-run", "unknown", expected["bundle_id"]):
            assert value in result.stdout


@pytest.mark.skipif(not POSIX_READER, reason="Bounded POSIX preview reader")
@pytest.mark.parametrize("kind", ["missing", "directory", "symlink", "fifo"])
def test_non_regular_inputs_are_rejected_without_opening(tmp_path, monkeypatch, kind):
    path = tmp_path / "private-input"
    if kind == "directory":
        path.mkdir()
    elif kind == "symlink":
        target = tmp_path / "target.json"
        target.write_text("{}", encoding="utf-8")
        path.symlink_to(target)
    elif kind == "fifo":
        os.mkfifo(path)

    def forbidden(*args, **kwargs):
        pytest.fail("A rejected input must not be opened")

    monkeypatch.setattr(os, "open", forbidden)
    error = assert_invalid(runner.invoke(app, ["proposal-preview", str(path)]))
    assert str(path) not in error["detail"] and "private-input" not in error["detail"]


@pytest.mark.skipif(not POSIX_READER, reason="Bounded POSIX preview reader")
@pytest.mark.parametrize("content", [b"\xff", b'{"secret":"untrusted"}', b"{", b""])
def test_invalid_contents_have_one_redacted_error(tmp_path, content):
    path = tmp_path / "private-input.json"
    path.write_bytes(content)
    error = assert_invalid(runner.invoke(app, ["proposal-preview", str(path), "--json"]))
    missing = assert_invalid(runner.invoke(app, ["proposal-preview", str(tmp_path / "missing")]))
    assert error == missing
    assert "private-input" not in error["detail"] and "untrusted" not in error["detail"]


@pytest.mark.skipif(not POSIX_READER, reason="Bounded POSIX preview reader")
def test_oversize_is_rejected_before_opening(tmp_path, monkeypatch):
    path = tmp_path / "oversize.json"
    path.write_bytes(b" " * (MAX_JSON_BYTES + 1))

    def forbidden(*args, **kwargs):
        pytest.fail("An oversized input must not be opened")

    monkeypatch.setattr(os, "open", forbidden)
    assert_invalid(runner.invoke(app, ["proposal-preview", str(path)]))


@pytest.mark.skipif(not POSIX_READER, reason="Bounded POSIX preview reader")
def test_cross_artifact_binding_is_revalidated(bundle, tmp_path):
    data = bundle.to_dict()
    data["proposal"]["rationale"] = "Changed without updating the bound manifest."
    path = tmp_path / "stale.json"
    path.write_text(canonical(data), encoding="utf-8")
    assert_invalid(runner.invoke(app, ["proposal-preview", str(path)]))


def test_unsupported_platform_fails_before_opening(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Unsupported platforms must not inspect or open the input")

    monkeypatch.setattr(reader, "preview_file_supported", lambda: False)
    monkeypatch.setattr(os, "open", forbidden)
    monkeypatch.setattr(os, "lstat", forbidden)
    with pytest.raises(reader.PreviewInputError):
        reader.load_preview(Path("not-read.json"))
    assert_invalid(runner.invoke(app, ["proposal-preview", "not-read.json"]))


def test_interrupted_preview_has_no_output(monkeypatch):
    def interrupted(*args, **kwargs):
        raise KeyboardInterrupt()

    monkeypatch.setattr(reader, "load_preview", interrupted)
    result = runner.invoke(app, ["proposal-preview", "unused.json"])
    assert result.exit_code == 130
    assert result.stdout == ""


@pytest.mark.skipif(not POSIX_READER, reason="Bounded POSIX preview reader")
def test_nul_path_has_a_redacted_reader_error():
    with pytest.raises(reader.PreviewInputError) as caught:
        reader.load_preview(Path("private\x00input.json"))
    assert "private" not in str(caught.value) and "\x00" not in str(caught.value)


@pytest.mark.skipif(not POSIX_READER, reason="Bounded POSIX preview reader")
@pytest.mark.parametrize("failure", ["changed-input", "read-error", "never-eof"])
def test_reader_closes_descriptor_and_bounds_reads(bundle_file, monkeypatch, failure):
    real_read, real_close = os.read, os.close
    requested, returned, closed = [], [], []

    def controlled_read(fd, amount):
        requested.append(amount)
        if failure == "read-error":
            raise OSError("private diagnostic must not be disclosed")
        if failure == "never-eof":
            value = b"x" * amount
        else:
            value = real_read(fd, amount)
            if len(requested) == 1:
                bundle_file.write_bytes(b"changed after descriptor read")
        returned.append(len(value))
        return value

    def close(fd):
        closed.append(fd)
        real_close(fd)

    monkeypatch.setattr(os, "read", controlled_read)
    monkeypatch.setattr(os, "close", close)
    with pytest.raises(reader.PreviewInputError) as caught:
        reader.load_preview(bundle_file)
    assert requested and max(requested) <= 16_384
    assert sum(returned) <= MAX_JSON_BYTES + 1
    assert len(closed) == 1
    assert "private diagnostic" not in str(caught.value)
    with pytest.raises(OSError):
        os.fstat(closed[0])


@pytest.mark.skipif(not POSIX_READER, reason="Bounded POSIX preview reader")
@pytest.mark.parametrize("replacement", ["regular", "symlink", "fifo"])
def test_path_replacement_during_open_is_rejected_before_reading(
    bundle_file, tmp_path, monkeypatch, replacement
):
    real_open = os.open
    target = tmp_path / "target.json"
    target.write_bytes(b"{}")

    def replacing_open(path, flags, *args, **kwargs):
        bundle_file.unlink()
        if replacement == "regular":
            bundle_file.write_bytes(b"{}")
        elif replacement == "symlink":
            bundle_file.symlink_to(target)
        else:
            os.mkfifo(bundle_file)
        return real_open(path, flags, *args, **kwargs)

    def forbidden(*args, **kwargs):
        pytest.fail("An identity/type mismatch must be rejected before any read")

    monkeypatch.setattr(os, "open", replacing_open)
    monkeypatch.setattr(os, "read", forbidden)
    with pytest.raises(reader.PreviewInputError):
        reader.load_preview(bundle_file)


@pytest.mark.skipif(not POSIX_READER, reason="Bounded POSIX preview reader")
@pytest.mark.parametrize("as_json", [False, True])
def test_untrusted_terminal_characters_are_escaped(bundle, tmp_path, as_json):
    data = bundle.to_dict()
    unsafe = "review \u0085\u202e\r\t한글"
    data["proposal"]["rationale"] = unsafe
    change = data["proposal"]["changes"][0]
    change["after_text"] += "# " + unsafe + "\n"
    data["manifest"]["proposal_id"] = "proposal-" + identity(data["proposal"])
    for item in data["manifest"]["expectations"]:
        item["after_sha256"] = content_hash(change["after_text"])
    updated = validate_preview_bundle(canonical(data))
    path = tmp_path / "quoted.json"
    path.write_text(updated.payload_json, encoding="utf-8")
    result = runner.invoke(app, ["proposal-preview", str(path), *(["--json"] if as_json else [])])
    assert result.exit_code == 0, result.output
    assert result.stdout.isascii()
    assert "\r" not in result.stdout and "\t" not in result.stdout
    for escaped in ("\\u0085", "\\u202e", "\\r", "\\t", "\\ud55c"):
        assert escaped in result.stdout
    if as_json:
        assert json.loads(result.stdout) == preview_bundle(updated)


@pytest.fixture
def offline_export(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Demo export must not start processes, providers or network connections")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(CodexAppServerAdapter, "__init__", forbidden)


def test_demo_export_stdout_is_an_ascii_valid_bundle(monkeypatch, capsys, offline_export):
    monkeypatch.setattr(sys, "argv", ["demo-preview"])
    demo_preview.main()
    captured = capsys.readouterr()
    assert captured.err == "" and captured.out.isascii()
    assert validate_preview_bundle(captured.out).to_dict() == build_demo_bundle().to_dict()


def test_demo_export_creates_only_new_file_and_preserves_fixture(
    tmp_path, monkeypatch, capsys, offline_export
):
    source = Path(__file__).parent / "fixtures/ai_evaluation/v1/public/main.py"
    before = source.read_bytes()
    output = tmp_path / "bundle.json"
    monkeypatch.setattr(sys, "argv", ["demo-preview", "--output", str(output)])
    demo_preview.main()
    captured = capsys.readouterr()
    assert captured.out == captured.err == ""
    first = output.read_bytes()
    assert first.isascii()
    data = validate_preview_bundle(first.decode("utf-8")).to_dict()
    embedded = next(e["data"] for e in data["request"]["evidence"] if e["kind"] == "source")
    assert embedded["text"].encode("utf-8") == before
    with pytest.raises(SystemExit) as caught:
        demo_preview.main()
    assert caught.value.code == 2
    assert capsys.readouterr().out == ""
    assert output.read_bytes() == first and source.read_bytes() == before


def test_demo_export_failure_has_no_output_or_private_path(
    tmp_path, monkeypatch, capsys, offline_export
):
    output = tmp_path / "private-missing-directory" / "bundle.json"
    monkeypatch.setattr(sys, "argv", ["demo-preview", "--output", str(output)])
    with pytest.raises(SystemExit) as caught:
        demo_preview.main()
    captured = capsys.readouterr()
    assert caught.value.code == 2 and captured.out == ""
    assert "Cannot create the output bundle" in captured.err
    assert "private-missing-directory" not in captured.err and str(output) not in captured.err
    assert not output.exists()


@pytest.mark.skipif(not POSIX_READER, reason="Bounded POSIX preview reader")
@pytest.mark.parametrize("malformed", ["nested-location", "integer-overflow"])
def test_malformed_nested_artifacts_have_no_traceback_or_partial_output(
    bundle, tmp_path, malformed
):
    data = bundle.to_dict()
    if malformed == "integer-overflow":
        data["request"]["config"]["temperature"] = 10**400
    else:
        evidence = next(item for item in data["request"]["evidence"] if item["kind"] == "route")
        route = evidence["data"]
        del route["registration"]["declaration"]["line"]
        route["registration_id"] = "route-" + identity(
            {
                key: route[key]
                for key in ("path", "methods", "function", "file", "line", "registration")
            }
        )
        evidence["id"] = "ev-" + identity({"kind": "route", "data": route})
    raw = canonical(data)
    with pytest.raises(ContractError):
        validate_preview_bundle(raw)
    path = tmp_path / "malformed.json"
    path.write_text(raw, encoding="utf-8")
    error = assert_invalid(runner.invoke(app, ["proposal-preview", str(path), "--json"]))
    assert "Traceback" not in error["detail"] and str(path) not in error["detail"]
