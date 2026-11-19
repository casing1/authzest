"""Only maintained inert bytes are staged in disposable private roots."""

import hashlib
import os
import stat
from importlib.resources import files
from pathlib import Path

import pytest

from authzest.codex.contracts import ContractError
from authzest.runner import _owner_read_copy_files as copy

pytestmark = pytest.mark.skipif(not copy.copy_supported(), reason="POSIX source copies only")

BASELINE = files("authzest.owner_read_demo").joinpath("availability.py").read_bytes()
TEST = (
    b"def test_owner_archived_note(owner_client):\n"
    b'    assert owner_client.get("/records/archived-note").status_code == 200\n'
)
PROPOSED = (
    b'def available_to_owner(state: str) -> bool:\n    return state in ("active", "archived")\n'
)


@pytest.fixture(autouse=True)
def private_parent(tmp_path, monkeypatch):
    monkeypatch.setattr(copy, "_TEMP_PARENT", tmp_path)


def stage(guard=lambda: None):
    return copy.stage_private_copy(BASELINE, TEST, PROPOSED, guard=guard)


def test_exact_contents_permissions_unique_paths_and_short_writes(tmp_path, monkeypatch):
    monkeypatch.setenv("TMPDIR", str(tmp_path / "ignored"))
    real_write = os.write
    monkeypatch.setattr(os, "write", lambda fd, data: real_write(fd, data[:7]))
    calls = []
    paths = []
    for _ in range(2):
        result = stage(lambda: calls.append(True))
        assert result["status"] == "prepared" and result["exit_code"] == 0
        path = Path(result["path"])
        paths.append(path)
        assert path.parent == tmp_path and stat.S_IMODE(path.stat().st_mode) == 0o700
        assert set(f.name for f in path.iterdir()) == set(copy.FILES)
        for name, data in zip(copy.FILES, (BASELINE, TEST, PROPOSED), strict=True):
            file = path / name
            assert stat.S_IMODE(file.stat().st_mode) == 0o600 and file.read_bytes() == data
            assert result["files"][name]["state"] == "verified"
            assert result["files"][name]["sha256"] == hashlib.sha256(data).hexdigest()
            assert result["files"][name]["identity"][:2] == [file.stat().st_dev, file.stat().st_ino]
    assert paths[0] != paths[1] and calls == [True, True]


def test_expired_decision_has_no_files(tmp_path):
    def expire():
        raise TimeoutError

    with pytest.raises(TimeoutError):
        stage(expire)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "baseline,test,proposed",
    [
        (b"different", TEST, PROPOSED),
        (BASELINE, TEST, BASELINE),
        (BASELINE, b"\xff", PROPOSED),
        (BASELINE, TEST, b"x" * 4097),
        (BASELINE, b"def broken", PROPOSED),
    ],
)
def test_invalid_bindings_never_reach_dispatch(tmp_path, baseline, test, proposed):
    with pytest.raises((ValueError, ContractError)):
        copy.stage_private_copy(baseline, test, proposed, guard=lambda: pytest.fail("dispatch"))
    assert list(tmp_path.iterdir()) == []


def test_existing_directory_is_never_opened_or_overwritten(monkeypatch, tmp_path):
    monkeypatch.setattr(copy.secrets, "token_hex", lambda _: "fixed")
    existing = tmp_path / "authzest-owner-read-fixed"
    existing.mkdir(mode=0o700)
    original = existing / "availability.py"
    original.write_bytes(b"existing")
    result = stage()
    assert result["status"] == "creation-failed" and result["path"] is None
    assert original.read_bytes() == b"existing" and list(existing.iterdir()) == [original]


@pytest.mark.parametrize("cause", [KeyboardInterrupt, SystemExit, OSError])
def test_partial_write_retains_private_path_and_progress(monkeypatch, cause):
    def interrupt(_fd, _data):
        raise cause

    monkeypatch.setattr(os, "write", interrupt)
    result = stage()
    assert result["status"] == "incomplete" and result["exit_code"] == 1
    assert result["interrupted"] == (cause is not OSError)
    path = Path(result["path"])
    first = path / copy.FILES[0]
    assert first.read_bytes() == b"" and list(path.iterdir()) == [first]
    assert result["files"][copy.FILES[0]] == {"state": "created-unconfirmed"}
    assert result["files"][copy.FILES[1]] == {"state": "not-created"}


@pytest.mark.parametrize("replacement", ["symlink", "fifo", "same-bytes", "extra", "edit-earlier"])
def test_changed_copy_never_reports_success(monkeypatch, replacement, tmp_path):
    real = copy._verify_file

    def change(root, name, data, identity):
        if name == copy.FILES[-1]:
            path = next(tmp_path.iterdir())
            target = path / name
            if replacement in {"symlink", "fifo", "same-bytes"}:
                # Keep the original inode live to guarantee that even identical replacements differ.
                target.rename(path / "original")
                if replacement == "symlink":
                    target.symlink_to(path / "original")
                elif replacement == "fifo":
                    os.mkfifo(target, mode=0o600)
                else:
                    target.write_bytes(data)
                    target.chmod(0o600)
            elif replacement == "extra":
                (path / "extra").touch()
            else:
                (path / copy.FILES[0]).write_bytes(b"operator edit")
        return real(root, name, data, identity)

    monkeypatch.setattr(copy, "_verify_file", change)
    result = stage()
    assert result["status"] == "incomplete" and result["stage"] == "verify-copy"
    assert all("sha256" not in entry for entry in result["files"].values())
    if replacement == "edit-earlier":
        assert (Path(result["path"]) / copy.FILES[0]).read_bytes() == b"operator edit"


def test_failed_mkdir_does_not_claim_a_retained_directory(monkeypatch, tmp_path):
    def refuse(*args, **kwargs):
        raise PermissionError("refused")

    monkeypatch.setattr(copy, "copy_supported", lambda: True)
    monkeypatch.setattr(os, "mkdir", refuse)
    result = stage()
    assert result["status"] == "creation-failed" and result["path"] is None
    assert result["stage"] == "create-directory" and list(tmp_path.iterdir()) == []
