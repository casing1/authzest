import subprocess

import pytest

from authzest.diagnostics import collect_diagnostics


def test_doctor_allows_static_scans_when_codex_is_missing() -> None:
    report = collect_diagnostics(which=lambda _: None)

    assert report.ready is True
    assert report.checks[-1].name == "Codex CLI"
    assert report.checks[-1].status == "warning"
    assert "AI analysis is not implemented" in (report.checks[-1].remedy or "")


def test_doctor_checks_codex_version_and_login() -> None:
    commands: list[tuple[str, ...]] = []

    def fake_run(command: tuple[str, ...], **options: object) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        assert options == {"capture_output": True, "check": False, "text": True, "timeout": 5}
        output = "codex-cli 1.2.3\n" if command[-1] == "--version" else "Logged in using ChatGPT\n"
        return subprocess.CompletedProcess(command, 0, stdout=output, stderr="")

    report = collect_diagnostics(which=lambda _: "/usr/local/bin/codex", run=fake_run)

    assert report.ready is True
    assert [check.status for check in report.checks] == ["ok", "ok", "ok"]
    assert report.checks[-1].detail == "Logged in using ChatGPT"
    assert "AI analysis is not implemented" in report.checks[1].detail
    assert commands == [
        ("/usr/local/bin/codex", "--version"),
        ("/usr/local/bin/codex", "login", "status"),
    ]


def test_doctor_login_warning_does_not_suggest_that_login_enables_analysis() -> None:
    def fake_run(command: tuple[str, ...], **_: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            command, 0 if command[-1] == "--version" else 1, stdout="", stderr=""
        )

    report = collect_diagnostics(which=lambda _: "/mock/codex", run=fake_run)

    assert report.ready is True
    assert report.checks[-1].status == "warning"
    assert "does not enable AI analysis" in (report.checks[-1].remedy or "")


@pytest.mark.parametrize("timeout", [False, True])
def test_doctor_failed_optional_check_preserves_static_readiness(timeout: bool) -> None:
    def fake_run(command: tuple[str, ...], **_: object) -> subprocess.CompletedProcess[str]:
        if timeout:
            raise subprocess.TimeoutExpired(command, 5)
        raise OSError("mock command unavailable")

    report = collect_diagnostics(which=lambda _: "/mock/codex", run=fake_run)

    assert report.ready is True
    assert report.checks[-1].status == "warning"
    assert "AI analysis is not implemented" in (report.checks[-1].remedy or "")
