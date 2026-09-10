from pathlib import Path

import pytest

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


@pytest.mark.parametrize("excluded_name", ["dist", "node_modules", ".venv"])
@pytest.mark.parametrize("placement", ["ancestor", "root"])
def test_skip_rules_apply_only_below_the_explicit_scan_root(
    tmp_path: Path, excluded_name: str, placement: str
) -> None:
    baseline_root = tmp_path / "ordinary" / "project"
    selected_root = tmp_path / excluded_name
    if placement == "ancestor":
        selected_root /= "project"
    source = (
        'from fastapi import FastAPI\napp = FastAPI()\n@app.get("/health")\ndef health(): pass\n'
    )
    for root in (baseline_root, selected_root):
        root.mkdir(parents=True)
        (root / "main.py").write_text(source, encoding="utf-8")
        ignored = root / "nested" / excluded_name
        ignored.mkdir(parents=True)
        (ignored / "ignored.py").write_bytes(b"\xff")

    baseline = ScanRunner().run(baseline_root)
    selected = ScanRunner().run(selected_root)

    assert baseline.python_files == selected.python_files == 1
    assert baseline.parse_errors == selected.parse_errors == ()
    assert baseline.to_dict()["routes"] == selected.to_dict()["routes"]
    assert [route.path for route in selected.routes] == ["/health"]
    assert selected.routes[0].file == selected_root / "main.py"
