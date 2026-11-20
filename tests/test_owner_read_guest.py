"""Guest protocol with fixed, maintainer-written samples only. No Docker or provider."""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from runtime.owner_read import guest

from authzest.codex.contracts import ContractError
from authzest.owner_read_demo import rehearsal
from authzest.owner_read_demo.checks import compare_owner_read_observations

_RULE = Path(rehearsal.__file__).with_name("availability.py").read_bytes()
_REFERENCE = (
    b'def available_to_owner(state: str) -> bool:\n    return state in ("active", "archived")\n'
)
_MAINTAINED_TEST = (
    b"def test_package_owner_archive(owner_client):\n"
    b'    observed = owner_client.get("/records/archived-note")\n'
    b"    assert observed.status_code == 200\n"
)


def _sha(data):
    return hashlib.sha256(data).hexdigest()


@pytest.fixture
def staged(tmp_path, monkeypatch):
    # Only this temporary fixture supplies alternative paths; the product accepts neither.
    rule = tmp_path / "availability.py"
    test = tmp_path / "test_owner_archived_read.py"
    monkeypatch.setattr(guest, "_RULE", rule)
    monkeypatch.setattr(guest, "_TEST", test)

    def stage(source=_RULE, sample=_MAINTAINED_TEST):
        rule.write_bytes(source)
        test.write_bytes(sample)
        return json.dumps({"source_sha256": _sha(source), "test_sha256": _sha(sample)}).encode()

    return stage


@pytest.mark.parametrize(("source", "matches"), [(_RULE, 6), (_REFERENCE, 7)])
def test_guest_checks_independently_match_real_fixed_profile(staged, monkeypatch, source, matches):
    # A non-Python ASCII note cannot be collected; the controls role binds its digest only.
    manifest = staged(source=source, sample=b"maintainer note; never imported")
    monkeypatch.setattr(guest, "_test_observation", lambda *_: pytest.fail("unexpected test"))
    result = guest._observe("controls", manifest)
    assert result.keys() == {
        "kind",
        "schema_version",
        "role",
        "source_sha256",
        "test_sha256",
        "observations",
    }
    assert result["role"] == "controls"
    assert result["source_sha256"] == _sha(source)
    assert result["test_sha256"] == _sha(b"maintainer note; never imported")
    assert compare_owner_read_observations(result["observations"])["intended_matches"] == matches


@pytest.mark.parametrize(
    ("source", "outcome", "status"), [(_RULE, "assertion-failed", 403), (_REFERENCE, "passed", 200)]
)
def test_single_item_uses_approved_bytecode_in_fresh_process(
    staged, source, outcome, status, tmp_path
):
    # The child uses only these two checked-in, human-authored byte strings.
    manifest = staged(source).decode()
    child = """
import json, sys
from pathlib import Path
sys.path[:0] = sys.argv[1:3]
from runtime.owner_read import guest
guest._RULE = Path.cwd() / 'availability.py'
guest._TEST = Path.cwd() / 'test_owner_archived_read.py'
print(json.dumps(guest._observe('test', sys.argv[3].encode())))
"""
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            "-c",
            child,
            str(Path(guest.__file__).resolve().parents[2]),
            str(Path(rehearsal.__file__).resolve().parents[2]),
            manifest,
        ],
        cwd=tmp_path,
        env={k: os.environ[k] for k in ("SYSTEMROOT",) if k in os.environ},
        capture_output=True,
        check=True,
        timeout=20,
    )
    record = json.loads(result.stdout)
    assert record.keys() == {
        "schema_version",
        "kind",
        "role",
        "source_sha256",
        "test_sha256",
        "regression",
    }
    assert record["kind"] == "owner-read-guest-observation" and record["role"] == "test"
    assert record["test_sha256"] == _sha(_MAINTAINED_TEST) and record["source_sha256"] == _sha(
        source
    )
    assert record["regression"] == {
        "status": outcome,
        "pytest_exit": int(status == 403),
        "collected": 1,
        "setup": "passed",
        "call": "failed" if status == 403 else "passed",
        "teardown": "passed",
        "requests": 1,
        "response": {
            "status_code": status,
            "body": (
                {"detail": "Read denied"}
                if status == 403
                else {"id": "archived-note", "title": "Archived note"}
            ),
        },
    }


@pytest.mark.parametrize("role", ["test", "controls"])
@pytest.mark.parametrize("which", ["source_sha256", "test_sha256"])
def test_both_role_hashes_are_mandatory(staged, monkeypatch, role, which):
    identities = json.loads(staged())
    identities[which] = "0" * 64
    monkeypatch.setattr(guest, "_test_observation", lambda *_: pytest.fail("unexpected execution"))
    with pytest.raises(ValueError, match="identity changed"):
        guest._observe(role, json.dumps(identities).encode())


@pytest.mark.parametrize(
    "raw",
    [
        b"{}",
        b"[]",
        b" " * 1025,
        b'{"source_sha256":null,"test_sha256":null}',
        b'{"a":1,"a":2}',
        b"\xff",
    ],
)
def test_malformed_manifest_is_refused(raw):
    with pytest.raises((ValueError, ContractError)):
        guest._identities(raw)


def test_wrong_role_and_out_of_grammar_test_are_refused(staged, monkeypatch):
    wrong = staged(sample=b"def test_other():\n    pass\n")
    monkeypatch.setattr(guest, "_test_observation", lambda *_: pytest.fail("unexpected execution"))
    with pytest.raises(ValueError, match="Unsupported role"):
        guest._observe("other", wrong)
    with pytest.raises(ContractError):
        guest._observe("test", wrong)


@pytest.mark.skipif(not hasattr(os, "O_NOFOLLOW"), reason="POSIX guest only")
def test_links_and_oversize_files_are_refused(staged, tmp_path):
    ids = json.loads(staged())
    old = tmp_path / "old"
    guest._RULE.rename(old)
    guest._RULE.symlink_to(old)
    with pytest.raises(OSError):
        guest._read_fixed(guest._RULE, ids["source_sha256"])
    guest._RULE.unlink()
    guest._RULE.write_bytes(b"x" * 4097)
    with pytest.raises(ValueError):
        guest._read_fixed(guest._RULE, _sha(b"x" * 4097))


def test_real_entry_refuses_checkout_and_unsupported_guard(monkeypatch, capsys):
    assert not guest._permitted_entry()
    monkeypatch.setattr(guest, "_observe", lambda *_: pytest.fail("unexpected execution"))
    assert guest.main() == 64
    monkeypatch.setattr(guest, "_permitted_entry", lambda: True)
    monkeypatch.setattr(sys, "path", list(sys.path))

    def refuse():
        raise RuntimeError("unexpected local detail")

    monkeypatch.setitem(
        sys.modules, "owner_read_kernel", SimpleNamespace(require_guest_controls=refuse)
    )
    assert guest.main() == 78
    capture = capsys.readouterr()
    assert capture.out == "" and capture.err == "owner-read-isolation-refused\n"
