from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from scripts import verify_preview_dispatch as dispatch

CHECKOUT = Path(__file__).resolve().parents[1]
SHA = "0123456789abcdef0123456789abcdef01234567"
OTHER_SHA = "abcdef0123456789abcdef0123456789abcdef01"


def test_dispatch_accepts_only_an_exact_main_run_and_checkout() -> None:
    dispatch.verify_dispatch("workflow_dispatch", "refs/heads/main", SHA, SHA, SHA)


@pytest.mark.parametrize("event", ["", "push", "pull_request", "workflow_run", "schedule"])
def test_dispatch_refuses_other_events(event: str) -> None:
    with pytest.raises(ValueError, match="workflow_dispatch"):
        dispatch.verify_dispatch(event, "refs/heads/main", SHA, SHA, SHA)


@pytest.mark.parametrize(
    "ref",
    ["", "main", "refs/heads/main/", "refs/heads/feature", "refs/tags/main", "refs/tags/v0.1.0"],
)
def test_dispatch_refuses_other_refs(ref: str) -> None:
    with pytest.raises(ValueError, match="main branch"):
        dispatch.verify_dispatch("workflow_dispatch", ref, SHA, SHA, SHA)


@pytest.mark.parametrize(
    "invalid",
    ["", SHA[:7], SHA[:-1], SHA + "0", SHA.upper(), "g" * 40, " " + SHA, SHA + "\n", "é" * 40],
)
@pytest.mark.parametrize("field", [0, 1, 2])
def test_dispatch_refuses_malformed_shas(invalid: str, field: int) -> None:
    shas = [SHA, SHA, SHA]
    shas[field] = invalid
    with pytest.raises(ValueError, match="40 lowercase hexadecimal digits"):
        dispatch.verify_dispatch("workflow_dispatch", "refs/heads/main", *shas)


@pytest.mark.parametrize(
    "shas", [(OTHER_SHA, SHA, SHA), (SHA, OTHER_SHA, SHA), (SHA, SHA, OTHER_SHA)]
)
def test_dispatch_refuses_a_stale_selection_or_different_checkout(
    shas: tuple[str, str, str],
) -> None:
    with pytest.raises(ValueError, match="does not match"):
        dispatch.verify_dispatch("workflow_dispatch", "refs/heads/main", *shas)


@pytest.fixture
def dispatch_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_EVENT_NAME", "workflow_dispatch")
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")
    monkeypatch.setenv("AUTHZEST_PREVIEW_EXPECTED_SHA", SHA)
    monkeypatch.setenv("GITHUB_SHA", SHA)


def test_main_checks_checkout_and_reports_the_exact_nonpublishing_commit(
    dispatch_environment: None, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(dispatch, "read_checkout_sha", lambda: SHA)
    dispatch.main()
    output = capsys.readouterr().out
    assert f"main commit {SHA}" in output
    assert "not release or policy-execution approval" in output


@pytest.mark.parametrize(
    "missing", ["GITHUB_EVENT_NAME", "GITHUB_REF", "AUTHZEST_PREVIEW_EXPECTED_SHA", "GITHUB_SHA"]
)
def test_main_fails_closed_before_git_if_context_is_missing(
    dispatch_environment: None, monkeypatch: pytest.MonkeyPatch, missing: str
) -> None:
    monkeypatch.delenv(missing)

    def unexpected_git() -> str:
        pytest.fail("A refused workflow context must not query Git.")

    monkeypatch.setattr(dispatch, "read_checkout_sha", unexpected_git)
    with pytest.raises(SystemExit, match="dispatch refused"):
        dispatch.main()


def test_main_refuses_a_mismatching_checkout(
    dispatch_environment: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(dispatch, "read_checkout_sha", lambda: OTHER_SHA)
    with pytest.raises(SystemExit, match="checkout HEAD does not match"):
        dispatch.main()


@pytest.mark.parametrize(
    "error",
    [
        OSError("git unavailable"),
        subprocess.CalledProcessError(128, ["git", "rev-parse"]),
        subprocess.TimeoutExpired(["git", "rev-parse"], 10),
        UnicodeDecodeError("ascii", b"\xff", 0, 1, "not ASCII"),
    ],
)
def test_main_refuses_checkout_query_errors(
    dispatch_environment: None, monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    def fail() -> str:
        raise error

    monkeypatch.setattr(dispatch, "read_checkout_sha", fail)
    with pytest.raises(SystemExit, match="dispatch refused"):
        dispatch.main()


def test_checkout_query_is_read_only_bounded_and_exact(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, stdout=SHA + "\n", stderr="")

    monkeypatch.setattr(dispatch.subprocess, "run", fake_run)
    assert dispatch.read_checkout_sha() == SHA
    assert calls == [
        (
            ["git", "rev-parse", "--verify", "HEAD"],
            {
                "stdin": subprocess.DEVNULL,
                "capture_output": True,
                "encoding": "ascii",
                "errors": "strict",
                "timeout": 10,
                "check": True,
            },
        )
    ]


def test_checkout_query_rejects_unexpected_stderr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        dispatch.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess([], 0, SHA + "\n", "warning"),
    )
    with pytest.raises(ValueError, match="clean checkout HEAD response"):
        dispatch.read_checkout_sha()


@pytest.mark.parametrize("output", [SHA + "\n\n", " " + SHA + "\n", SHA + " extra\n"])
def test_git_output_is_not_silently_trimmed_or_partially_accepted(
    monkeypatch: pytest.MonkeyPatch, output: str
) -> None:
    monkeypatch.setattr(
        dispatch.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess([], 0, output, ""),
    )
    with pytest.raises(ValueError, match="40 lowercase hexadecimal digits"):
        dispatch.verify_dispatch(
            "workflow_dispatch", "refs/heads/main", SHA, SHA, dispatch.read_checkout_sha()
        )


def test_native_preview_workflow_is_manual_and_nonpublishing() -> None:
    workflow = (CHECKOUT / ".github/workflows/native-preview.yml").read_text()
    trigger = workflow.split("\non:\n", 1)[1].split("\npermissions:\n", 1)[0]
    assert trigger == (
        "  workflow_dispatch:\n"
        "    inputs:\n"
        "      expected_sha:\n"
        '        description: "Exact 40-character lowercase main commit SHA to check '
        '(no publication)"\n'
        "        required: true\n"
        "        type: string\n"
    )
    assert "permissions:\n  contents: read\n" in workflow
    assert workflow.count("permissions:") == 1
    assert "group: native-preview-${{ github.ref }}" in workflow
    assert "cancel-in-progress: false" in workflow
    assert workflow.count("uses: actions/checkout@v7") == 3
    assert workflow.count("ref: ${{ github.sha }}\n          persist-credentials: false") == 3
    assert workflow.count("timeout-minutes:") == 3
    assert "timeout-minutes: 5" in workflow
    assert "timeout-minutes: 45" in workflow
    assert "timeout-minutes: 20" in workflow
    for forbidden in (
        "smoke_fixture_runtime",
        "doctor",
        "codex ",
        "policy_worker",
        "gh release",
        "git tag",
        "git push",
        "contents: write",
        "secrets.",
        "GH_TOKEN",
        "pull_request_target",
        "workflow_call",
    ):
        assert forbidden not in workflow
    assert "  publish:" not in workflow


def test_native_preview_workflow_gates_build_and_download_at_the_same_sha() -> None:
    workflow = (CHECKOUT / ".github/workflows/native-preview.yml").read_text()
    guard, rest = workflow.split("\n  guard:\n", 1)[1].split("\n  build:\n", 1)
    build, download = rest.split("\n  verify-artifacts:\n", 1)
    assert "python -I -S scripts/verify_preview_dispatch.py" in guard
    assert "AUTHZEST_PREVIEW_EXPECTED_SHA: ${{ inputs.expected_sha }}" in guard
    assert "${{ inputs." not in build + download
    assert "    needs: guard\n" in build
    assert "    needs: build\n" in download
    for job in (build, download):
        assert "os: [ubuntu-latest, macos-latest, windows-latest]" in job
        assert "fail-fast: false" in job
        assert "ref: ${{ github.sha }}" in job
    assert "python -m pip install -e '.[build]'" in build
    assert "npm ci --ignore-scripts" in build
    assert "npm run build" in build
    assert "python -m PyInstaller --clean --noconfirm authzest.spec" in build
    assert "python -I -S scripts/smoke_release.py --binary dist/authzest\n" in build
    assert "python -I -S scripts/smoke_release.py --binary dist/authzest.exe\n" in build
    assert "python scripts/package_release.py" in build
    assert 'AUTHZEST_RELEASE_TAG: ""' in build
    assert "python -I -S scripts/smoke_release.py --artifact-dir release" in build
    assert "uses: actions/upload-artifact@v7" in build
    assert "retention-days: 7" in build
    assert "if-no-files-found: error" in build
    assert "uses: actions/download-artifact@v8" in download
    assert "importlib.util.find_spec('authzest') is None" in download
    assert "python -I -S scripts/smoke_release.py --artifact-dir artifact" in download
    assert "pip install" not in download
    artifact_name = (
        "name: preview-${{ github.sha }}-${{ github.run_id }}-${{ github.run_attempt }}"
        "-${{ runner.os }}-${{ runner.arch }}"
    )
    assert artifact_name in build and artifact_name in download
