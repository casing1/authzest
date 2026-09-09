from pathlib import Path

from authzest.runner import ScanRunner


def test_scan_runner_counts_python_files_and_routes(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text(
        "from fastapi import FastAPI\napp = FastAPI()\n"
        '@app.post("/sessions")\ndef create_session():\n    pass\n',
        encoding="utf-8",
    )
    ignored = tmp_path / "node_modules"
    ignored.mkdir()
    (ignored / "ignored.py").write_text(
        'from fastapi import FastAPI\napp = FastAPI()\n@app.get("/ignored")\ndef ignored(): pass\n'
    )

    report = ScanRunner().run(tmp_path)

    assert report.python_files == 1
    assert len(report.routes) == 1
    assert report.routes[0].path == "/sessions"
    assert report.codex_status == "disabled"


def test_ignored_directories_are_not_local_import_candidates(tmp_path: Path) -> None:
    ignored = tmp_path / "node_modules"
    ignored.mkdir()
    (ignored / "__init__.py").write_text("", encoding="utf-8")
    (ignored / "users.py").write_text(
        "from fastapi import APIRouter\nrouter = APIRouter()\n"
        '@router.get("/ignored")\ndef ignored(): pass\n',
        encoding="utf-8",
    )
    (tmp_path / "main.py").write_text(
        "from fastapi import FastAPI\nfrom node_modules.users import router\n"
        "app = FastAPI()\n"
        'app.include_router(router, prefix="/incorrect")\n'
        '@app.get("/health")\ndef health(): pass\n',
        encoding="utf-8",
    )

    report = ScanRunner().run(tmp_path)

    assert report.python_files == 1
    assert report.parse_errors == ()
    assert [route.path for route in report.routes] == ["/health"]
