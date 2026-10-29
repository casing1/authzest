import asyncio
import builtins
import hashlib
import json
import os
import socket
import stat
import subprocess
import sys
from pathlib import Path

import pytest
from scripts import smoke_release
from scripts.verify_release import read_project_version

from authzest.cli_output import format_sharing_preview
from authzest.codex.contracts import MAX_JSON_BYTES, canonical, identity

PREVIEW_COMMANDS = {"codex-owner-review", "codex-owner-repair"}


@pytest.fixture(autouse=True)
def forbid_live_preview_effects(monkeypatch: pytest.MonkeyPatch) -> None:
    from authzest.runner import codex_owner_repair, codex_owner_review

    def forbidden(*args, **kwargs):
        pytest.fail("Release smoke unit tests must not start a provider, policy worker or network")

    original_import = builtins.__import__

    def checked_import(name, globals=None, locals=None, fromlist=(), level=0):
        targets = {name, *(f"{name}.{item}" for item in fromlist or ())}
        assert not targets.intersection(
            {
                "authzest.codex.app_server",
                "authzest.runner._owner_policy_worker",
                "authzest.runner._owner_policy_repair_worker",
            }
        )
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", checked_import)
    for workflow in (codex_owner_review, codex_owner_repair):
        monkeypatch.setattr(workflow, "_default_adapter_factory", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_shell", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)


def owner_preview(kind: str) -> dict:
    return (
        smoke_release.source_owner_preview()
        if kind == "review"
        else smoke_release.source_owner_repair_preview(kind)
    )


class FakeBinary:
    """Exercise the smoke driver without launching an arbitrary executable in unit tests."""

    def __init__(self, version: str = "0.1.0a2") -> None:
        self.version = version
        self.calls: list[tuple[list[str], dict[str, object]]] = []

    def __call__(self, arguments: list[str], **options: object) -> subprocess.CompletedProcess[str]:
        self.calls.append((arguments, options))
        command = arguments[1:]
        if command == ["--version"]:
            return subprocess.CompletedProcess(arguments, 0, f"authzest {self.version}\n", "")
        if command == ["--help"]:
            return subprocess.CompletedProcess(
                arguments, 0, "Usage: authzest [--version] scan\n", ""
            )
        if command[0] in PREVIEW_COMMANDS:
            candidate = command[2] if command[0] == "codex-owner-repair" else "review"
            prefix = (
                ["codex-owner-repair", "--candidate", candidate]
                if candidate != "review"
                else ["codex-owner-review"]
            )
            assert candidate in {"review", "before", "after"}
            assert command == [
                *prefix,
                "--model",
                smoke_release.OWNER_PREVIEW_MODEL,
                "--preview-only",
            ] + (["--json"] if "--json" in command else [])
            payload = owner_preview(candidate)
            payload["invocation_nonce"] = f"{len(self.calls):032x}"
            rebind_preview(payload)
            output = json.dumps(payload) if "--json" in command else format_sharing_preview(payload)
            return subprocess.CompletedProcess(arguments, 0, output + "\n", "")
        assert command[0] == "scan"
        fixture = Path(command[1])
        if not fixture.exists():
            return subprocess.CompletedProcess(
                arguments, 2, "", f"Error: Path does not exist: {fixture}\n"
            )
        payload = smoke_release.source_report(fixture)
        code = 1 if "--strict" in command and payload["analysis_status"] == "partial" else 0
        output = (
            json.dumps(payload) if "--json" in command else "FastAPI routes: 3\nAnalysis: bounded\n"
        )
        return subprocess.CompletedProcess(arguments, code, output, "")


def rebind_preview(payload: dict) -> None:
    """Recompute hashes so mutated-content tests cannot pass on hash rejection alone."""
    content = {
        key: value
        for key, value in payload.items()
        if key not in {"sharing_id", "sharing_content_id", "invocation_nonce"}
    }
    payload["sharing_content_id"] = "content-" + identity(content)
    payload["sharing_id"] = "share-" + identity(
        {key: value for key, value in payload.items() if key != "sharing_id"}
    )


def rebind_repair_preview(payload: dict) -> None:
    """Rehash nested changed data too; these self-consistent hashes do not make it trusted."""
    transport = payload["transport_request"]
    request = transport["request"]
    content = request["content"]
    for field in ("before", "after", "criteria"):
        content[field]["sha256"] = hashlib.sha256(content[field]["text"].encode()).hexdigest()
    content["cases_sha256"] = identity(content["cases"])
    request["registry"]["content_sha256"] = identity(content)
    for field in ("before", "after", "criteria", "cases"):
        request["evidence_ids"][field] = "owner-repair-evidence-" + identity(
            {"kind": field, "data": content[field]}
        )
    request_id = "owner-repair-request-" + identity(request)
    transport["request_id"] = payload["recommendation_request_id"] = request_id
    transport["output_schema"]["properties"]["request_id"]["enum"] = [request_id]
    transport["prompt"] = (
        request["prompt"]["text"]
        + "\nREQUEST_JSON:\n"
        + canonical(request)
        + "\nREQUEST_ID:\n"
        + request_id
        + "\n"
    )
    payload["request_id"] = "owner-repair-transport-" + identity(transport)
    payload["prompt"] = transport["prompt"]
    payload["prompt_sha256"] = hashlib.sha256(payload["prompt"].encode()).hexdigest()
    payload["output_schema"] = transport["output_schema"]
    payload["output_schema_sha256"] = identity(payload["output_schema"])
    payload["limits_sha256"] = identity(payload["limits"])
    rebind_preview(payload)


def write_binary(tmp_path: Path, name: str = "selected AuthZest") -> Path:
    binary = tmp_path / name
    binary.write_bytes(b"unit-test bytes, never executed")
    return binary


def write_artifact(tmp_path: Path) -> tuple[Path, str]:
    binary = write_binary(tmp_path, "authzest-0.1.0a2-test-x64")
    digest = hashlib.sha256(binary.read_bytes()).hexdigest()
    binary.with_name(binary.name + ".sha256").write_bytes(
        f"{digest}  {binary.name}\n".encode("ascii")
    )
    return binary, digest


def test_selected_binary_and_copy_use_only_bounded_commands_in_an_isolated_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    binary = write_binary(tmp_path)
    fake = FakeBinary()
    monkeypatch.setattr(subprocess, "run", fake)
    monkeypatch.setenv("PYTHONPATH", "/ambient/python/source")
    monkeypatch.setenv("PYTHONHOME", "/ambient/python/home")
    monkeypatch.setenv("VIRTUAL_ENV", "/ambient/venv")
    monkeypatch.setenv("CONDA_PREFIX", "/ambient/conda")

    checks = smoke_release.smoke_binary(binary, "0.1.0a2")

    assert len(checks) == 26
    assert len(fake.calls) == 30
    executables = {arguments[0] for arguments, _ in fake.calls}
    assert str(binary.resolve()) in executables and len(executables) == 2
    assert any("relocated binary copy" in check for check in checks)
    assert any("fastapi_partial JSON strict=True exit=1" in check for check in checks)
    for arguments, options in fake.calls:
        assert arguments[1] in {"--version", "--help", "scan", *PREVIEW_COMMANDS}
        assert isinstance(options["cwd"], Path) and options["cwd"] != smoke_release.CHECKOUT
        assert options["timeout"] == 45
        assert options["stdin"] == subprocess.DEVNULL
        assert options["check"] is False
        assert options.get("shell", False) is False
        environment = options["env"]
        assert "PYTHONPATH" not in environment and "PYTHONHOME" not in environment
        assert "VIRTUAL_ENV" not in environment and "CONDA_PREFIX" not in environment
        assert environment["PYTHONNOUSERSITE"] == "1"
        assert environment["PYTHONIOENCODING"] == "utf-8"


def test_artifact_mode_checks_a_relocated_verified_copy_without_changing_the_download(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    binary, digest = write_artifact(tmp_path)
    binary.chmod(stat.S_IRUSR | stat.S_IWUSR)
    original_mode = binary.stat().st_mode
    fake = FakeBinary()
    monkeypatch.setattr(subprocess, "run", fake)

    selected, verified_digest = smoke_release.select_artifact(tmp_path)
    checks = smoke_release.smoke_binary(selected, "0.1.0a2", artifact_digest=verified_digest)

    assert digest == verified_digest
    assert len(checks) == 13 and len(fake.calls) == 15
    assert len({arguments[0] for arguments, _ in fake.calls}) == 1
    assert all(arguments[0] != str(binary) for arguments, _ in fake.calls)
    assert all("relocated verified artifact" in check for check in checks)
    assert binary.stat().st_mode == original_mode
    assert binary.read_bytes() == b"unit-test bytes, never executed"


def test_installed_cli_checks_only_the_selected_launcher_without_copy_or_mode_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    binary = write_binary(tmp_path)
    original_mode = binary.stat().st_mode
    fake = FakeBinary()
    monkeypatch.setattr(subprocess, "run", fake)
    monkeypatch.setenv("OPENAI_API_KEY", "unit-test-not-a-secret")
    monkeypatch.setenv("PYTHONPATH", "/unselected/checkout")

    def forbidden(*args, **kwargs):
        pytest.fail("Installed console launchers must not be copied or chmodded")

    monkeypatch.setattr(smoke_release.shutil, "copy2", forbidden)
    monkeypatch.setattr(Path, "chmod", forbidden)
    checks = smoke_release.smoke_binary(binary, "0.1.0a2", installed_cli=True)

    assert len(checks) == 13 and len(fake.calls) == 15
    assert all(check.startswith("installed CLI:") for check in checks)
    assert {arguments[0] for arguments, _ in fake.calls} == {str(binary.resolve())}
    assert binary.stat().st_mode == original_mode
    assert binary.read_bytes() == b"unit-test bytes, never executed"
    for _, options in fake.calls:
        assert options["cwd"] != smoke_release.CHECKOUT
        assert options["stdin"] == subprocess.DEVNULL
        assert options["timeout"] == 45
        assert options.get("shell", False) is False
        assert options["env"] == smoke_release.preview_environment(options["cwd"].parent / "bin")
        assert "OPENAI_API_KEY" not in options["env"]
        assert "PYTHONPATH" not in options["env"]


def test_installed_cli_cannot_be_combined_with_artifact_digest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeBinary()
    monkeypatch.setattr(subprocess, "run", fake)
    with pytest.raises(smoke_release.SmokeError, match="mutually exclusive"):
        smoke_release.smoke_binary(
            write_binary(tmp_path), "0.1.0a2", installed_cli=True, artifact_digest="0" * 64
        )
    assert fake.calls == []


def test_modified_artifact_between_selection_and_copy_is_rejected_before_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    binary, _ = write_artifact(tmp_path)
    selected, digest = smoke_release.select_artifact(tmp_path)
    binary.write_bytes(b"changed after verification")
    fake = FakeBinary()
    monkeypatch.setattr(subprocess, "run", fake)

    with pytest.raises(smoke_release.SmokeError, match="Copied artifact"):
        smoke_release.smoke_binary(selected, "0.1.0a2", artifact_digest=digest)
    assert fake.calls == []


@pytest.mark.parametrize(
    "condition", ["missing", "multiple", "missing-checksum", "mismatch", "wrong-name"]
)
def test_artifact_selection_rejects_missing_ambiguous_or_unverified_inputs(
    tmp_path: Path, condition: str
) -> None:
    if condition == "missing":
        with pytest.raises(smoke_release.SmokeError, match="exactly one"):
            smoke_release.select_artifact(tmp_path)
        return
    binary, digest = write_artifact(tmp_path)
    checksum = binary.with_name(binary.name + ".sha256")
    if condition == "multiple":
        write_binary(tmp_path, "authzest-second-test-x64")
    elif condition == "missing-checksum":
        checksum.unlink()
    elif condition == "mismatch":
        binary.write_bytes(b"bad download")
    elif condition == "wrong-name":
        checksum.write_bytes(f"{digest}  another-binary\n".encode("ascii"))
    with pytest.raises(smoke_release.SmokeError):
        smoke_release.select_artifact(tmp_path)


def test_missing_selected_binary_and_missing_artifact_directory_are_clear_failures(
    tmp_path: Path,
) -> None:
    with pytest.raises(smoke_release.SmokeError, match="regular file"):
        smoke_release.selected_binary(tmp_path / "missing")
    with pytest.raises(smoke_release.SmokeError, match="regular file"):
        smoke_release.selected_binary(tmp_path)
    with pytest.raises(smoke_release.SmokeError, match="directory is missing"):
        smoke_release.select_artifact(tmp_path / "missing")


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf"), -float("inf")])
def test_invalid_timeouts_fail_before_any_process_starts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, timeout: float
) -> None:
    fake = FakeBinary()
    monkeypatch.setattr(subprocess, "run", fake)
    with pytest.raises(smoke_release.SmokeError, match="finite and positive"):
        smoke_release.smoke_binary(write_binary(tmp_path), "0.1.0a2", timeout)
    assert fake.calls == []


@pytest.mark.parametrize(
    "failure", ["timeout", "os-error", "wrong-exit", "stderr", "bad-version", "bad-help"]
)
@pytest.mark.parametrize("installed_cli", [False, True])
def test_process_and_command_contract_failures_stop_the_smoke_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str, installed_cli: bool
) -> None:
    fake = FakeBinary()

    def broken(arguments: list[str], **options: object) -> subprocess.CompletedProcess[str]:
        if failure == "timeout":
            raise subprocess.TimeoutExpired(arguments, options["timeout"])
        if failure == "os-error":
            raise OSError("cannot execute selected file")
        result = fake(arguments, **options)
        if failure == "wrong-exit":
            result.returncode = 7
        elif failure == "stderr":
            result.stderr = "unexpected warning"
        elif failure == "bad-version":
            result.stdout = "authzest 0.1.0a1\n"
        elif failure == "bad-help" and arguments[1] == "--help":
            result.stdout = "incomplete help"
        return result

    monkeypatch.setattr(subprocess, "run", broken)
    with pytest.raises(smoke_release.SmokeError):
        smoke_release.smoke_binary(write_binary(tmp_path), "0.1.0a2", installed_cli=installed_cli)


@pytest.mark.parametrize(
    "failure",
    ["json", "wrong-root", "wrong-schema", "lost-effective", "wrong-position", "boolean-count"],
)
@pytest.mark.parametrize("installed_cli", [False, True])
def test_full_json_contract_comparison_rejects_incorrect_binary_payloads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str, installed_cli: bool
) -> None:
    fake = FakeBinary()

    def incorrect(arguments: list[str], **options: object) -> subprocess.CompletedProcess[str]:
        result = fake(arguments, **options)
        if "--json" not in arguments or result.returncode == 2:
            return result
        payload = json.loads(result.stdout)
        if failure == "json":
            result.stdout = "not JSON"
            return result
        if failure == "wrong-root":
            payload["root"] = "/unselected/source"
        elif failure == "wrong-schema":
            payload["schema_version"] = "1.1"
        elif failure == "lost-effective":
            del payload["routes"][0]["effective_dependencies"]
        elif failure == "wrong-position":
            payload["routes"][0]["registration"]["declaration"]["column"] += 1
        elif failure == "boolean-count":
            payload["python_files"] = True
        result.stdout = json.dumps(payload)
        return result

    monkeypatch.setattr(subprocess, "run", incorrect)
    with pytest.raises(smoke_release.SmokeError):
        smoke_release.smoke_binary(write_binary(tmp_path), "0.1.0a2", installed_cli=installed_cli)


def test_normalization_changes_only_root_and_portable_source_file_separators(
    tmp_path: Path,
) -> None:
    source = {
        "root": str(tmp_path.resolve()),
        "routes": [{"file": "app\\main.py", "registration_id": "route-stable", "path": "/items"}],
    }
    normalized = smoke_release.normalized_report(source, tmp_path)
    assert normalized == {
        "root": "<owned-fixture>",
        "routes": [{"file": "app/main.py", "registration_id": "route-stable", "path": "/items"}],
    }
    assert source["root"] == str(tmp_path.resolve())
    assert source["routes"][0]["file"] == "app\\main.py"


def test_partial_fixture_is_analyzed_without_importing_or_executing_its_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_import = builtins.__import__

    def reject_target(name: str, *args: object, **kwargs: object) -> object:
        assert name.split(".")[0] not in {"fastapi", "examples", "main"}
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", reject_target)
    payload = smoke_release.source_report(smoke_release.CHECKOUT / "examples" / "fastapi_partial")
    assert payload["analysis_status"] == "partial" and payload["route_count"] == 1
    assert payload["parse_errors"] == [] and payload["codex_status"] == "disabled"
    assert [diagnostic["code"] for diagnostic in payload["diagnostics"]] == [
        "unsupported-dependency-list"
    ]
    assert payload["routes"][0]["dependencies"] == []
    assert payload["routes"][0]["effective_dependencies"][0]["target"] == "example_context"


def test_cli_requires_an_explicit_binary_or_artifact_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.argv", ["smoke_release.py"])
    with pytest.raises(SystemExit) as exit_info:
        smoke_release.main()
    assert exit_info.value.code == 2


def test_cli_defaults_to_checkout_version_and_reports_relocation_limitations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    binary = write_binary(tmp_path)
    fake = FakeBinary(read_project_version(smoke_release.CHECKOUT / "pyproject.toml"))
    monkeypatch.setattr(subprocess, "run", fake)
    monkeypatch.setattr("sys.argv", ["smoke_release.py", "--binary", str(binary)])

    smoke_release.main()

    output = capsys.readouterr().out
    assert "Release smoke passed: 26 checks" in output
    assert "not clean-machine installation, upgrade" in output
    assert "No Codex or target code was executed" in output


def test_installed_cli_selection_reports_no_install_or_relocation_claim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    binary = write_binary(tmp_path)
    fake = FakeBinary(read_project_version(smoke_release.CHECKOUT / "pyproject.toml"))
    monkeypatch.setattr(subprocess, "run", fake)
    monkeypatch.setattr("sys.argv", ["smoke_release.py", "--installed-cli", str(binary)])
    smoke_release.main()
    output = capsys.readouterr().out
    assert "Release smoke passed: 13 checks" in output
    assert "does not install or upgrade packages, verify installation provenance" in output
    assert "Record installer and source evidence separately" in output
    assert "relocated" not in output


@pytest.mark.parametrize("other", ["--binary", "--artifact-dir"])
def test_installed_cli_selection_is_mutually_exclusive(
    monkeypatch: pytest.MonkeyPatch, other: str
) -> None:
    monkeypatch.setattr("sys.argv", ["smoke_release.py", "--installed-cli", "cli", other, "other"])
    with pytest.raises(SystemExit) as exit_info:
        smoke_release.main()
    assert exit_info.value.code == 2


def test_environment_uses_only_the_selected_temp_bin_as_its_added_path(tmp_path: Path) -> None:
    environment = smoke_release.child_environment(tmp_path)
    assert environment["PATH"].split(os.pathsep)[0] == str(tmp_path)


def test_preview_environment_excludes_ambient_credentials_and_executable_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for key in (
        "OPENAI_API_KEY",
        "CODEX_HOME",
        "USERPROFILE",
        "PYTHONPATH",
        "PYTHONHOME",
        "VIRTUAL_ENV",
        "CONDA_PREFIX",
        "_PYI_ARCHIVE_FILE",
        "GH_TOKEN",
        "PATH",
    ):
        monkeypatch.setenv(key, "unusable-unit-test-value")
    monkeypatch.setenv("SystemRoot", "test-system-root")
    monkeypatch.setenv("TMP", "test-temp")
    environment = smoke_release.preview_environment(tmp_path)
    assert environment["PATH"] == str(tmp_path)
    assert next(value for key, value in environment.items() if key.upper() == "SYSTEMROOT") == (
        "test-system-root"
    )
    assert environment["TMP"] == "test-temp"
    assert set(environment) <= {
        "SystemRoot",
        "SYSTEMROOT",
        "WINDIR",
        "TEMP",
        "TMP",
        "TMPDIR",
        "LANG",
        "LC_ALL",
        "PATH",
        "PYTHONNOUSERSITE",
        "PYTHONDONTWRITEBYTECODE",
        "PYTHONUTF8",
        "PYTHONIOENCODING",
        "NO_COLOR",
        "TERM",
    }


def test_all_preview_calls_are_unapproved_offline_and_use_the_minimal_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeBinary()
    monkeypatch.setattr(subprocess, "run", fake)
    smoke_release.smoke_binary(write_binary(tmp_path), "0.1.0a2")
    calls = [(args, opts) for args, opts in fake.calls if args[1] in PREVIEW_COMMANDS]
    assert len(calls) == 12
    observed = set()
    for args, options in calls:
        assert "--preview-only" in args and "--model" in args
        candidate = args[3] if args[1] == "codex-owner-repair" else "review"
        observed.add((args[0], candidate, "--json" in args))
        assert options["env"]["PATH"] == str(options["cwd"].parent / "bin")
        assert not any(key in options["env"] for key in ("HOME", "CODEX_HOME", "OPENAI_API_KEY"))
        assert options["stdin"] == subprocess.DEVNULL
        assert options["timeout"] == 45
    assert len(observed) == 12
    assert {candidate for _, candidate, _ in observed} == {"review", "before", "after"}


@pytest.mark.parametrize("as_json", [False, True])
@pytest.mark.parametrize(
    "failure",
    [
        "json",
        "array",
        "duplicate",
        "extra-result",
        "nonfinite",
        "oversize",
        "nonce",
        "nonce-type",
        "sharing-id",
        "content-id",
        "main-source",
        "policy-source",
        "policy",
        "model",
        "evidence",
        "prompt",
        "schema",
        "limits",
        "host-instructions",
        "extra-field",
        "missing-field",
        "typed-limit",
    ],
)
def test_owner_preview_rejects_incomplete_or_changed_envelopes(as_json: bool, failure: str) -> None:
    expected = smoke_release.source_owner_preview()
    payload = json.loads(json.dumps(expected))
    payload["invocation_nonce"] = "1" * 32
    if failure in {"main-source", "policy-source"}:
        path = "main.py" if failure == "main-source" else "policy.py"
        snapshot = next(
            item["data"]
            for item in payload["request"]["evidence"]
            if item["kind"] == "source" and item["data"]["path"] == path
        )
        snapshot["text"] += "\n# changed packaged source\n"
    elif failure == "policy":
        next(item for item in payload["request"]["evidence"] if item["kind"] == "policy")[
            "data"
        ] = "changed policy"
    elif failure == "model":
        payload["request"]["config"]["model"] = "unexpected-model"
    elif failure == "evidence":
        payload["request"]["evidence"] = []
    elif failure == "prompt":
        payload["prompt"] += "\nchanged prompt"
    elif failure == "schema":
        payload["output_schema"]["type"] = "array"
    elif failure == "limits":
        payload["limits"]["application_retries"] = 1
    elif failure == "host-instructions":
        payload["host_instructions"] = "changed host instructions"
    elif failure == "extra-field":
        payload["approved"] = True
    elif failure == "missing-field":
        del payload["sharing"]
    elif failure == "typed-limit":
        payload["limits"]["application_retries"] = False
    rebind_preview(payload)
    if failure == "nonce":
        payload["invocation_nonce"] = "A" * 32
    elif failure == "nonce-type":
        payload["invocation_nonce"] = True
    elif failure == "sharing-id":
        payload["sharing_id"] = "share-incorrect"
    elif failure == "content-id":
        payload["sharing_content_id"] = "content-incorrect"
        payload["sharing_id"] = "share-" + identity(
            {key: value for key, value in payload.items() if key != "sharing_id"}
        )
    raw = json.dumps(payload)
    if failure == "json":
        raw = "not JSON"
    elif failure == "array":
        raw = "[]"
    elif failure == "duplicate":
        raw = '{"kind":"duplicate",' + raw[1:]
    elif failure == "extra-result":
        raw += "\n{}"
    elif failure == "nonfinite":
        raw = '{"invalid":NaN,' + raw[1:]
    elif failure == "oversize":
        raw = " " * (MAX_JSON_BYTES + 1) + raw
    output = (
        raw
        if as_json
        else format_sharing_preview(payload).split(smoke_release.SHARING_ENVELOPE_MARKER, 1)[0]
        + smoke_release.SHARING_ENVELOPE_MARKER
        + raw
    )
    seen: set[str] = set()
    with pytest.raises(smoke_release.SmokeError):
        smoke_release.check_owner_preview(output, expected, as_json=as_json, seen_nonces=seen)
    assert seen == set()


@pytest.mark.parametrize("kind", ["review", "before", "after"])
@pytest.mark.parametrize("failure", ["missing-envelope", "duplicate-envelope", "wrong-summary"])
def test_owner_preview_human_contract_rejects_summary_and_envelope_loss(
    kind: str, failure: str
) -> None:
    preview = owner_preview(kind)
    output = format_sharing_preview(preview)
    if failure == "missing-envelope":
        output = output.split(smoke_release.SHARING_ENVELOPE_MARKER, 1)[0]
    elif failure == "duplicate-envelope":
        output += smoke_release.SHARING_ENVELOPE_MARKER + "{}"
    else:
        output = output.replace("no approval implied", "approved", 1)
    with pytest.raises(smoke_release.SmokeError):
        smoke_release.check_owner_preview(output, preview, as_json=False, seen_nonces=set())


def test_reused_nonce_fails_even_with_a_valid_complete_preview() -> None:
    preview = smoke_release.source_owner_preview()
    seen: set[str] = set()
    smoke_release.check_owner_preview(json.dumps(preview), preview, as_json=True, seen_nonces=seen)
    with pytest.raises(smoke_release.SmokeError, match="reused"):
        smoke_release.check_owner_preview(
            format_sharing_preview(preview), preview, as_json=False, seen_nonces=seen
        )


@pytest.mark.parametrize("kind", ["review", "before", "after"])
def test_owner_preview_baseline_is_offline_and_never_imports_policy_or_cli(
    monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    from authzest.runner import codex_owner_repair, codex_owner_review

    def forbidden(*args, **kwargs):
        pytest.fail("Preview baseline must not use a provider, process or policy import")

    original_import = builtins.__import__

    def safe_import(name, *args, **kwargs):
        assert name not in {
            "fastapi",
            "typer",
            "authzest.cli",
            "authzest.cli_output",
            "policy",
            "main",
        }
        assert not name.startswith("examples.") and name != "authzest.codex.app_server"
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", safe_import)
    monkeypatch.setattr(codex_owner_review, "_default_adapter_factory", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(Path, "read_text", forbidden)
    monkeypatch.setattr(Path, "read_bytes", forbidden)
    monkeypatch.setattr(codex_owner_review.secrets, "token_hex", forbidden)
    monkeypatch.setattr(codex_owner_repair, "_default_adapter_factory", forbidden)
    preview = owner_preview(kind)
    request_key = "request" if kind == "review" else "transport_request"
    assert preview[request_key]["config"]["model"] == smoke_release.OWNER_PREVIEW_MODEL
    assert preview["invocation_nonce"] == "0" * 32
    if kind != "review":
        assert preview["candidate"] == preview["transport_request"]["request"]["candidate"] == kind


@pytest.mark.parametrize("kind", ["review", "before", "after"])
def test_baseline_rejects_an_ambient_owner_builder_and_restores_import_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    from authzest.runner import codex_owner_repair, codex_owner_review

    builder = codex_owner_review if kind == "review" else codex_owner_repair
    monkeypatch.setattr(builder, "__file__", str(tmp_path / "unexpected.py"))
    before = list(sys.path)
    with pytest.raises(smoke_release.SmokeError, match="not loaded from this checkout"):
        owner_preview(kind)
    assert sys.path == before


@pytest.mark.parametrize("kind", ["review", "before", "after"])
@pytest.mark.parametrize("failure", ["wrong-exit", "stderr", "timeout", "unicode"])
def test_owner_preview_process_failures_stop_the_driver(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str, kind: str
) -> None:
    fake = FakeBinary()
    selected = (
        ["codex-owner-review"] if kind == "review" else ["codex-owner-repair", "--candidate", kind]
    )

    def broken(arguments, **options):
        result = fake(arguments, **options)
        if arguments[1 : len(selected) + 1] != selected:
            return result
        if failure == "timeout":
            raise subprocess.TimeoutExpired(arguments, options["timeout"])
        if failure == "unicode":
            raise UnicodeError("unit-test invalid output")
        if failure == "wrong-exit":
            result.returncode = 1
        else:
            result.stderr = "unit-test unexpected preview warning"
        return result

    monkeypatch.setattr(subprocess, "run", broken)
    with pytest.raises(smoke_release.SmokeError):
        smoke_release.smoke_binary(write_binary(tmp_path), "0.1.0a2")
    assert len([args for args, _ in fake.calls if args[1 : len(selected) + 1] == selected]) == 1


def test_replayed_nonce_in_the_second_preview_stops_before_the_relocated_binary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeBinary()

    def replay(arguments, **options):
        result = fake(arguments, **options)
        if arguments[1] == "codex-owner-review":
            preview = smoke_release.source_owner_preview()
            result.stdout = (
                json.dumps(preview) if "--json" in arguments else format_sharing_preview(preview)
            )
        return result

    monkeypatch.setattr(subprocess, "run", replay)
    with pytest.raises(smoke_release.SmokeError, match="reused"):
        smoke_release.smoke_binary(write_binary(tmp_path), "0.1.0a2")
    assert len({args[0] for args, _ in fake.calls}) == 1


@pytest.mark.parametrize("candidate", ["before", "after"])
@pytest.mark.parametrize("as_json", [False, True])
@pytest.mark.parametrize(
    ("path", "replacement"),
    [
        (("candidate",), "unregistered"),
        (("content", "before", "text"), "# changed before policy, never executed\n"),
        (("content", "after", "text"), "# changed after policy, never executed\n"),
        (("content", "criteria", "text"), "Changed policy criterion"),
        (("content", "assumptions", 0, "text"), "Changed trust assumption"),
        (("content", "assumptions", 0, "id"), "unregistered-assumption"),
        (("content", "cases", 1, "expected"), "allow"),
        (("content", "cases", 0, "principal", "subject"), "mallory"),
        (("content", "cases", 0, "principal", "authenticated"), 1),
        (("content", "cases", 0, "principal", "scopes"), ["reports:*"]),
        (("content", "cases", 0, "report", "owner_id"), "mallory"),
        (("content", "cases", 0, "case_id"), "unreviewed-case"),
        (("content", "cases"), []),
        (("content", "path"), "unselected.py"),
        (("content", "scenario_id"), "unregistered-scenario"),
        (("registry", "pair_id"), "owner-repair-pair-unregistered"),
        (("registry", "review_record_sha256"), "f" * 64),
        (("prompt", "text"), "Changed nested prompt"),
        (("prompt", "version"), "unregistered-prompt"),
    ],
)
def test_repair_preview_rejects_rehashed_nested_policy_and_case_changes(
    candidate: str, as_json: bool, path: tuple, replacement: object
) -> None:
    expected = smoke_release.source_owner_repair_preview(candidate)
    payload = json.loads(json.dumps(expected))
    target = payload["transport_request"]["request"]
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = replacement
    rebind_repair_preview(payload)
    # The sharing identity is valid for the altered nested policy/cases and derived prompt.
    output = json.dumps(payload) if as_json else format_sharing_preview(payload)
    seen: set[str] = set()
    with pytest.raises(smoke_release.SmokeError, match="differs from the checkout"):
        smoke_release.check_owner_preview(output, expected, as_json=as_json, seen_nonces=seen)
    assert seen == set()


@pytest.mark.parametrize("candidate", ["before", "after"])
@pytest.mark.parametrize("as_json", [False, True])
@pytest.mark.parametrize(
    ("path", "replacement"),
    [
        (("kind",), "codex-owner-review-sharing-preview"),
        (("candidate",), "unregistered"),
        (("source_scope",), "arbitrary-repository"),
        (("transport_request", "config", "model"), "wrong-model"),
        (("transport_request", "request_id"), "unbound-request"),
        (("transport_request", "output_schema", "type"), "array"),
        (("transport_request", "host_instructions"), "Changed transport instructions"),
        (("transport_request", "prompt"), "Changed transport prompt"),
        (("recommendation_request_id",), "unbound-recommendation"),
        (("request_id",), "unbound-transport"),
        (("host_instructions",), "Changed outer instructions"),
        (("prompt",), "Changed outer prompt"),
        (("output_schema", "properties", "status", "enum"), ["approved"]),
        (("limits", "application_retries"), 1),
        (("limits", "application_retries"), False),
        (("limits", "max_application_turn_attempts"), 2),
        (("limits", "timeout_seconds"), 121.0),
        (("sharing",), "Approved; execute and apply automatically"),
    ],
)
def test_repair_preview_rejects_rehashed_transport_schema_limits_and_sharing_changes(
    candidate: str, as_json: bool, path: tuple, replacement: object
) -> None:
    expected = smoke_release.source_owner_repair_preview(candidate)
    payload = json.loads(json.dumps(expected))
    target = payload
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = replacement
    payload["prompt_sha256"] = hashlib.sha256(payload["prompt"].encode()).hexdigest()
    payload["output_schema_sha256"] = identity(payload["output_schema"])
    payload["limits_sha256"] = identity(payload["limits"])
    rebind_preview(payload)
    output = json.dumps(payload) if as_json else format_sharing_preview(payload)
    with pytest.raises(smoke_release.SmokeError, match="differs from the checkout"):
        smoke_release.check_owner_preview(output, expected, as_json=as_json, seen_nonces=set())


@pytest.mark.parametrize("candidate", ["before", "after"])
@pytest.mark.parametrize("as_json", [False, True])
@pytest.mark.parametrize(
    "failure",
    [
        "json",
        "array",
        "refused",
        "duplicate",
        "extra-result",
        "nonfinite",
        "oversize",
        "nonce",
        "nonce-type",
        "sharing-id",
        "content-id",
        "missing-field",
        "extra-field",
    ],
)
def test_repair_preview_rejects_malformed_refused_or_incomplete_output(
    candidate: str, as_json: bool, failure: str
) -> None:
    expected = smoke_release.source_owner_repair_preview(candidate)
    payload = json.loads(json.dumps(expected))
    if failure == "missing-field":
        del payload["transport_request"]
    elif failure == "extra-field":
        payload["approved"] = True
    elif failure == "nonce":
        payload["invocation_nonce"] = "A" * 32
    elif failure == "nonce-type":
        payload["invocation_nonce"] = False
    rebind_preview(payload)
    if failure == "sharing-id":
        payload["sharing_id"] = "share-incorrect"
    elif failure == "content-id":
        payload["sharing_content_id"] = "content-incorrect"
        payload["sharing_id"] = "share-" + identity(
            {key: value for key, value in payload.items() if key != "sharing_id"}
        )
    raw = json.dumps(payload)
    if failure == "json":
        raw = "not JSON"
    elif failure == "array":
        raw = "[]"
    elif failure == "refused":
        raw = '{"status":"not-shared","sharing_decision":"cancel"}'
    elif failure == "duplicate":
        raw = '{"candidate":"duplicate",' + raw[1:]
    elif failure == "extra-result":
        raw += "\n{}"
    elif failure == "nonfinite":
        raw = '{"invalid":NaN,' + raw[1:]
    elif failure == "oversize":
        raw = " " * (MAX_JSON_BYTES + 1) + raw
    output = (
        raw
        if as_json
        else format_sharing_preview(payload).split(smoke_release.SHARING_ENVELOPE_MARKER, 1)[0]
        + smoke_release.SHARING_ENVELOPE_MARKER
        + raw
    )
    seen: set[str] = set()
    with pytest.raises(smoke_release.SmokeError):
        smoke_release.check_owner_preview(output, expected, as_json=as_json, seen_nonces=seen)
    assert seen == set()


@pytest.mark.parametrize("as_json", [False, True])
def test_driver_rejects_valid_before_envelope_returned_for_after_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, as_json: bool
) -> None:
    fake = FakeBinary()

    def swapped(arguments, **options):
        result = fake(arguments, **options)
        if (
            arguments[1:4] == ["codex-owner-repair", "--candidate", "after"]
            and ("--json" in arguments) == as_json
        ):
            preview = smoke_release.source_owner_repair_preview("before")
            preview["invocation_nonce"] = "f" * 32
            rebind_preview(preview)
            result.stdout = json.dumps(preview) if as_json else format_sharing_preview(preview)
        return result

    monkeypatch.setattr(subprocess, "run", swapped)
    with pytest.raises(smoke_release.SmokeError, match="differs from the checkout"):
        smoke_release.smoke_binary(write_binary(tmp_path), "0.1.0a2")
    assert len({args[0] for args, _ in fake.calls}) == 1


@pytest.mark.parametrize(
    ("original_index", "replay_index"),
    [(0, 2), (2, 4), (0, 6), (2, 8), (4, 11)],
    ids=[
        "review-to-repair",
        "before-to-after",
        "review-relocated",
        "before-relocated",
        "after-json",
    ],
)
def test_driver_rejects_nonce_reuse_across_commands_candidates_formats_and_relocation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, original_index: int, replay_index: int
) -> None:
    fake = FakeBinary()
    preview_index = 0
    remembered = None

    def replay(arguments, **options):
        nonlocal preview_index, remembered
        result = fake(arguments, **options)
        if arguments[1] not in PREVIEW_COMMANDS:
            return result
        candidate = arguments[3] if arguments[1] == "codex-owner-repair" else "review"
        preview = owner_preview(candidate)
        preview["invocation_nonce"] = f"{len(fake.calls):032x}"
        if preview_index == original_index:
            remembered = preview["invocation_nonce"]
        if preview_index == replay_index:
            assert remembered is not None
            preview["invocation_nonce"] = remembered
        rebind_preview(preview)
        result.stdout = (
            json.dumps(preview) if "--json" in arguments else format_sharing_preview(preview)
        )
        preview_index += 1
        return result

    monkeypatch.setattr(subprocess, "run", replay)
    with pytest.raises(smoke_release.SmokeError, match="reused"):
        smoke_release.smoke_binary(write_binary(tmp_path), "0.1.0a2")
    assert preview_index == replay_index + 1
    assert len({args[0] for args, _ in fake.calls}) == (1 if replay_index < 6 else 2)


def test_repair_baseline_restores_import_path_when_builder_refuses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from authzest.runner import codex_owner_repair

    def refused(*args, **kwargs):
        raise codex_owner_repair.OwnerRepairInputError("registered source changed")

    monkeypatch.setattr(codex_owner_repair, "build_owner_repair_preview", refused)
    before = list(sys.path)
    with pytest.raises(codex_owner_repair.OwnerRepairInputError, match="registered source changed"):
        smoke_release.source_owner_repair_preview("before")
    assert sys.path == before


def test_release_and_windows_ci_continue_using_the_versioned_smoke_driver() -> None:
    release = (smoke_release.CHECKOUT / ".github/workflows/release.yml").read_text()
    assert "os: [ubuntu-latest, macos-latest, windows-latest]" in release
    assert "python scripts/smoke_release.py --binary dist/authzest" in release
    assert "python scripts/smoke_release.py --binary dist/authzest.exe" in release
    assert "python scripts/smoke_release.py --artifact-dir release" in release
    assert "python -I scripts/smoke_release.py --artifact-dir artifact" in release
    ci = (smoke_release.CHECKOUT / ".github/workflows/ci.yml").read_text()
    windows_job = ci.split("  proposal-check-windows:", 1)[1].split("  frontend:", 1)[0]
    assert "tests/test_release_smoke.py" in windows_job
