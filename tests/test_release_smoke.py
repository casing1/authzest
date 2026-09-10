import builtins
import hashlib
import json
import os
import stat
import subprocess
from pathlib import Path

import pytest
from scripts import smoke_release


class FakeBinary:
    """Exercise the smoke driver without launching an arbitrary executable in unit tests."""

    def __init__(self) -> None:
        self.calls: list[tuple[list[str], dict[str, object]]] = []

    def __call__(self, arguments: list[str], **options: object) -> subprocess.CompletedProcess[str]:
        self.calls.append((arguments, options))
        command = arguments[1:]
        if command == ["--version"]:
            return subprocess.CompletedProcess(arguments, 0, "authzest 0.1.0a2\n", "")
        if command == ["--help"]:
            return subprocess.CompletedProcess(
                arguments, 0, "Usage: authzest [--version] scan\n", ""
            )
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

    assert len(checks) == 14
    assert len(fake.calls) == 18
    executables = {arguments[0] for arguments, _ in fake.calls}
    assert str(binary.resolve()) in executables and len(executables) == 2
    assert any("relocated binary copy" in check for check in checks)
    assert any("fastapi_partial JSON strict=True exit=1" in check for check in checks)
    for arguments, options in fake.calls:
        assert arguments[1] in {"--version", "--help", "scan"}
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
    assert len(checks) == 7 and len(fake.calls) == 9
    assert len({arguments[0] for arguments, _ in fake.calls}) == 1
    assert all(arguments[0] != str(binary) for arguments, _ in fake.calls)
    assert all("relocated verified artifact" in check for check in checks)
    assert binary.stat().st_mode == original_mode
    assert binary.read_bytes() == b"unit-test bytes, never executed"


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
def test_process_and_command_contract_failures_stop_the_smoke_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
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
        smoke_release.smoke_binary(write_binary(tmp_path), "0.1.0a2")


@pytest.mark.parametrize(
    "failure",
    ["json", "wrong-root", "wrong-schema", "lost-effective", "wrong-position", "boolean-count"],
)
def test_full_json_contract_comparison_rejects_incorrect_binary_payloads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
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
        smoke_release.smoke_binary(write_binary(tmp_path), "0.1.0a2")


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
    fake = FakeBinary()
    monkeypatch.setattr(subprocess, "run", fake)
    monkeypatch.setattr("sys.argv", ["smoke_release.py", "--binary", str(binary)])

    smoke_release.main()

    output = capsys.readouterr().out
    assert "Release smoke passed: 14 checks" in output
    assert "not clean-machine installation, upgrade" in output
    assert "No Codex or target code was executed" in output


def test_environment_uses_only_the_selected_temp_bin_as_its_added_path(tmp_path: Path) -> None:
    environment = smoke_release.child_environment(tmp_path)
    assert environment["PATH"].split(os.pathsep)[0] == str(tmp_path)
