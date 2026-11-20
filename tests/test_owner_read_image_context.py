"""Build only the maintained owner-read guest context without a Docker daemon."""

import hashlib
import io
import os
import tarfile

import pytest
from scripts import owner_read_image_context as context

pytestmark = pytest.mark.skipif(os.name != "posix", reason="POSIX image preparation")


def test_fixed_context_is_deterministic_and_contains_only_reviewed_sources():
    outputs = []
    for _ in range(2):
        stream = io.BytesIO()
        context.write_context(stream)
        outputs.append(stream.getvalue())
    assert outputs[0] == outputs[1]
    with tarfile.open(fileobj=io.BytesIO(outputs[0])) as archive:
        members = archive.getmembers()
        assert [m.name for m in members] == [name for name, _ in context._FILES]
        assert set(m.name for m in members if not m.name.startswith("package/")) == {
            "assets/guest.py",
            "assets/owner_read_kernel.py",
            "assets/_guest_common.py",
            "Dockerfile",
        }
        assert all(
            m.isfile() and (m.mode, m.mtime, m.uid, m.gid) == (0o444, 0, 0, 0) for m in members
        )
        for name, packaged in context._FILES:
            assert archive.extractfile(name).read() == (context._ROOT / packaged).read_bytes()
        sample = archive.extractfile("package/authzest/owner_read_demo/positive_regression.py")
        assert hashlib.sha256(sample.read()).hexdigest() == (
            "92e382cadcb9584b7e953b90955a0f0fee8f4cb16b89f649b1ca26fe807b57a4"
        )


@pytest.mark.parametrize("replacement", ["missing", "symlink", "hardlink", "too-large"])
def test_bad_source_fails_before_writing_any_context(tmp_path, monkeypatch, replacement):
    first = tmp_path / "first.py"
    first.write_bytes(b"a")
    second = tmp_path / "second.py"
    if replacement == "symlink":
        second.symlink_to(first)
    elif replacement == "hardlink":
        second.hardlink_to(first)
    elif replacement == "too-large":
        second.write_bytes(b"x" * 262145)
    monkeypatch.setattr(context, "_ROOT", tmp_path)
    monkeypatch.setattr(context, "_FILES", (("first", "first.py"), ("second", "second.py")))
    stream = io.BytesIO()
    with pytest.raises((ValueError, OSError)):
        context.write_context(stream)
    assert stream.getvalue() == b""
