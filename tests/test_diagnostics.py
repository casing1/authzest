import subprocess

from authguard.diagnostics import collect_diagnostics


def test_doctor_allows_static_scans_when_codex_is_missing() -> None:
    report = collect_diagnostics(which=lambda _: None)

    assert report.ready is True
    assert report.checks[-1].name == "Codex CLI"
    assert report.checks[-1].status == "warning"


def test_doctor_checks_codex_version_and_login() -> None:
    def fake_run(command: tuple[str, ...], **_: object) -> subprocess.CompletedProcess[str]:
        output = "codex-cli 1.2.3\n" if command[-1] == "--version" else "Logged in using ChatGPT\n"
        return subprocess.CompletedProcess(command, 0, stdout=output, stderr="")

    report = collect_diagnostics(which=lambda _: "/usr/local/bin/codex", run=fake_run)

    assert report.ready is True
    assert [check.status for check in report.checks] == ["ok", "ok", "ok"]
    assert report.checks[-1].detail == "Logged in using ChatGPT"
