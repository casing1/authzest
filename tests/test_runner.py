from pathlib import Path

from authguard.runner import ScanRunner


def test_scan_runner_counts_python_files_and_routes(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text(
        '@app.post("/sessions")\ndef create_session():\n    pass\n',
        encoding="utf-8",
    )
    ignored = tmp_path / "node_modules"
    ignored.mkdir()
    (ignored / "ignored.py").write_text('@app.get("/ignored")\ndef ignored(): pass\n')

    report = ScanRunner().run(tmp_path)

    assert report.python_files == 1
    assert len(report.routes) == 1
    assert report.routes[0].path == "/sessions"
    assert report.codex_status == "disabled"
