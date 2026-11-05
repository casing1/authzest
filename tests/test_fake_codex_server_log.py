"""Deterministic publication checks for the owned offline test log, not Codex."""

import json
from contextlib import contextmanager
from pathlib import Path

import pytest

from helpers import fake_codex_server as server
from test_codex_app_server import Fake

SEED = {"event": "start", "generation": 1}
SEED_BYTES = (json.dumps(SEED) + "\n").encode()


@pytest.fixture
def log(tmp_path, monkeypatch):
    path = tmp_path / "events.jsonl"
    monkeypatch.setattr(server, "SETTINGS", {"log": str(path)})
    return path


def reader(log):
    return Fake(log.parent / "unused-fake-executable", log)


def test_partial_snapshot_reproduces_legacy_polling_failure(log):
    log.write_bytes(SEED_BYTES + b'{"event": "sta')
    with pytest.raises(json.JSONDecodeError):
        [json.loads(line) for line in log.read_text().splitlines()]
    # An invalid published snapshot must remain an error, not a dropped event.
    with pytest.raises(ValueError):
        reader(log).events()


@pytest.mark.parametrize("existing", [False, True], ids=["first", "subsequent"])
def test_record_publishes_only_a_closed_complete_snapshot(log, monkeypatch, existing):
    if existing:
        log.write_bytes(SEED_BYTES)
    expected_before = [SEED] if existing else []
    observations = []
    replace = server.os.replace
    create = server.tempfile.NamedTemporaryFile
    streams = []

    def track_stream(*args, **kwargs):
        stream = create(*args, **kwargs)
        streams.append(stream)
        return stream

    def inspect_replace(source, destination):
        assert len(streams) == 1 and streams[0].closed
        source = Path(source)
        assert source.parent == log.parent and source != log
        assert Path(destination) == log
        observations.append(reader(log).events())
        with source.open("rb") as stream:
            candidate = stream.read()
        assert candidate.endswith(b"\n")
        assert candidate == (SEED_BYTES if existing else b"") + b'{"event": "next"}\n'
        replace(source, destination)

    monkeypatch.setattr(server.tempfile, "NamedTemporaryFile", track_stream)
    monkeypatch.setattr(server.os, "replace", inspect_replace)
    server.record("next")
    assert observations == [expected_before]
    assert reader(log).events() == [*expected_before, {"event": "next"}]
    assert list(log.parent.iterdir()) == [log]


@pytest.mark.parametrize("empty", [False, True], ids=["missing", "empty"])
def test_missing_and_empty_logs_have_no_events(log, empty):
    if empty:
        log.write_bytes(b"")
    assert reader(log).events() == []


def test_reader_preserves_utf8_and_literal_unicode_line_separator(log):
    event = {"event": "note", "text": "한글\u2028続き"}
    log.write_bytes((json.dumps(event, ensure_ascii=False) + "\n").encode())
    assert reader(log).events() == [event]


@pytest.mark.parametrize("tail", [b'{"event": "next"}', b'{"event":', b"\xe2\x82"])
def test_unterminated_published_record_is_rejected(log, tail):
    log.write_bytes(SEED_BYTES + tail)
    with pytest.raises(ValueError, match="Unterminated"):
        reader(log).events()


@pytest.mark.parametrize("data", [b"not-json\n", b"\n", SEED_BYTES + b'{"event":}\n'])
def test_complete_malformed_records_are_not_ignored(log, data):
    log.write_bytes(data)
    with pytest.raises(json.JSONDecodeError):
        reader(log).events()


@pytest.mark.parametrize("data", [b"\xff\n", SEED_BYTES + b"\xe2\x82\n"])
def test_complete_invalid_utf8_is_rejected(log, data):
    log.write_bytes(data)
    with pytest.raises(UnicodeDecodeError):
        reader(log).events()


def test_non_file_log_error_is_not_treated_as_empty(log):
    log.mkdir()
    with pytest.raises(IsADirectoryError):
        reader(log).events()


@pytest.mark.parametrize("fail_write", [False, True], ids=["split-write", "write-failure"])
@pytest.mark.parametrize("existing", [False, True], ids=["first", "subsequent"])
def test_partial_temporary_write_never_changes_published_log(
    log, monkeypatch, existing, fail_write
):
    before = SEED_BYTES if existing else b""
    if existing:
        log.write_bytes(before)
    sentinel = log.parent / "unrelated.txt"
    sentinel.write_bytes(b"keep")
    expected_before = [SEED] if existing else []
    snapshots = []
    create = server.tempfile.NamedTemporaryFile

    @contextmanager
    def split_file(*args, **kwargs):
        with create(*args, **kwargs) as stream:

            class SplitWriter:
                name = stream.name

                def write(self, data):
                    boundary = len(before) + 1
                    stream.write(data[:boundary])
                    stream.flush()
                    snapshots.append(reader(log).events())
                    assert Path(self.name).read_bytes() == data[:boundary]
                    if fail_write:
                        raise OSError("owned temporary write failed")
                    return boundary + stream.write(data[boundary:])

            yield SplitWriter()

    monkeypatch.setattr(server.tempfile, "NamedTemporaryFile", split_file)
    if fail_write:
        with pytest.raises(OSError, match="owned temporary write failed"):
            server.record("next")
        if existing:
            assert log.read_bytes() == before
        else:
            assert not log.exists()
    else:
        server.record("next")
        assert reader(log).events() == [*expected_before, {"event": "next"}]
    assert snapshots == [expected_before]
    assert sorted(path.name for path in log.parent.iterdir()) == (
        ["events.jsonl", "unrelated.txt"] if existing or not fail_write else ["unrelated.txt"]
    )
    assert sentinel.read_bytes() == b"keep"


@pytest.mark.parametrize("existing", [False, True], ids=["first", "subsequent"])
def test_replace_failure_preserves_previous_log_and_cleans_only_own_temp(
    log, monkeypatch, existing
):
    if existing:
        log.write_bytes(SEED_BYTES)
    sentinel = log.parent / "unrelated.txt"
    sentinel.write_bytes(b"keep")

    def fail_replace(source, destination):
        assert Path(source).is_file() and Path(destination) == log
        assert reader(log).events() == ([SEED] if existing else [])
        raise OSError("owned replacement failed")

    monkeypatch.setattr(server.os, "replace", fail_replace)
    with pytest.raises(OSError, match="owned replacement failed"):
        server.record("next")
    if existing:
        assert log.read_bytes() == SEED_BYTES
    else:
        assert not log.exists()
    assert sorted(path.name for path in log.parent.iterdir()) == (
        ["events.jsonl", "unrelated.txt"] if existing else ["unrelated.txt"]
    )
    assert sentinel.read_bytes() == b"keep"


@pytest.mark.parametrize(
    "data,error",
    [
        (b'{"event": "old"}', ValueError),
        (b'{"event":', ValueError),
        (b"bad\n", json.JSONDecodeError),
        (b"\xff\n", UnicodeDecodeError),
    ],
)
def test_writer_refuses_to_extend_a_corrupt_predecessor(log, monkeypatch, data, error):
    log.write_bytes(data)

    def unexpected_publish(*args):
        pytest.fail("A corrupt predecessor must not be replaced")

    monkeypatch.setattr(server.os, "replace", unexpected_publish)
    with pytest.raises(error):
        server.record("next")
    assert log.read_bytes() == data
    assert list(log.parent.iterdir()) == [log]
