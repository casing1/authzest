"""Owned temporary inputs only; no target execution or provider calls."""

import os
from dataclasses import FrozenInstanceError
from hashlib import sha256

import pytest

from authzest.analyzer import repository_input as loader


@pytest.fixture
def repo(tmp_path):
    if not loader._supported():
        pytest.skip("POSIX descriptor-based input capture required")
    root = tmp_path.resolve() / "external"
    root.mkdir()
    (root / "app.py").write_text(
        'raise RuntimeError("This source must never execute")\n', encoding="utf-8"
    )
    (root / "POLICY.md").write_text("Only an authenticated owner may read an item.\n")
    return root


def capture(repo, **kwargs):
    return loader.capture_repository(repo, "app.py", "POLICY.md", **kwargs)


def test_selected_source_is_inert_and_absolute_root_is_not_in_shared_data(repo):
    (repo / "unselected.py").write_bytes(b"\x00invalid unselected source")
    (repo / ".env").write_text("SECRET=do-not-read")
    raw = (repo / "app.py").read_bytes()
    value = capture(repo)
    assert value.root == repo
    assert value.source == "app.py" and value.policy == "POLICY.md" and value.contexts == ()
    assert [file.path for file in value.files] == ["app.py", "POLICY.md"]
    assert value.files[0].text.encode() == raw
    assert value.files[0].sha256 == sha256(raw).hexdigest()
    assert value.files[0].to_dict() == {
        "path": "app.py",
        "text": raw.decode(),
        "sha256": sha256(raw).hexdigest(),
    }
    assert "root" not in value.to_dict()
    assert str(repo) not in str(value.to_dict())
    with pytest.raises(FrozenInstanceError):
        value.source = "other.py"


def test_nested_context_and_empty_package_source_are_explicitly_captured(repo):
    (repo / "api").mkdir()
    (repo / "api" / "__init__.py").write_bytes(b"")
    (repo / "api" / "auth.py").write_text('OWNER = "alice"\n')
    value = capture(repo, contexts=("api/auth.py", "api/__init__.py"))
    assert [file.path for file in value.files] == [
        "app.py",
        "POLICY.md",
        "api/auth.py",
        "api/__init__.py",
    ]
    assert value.to_dict()["contexts"] == ["api/auth.py", "api/__init__.py"]
    assert value.files[-1].text == ""


@pytest.mark.parametrize(
    "path",
    [
        "",
        "/app.py",
        "../app.py",
        "api/../app.py",
        "./app.py",
        "api//app.py",
        "api/./app.py",
        "api/",
        r"api\app.py",
        ".env.py",
        ".git/a.py",
        "api/.auth.py",
        "app.py\n",
        "app\x00.py",
        "app\u202e.py",
        "app\ud800.py",
        "app.txt",
        "a" * 513 + ".py",
        "/".join(["api"] * 16 + ["app.py"]),
        None,
    ],
)
def test_source_path_refusals_are_redacted(repo, path):
    with pytest.raises(loader.RepositoryInputError, match="selection-invalid") as error:
        loader.capture_repository(repo, path, "POLICY.md")
    assert str(repo) not in str(error.value)


@pytest.mark.parametrize("policy", ["app.py", ".env", "policy.json", "../POLICY.md"])
def test_policy_requires_an_explicit_nonhidden_text_path(repo, policy):
    with pytest.raises(loader.RepositoryInputError, match="selection-invalid"):
        loader.capture_repository(repo, "app.py", policy)


@pytest.mark.parametrize("contexts", [("app.py",), ("a.py", "a.py"), ("a.py",) * 5, ["a.py"]])
def test_duplicate_and_overbudget_context_selections_are_rejected(repo, contexts):
    with pytest.raises(loader.RepositoryInputError, match="selection-invalid"):
        capture(repo, contexts=contexts)


@pytest.mark.parametrize("member", ["app.py", "POLICY.md"])
def test_selected_symlink_is_never_followed(repo, member):
    target = repo.parent / "outside.txt"
    target.write_text("private outside content")
    (repo / member).unlink()
    (repo / member).symlink_to(target)
    with pytest.raises(loader.RepositoryInputError, match="unavailable") as error:
        capture(repo)
    assert str(target) not in str(error.value)


def test_root_and_nested_parent_symlinks_are_rejected(repo):
    alias = repo.parent / "alias"
    alias.symlink_to(repo, target_is_directory=True)
    with pytest.raises(loader.RepositoryInputError, match="unavailable"):
        capture(alias)
    (repo / "api").symlink_to(repo, target_is_directory=True)
    with pytest.raises(loader.RepositoryInputError, match="unavailable"):
        capture(repo, contexts=("api/app.py",))


def test_fifo_and_hardlink_are_rejected_without_reading(repo, monkeypatch):
    def no_read(*args):
        pytest.fail("Nonregular selected file was read")

    monkeypatch.setattr(loader, "_read", no_read)
    (repo / "app.py").unlink()
    os.mkfifo(repo / "app.py")
    with pytest.raises(loader.RepositoryInputError, match="regular-file-required"):
        capture(repo)
    (repo / "app.py").unlink()
    os.link(repo / "POLICY.md", repo / "app.py")
    with pytest.raises(loader.RepositoryInputError, match="regular-file-required"):
        capture(repo)


@pytest.mark.parametrize(
    "member,limit", [("app.py", loader.MAX_SOURCE_BYTES), ("POLICY.md", loader.MAX_POLICY_BYTES)]
)
def test_oversized_files_are_rejected_before_reading(repo, monkeypatch, member, limit):
    (repo / member).write_bytes(b"x" * (limit + 1))
    real_read = loader._read
    read_limits = []

    def measured(fd, cap):
        read_limits.append(cap)
        return real_read(fd, cap)

    monkeypatch.setattr(loader, "_read", measured)
    with pytest.raises(loader.RepositoryInputError, match="size-limit"):
        capture(repo)
    assert len(read_limits) == (0 if member == "app.py" else 1)


def test_aggregate_byte_budget_and_context_count_bound_total_capture(repo):
    (repo / "app.py").write_bytes(b"x" * loader.MAX_SOURCE_BYTES)
    contexts = tuple(f"context{i}.py" for i in range(4))
    for name in contexts:
        (repo / name).write_bytes(b"x" * loader.MAX_SOURCE_BYTES)
    with pytest.raises(loader.RepositoryInputError, match="size-limit"):
        capture(repo, contexts=contexts)


@pytest.mark.parametrize("raw", [b"\xff", b"text\x00text"])
def test_invalid_utf8_and_nul_text_are_refused(repo, raw):
    (repo / "app.py").write_bytes(raw)
    with pytest.raises(loader.RepositoryInputError):
        capture(repo)


def test_blank_policy_is_refused(repo):
    (repo / "POLICY.md").write_text(" \n\t")
    with pytest.raises(loader.RepositoryInputError, match="text-invalid"):
        capture(repo)


def test_changed_selected_bytes_are_detected_while_other_inputs_are_captured(repo, monkeypatch):
    read = loader._read
    calls = 0

    def edit_first_after_second_read(fd, limit):
        nonlocal calls
        raw = read(fd, limit)
        calls += 1
        if calls == 2:
            (repo / "app.py").write_text("changed = True\n")
        return raw

    monkeypatch.setattr(loader, "_read", edit_first_after_second_read)
    with pytest.raises(loader.RepositoryInputError, match="changed"):
        capture(repo)


def test_selected_parent_replacement_is_detected(repo, monkeypatch):
    (repo / "api").mkdir()
    (repo / "api" / "auth.py").write_text("guard = True\n")
    read = loader._read
    calls = 0

    def replace_parent_after_capture(fd, limit):
        nonlocal calls
        raw = read(fd, limit)
        calls += 1
        if calls == 3:
            (repo / "api").rename(repo / "old-api")
            (repo / "api").mkdir()
            (repo / "api" / "auth.py").write_bytes(raw)
        return raw

    monkeypatch.setattr(loader, "_read", replace_parent_after_capture)
    with pytest.raises(loader.RepositoryInputError, match="changed"):
        capture(repo, contexts=("api/auth.py",))


def test_file_growth_read_is_capped_at_limit_plus_one(repo, monkeypatch):
    reads = []

    def grow(fd, size, offset):
        reads.append(size)
        return b"x" * size

    monkeypatch.setattr(loader.os, "pread", grow)
    with pytest.raises(loader.RepositoryInputError, match="size-limit"):
        capture(repo)
    assert sum(reads) == loader.MAX_SOURCE_BYTES + 1


def test_unsupported_platform_is_refused_before_any_file_read(monkeypatch):
    monkeypatch.setattr(loader, "_supported", lambda: False)
    with pytest.raises(loader.RepositoryInputError, match="platform-unsupported"):
        loader.capture_repository(None, "app.py", "POLICY.md")


@pytest.mark.parametrize("fail", [False, True])
def test_all_held_descriptors_are_closed_on_success_and_input_failure(repo, monkeypatch, fail):
    opened = []
    real_open = loader.os.open

    def track(*args, **kwargs):
        fd = real_open(*args, **kwargs)
        opened.append(fd)
        return fd

    monkeypatch.setattr(loader.os, "open", track)
    if fail:
        (repo / "POLICY.md").write_bytes(b"\xff")
        with pytest.raises(loader.RepositoryInputError):
            capture(repo)
    else:
        capture(repo)
    assert opened
    for fd in opened:
        with pytest.raises(OSError):
            os.fstat(fd)


def test_crlf_unicode_and_policy_bytes_remain_exact(repo):
    raw = '# 주석\r\nvalue = "한글"\r\n'.encode()
    (repo / "app.py").write_bytes(raw)
    value = capture(repo)
    assert value.files[0].text.encode() == raw
    assert value.files[0].sha256 == sha256(raw).hexdigest()


def test_root_control_characters_and_missing_inputs_use_closed_errors(repo):
    with pytest.raises(loader.RepositoryInputError, match="root-invalid"):
        capture(repo / "bad\x00private")
    (repo / "app.py").unlink()
    with pytest.raises(loader.RepositoryInputError, match="unavailable") as error:
        capture(repo)
    assert str(repo) not in str(error.value)


def test_unavailable_home_expansion_does_not_expose_private_root(repo, monkeypatch):
    def missing_home(_path):
        raise RuntimeError("private-account-name")

    monkeypatch.setattr(loader.Path, "expanduser", missing_home)
    with pytest.raises(loader.RepositoryInputError, match="root-invalid") as error:
        capture(repo)
    assert "private-account-name" not in str(error.value)
