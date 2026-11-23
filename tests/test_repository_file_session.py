"""Own inert bytes and fake clocks only; no app, test, model or guest is executed."""

import copy
import json
import os
import pickle
from contextlib import suppress
from dataclasses import asdict
from pathlib import Path

import pytest

from authzest.analyzer.repository_origin import RepositoryOriginError, capture_repository_origin
from authzest.codex.repository_copy_plan import prepare_repository_copy_plan
from authzest.codex.repository_proposal import TEST_PATH, build_repository_request
from authzest.runner import repository_file_session as module
from authzest.runner.repository_file_session import (
    RepositoryFileDecision,
    RepositoryFilePlan,
    RepositoryFileSession,
    RepositorySessionEffectError,
    RepositorySessionError,
)

pytestmark = pytest.mark.skipif(
    os.name != "posix", reason="POSIX source-only private file boundary"
)

SOURCE = (
    "from fastapi import FastAPI\napp = FastAPI()\n"
    '@app.get("/items/{item_id}")\n'
    'def read(item_id: str):\n    return {"id": item_id}\n'
    'raise RuntimeError("INERT SOURCE MUST NEVER EXECUTE")\n'
)
AFTER = SOURCE.replace('{"id": item_id}', '{"id": item_id, "checked": True}')
TEST = 'raise RuntimeError("INERT GENERATED TEST MUST NEVER EXECUTE")\n'


class Clock:
    def __init__(self):
        self.value = 10.0

    def __call__(self):
        return self.value


@pytest.fixture
def setup(tmp_path):
    root = (tmp_path / "origin").resolve()
    (root / "pkg").mkdir(parents=True)
    (root / "pkg/app.py").write_text(SOURCE)
    (root / "pkg/__init__.py").write_bytes(b"")
    (root / "auth.py").write_bytes('ROLE = "소유자"\r\n'.encode())
    (root / "policy.md").write_text("Only the authenticated owner may read an item.\n")
    parent = (tmp_path / "private").resolve()
    parent.mkdir(mode=0o700)
    sessions = []

    def create(*, clock=None):
        origin = capture_repository_origin(
            root, "pkg/app.py", "policy.md", ("pkg/__init__.py", "auth.py")
        )
        request = build_repository_request(origin.snapshot, "offline-model")
        response = dict(
            schema_version="1.0",
            request_id=request.request_id,
            status="proposed-change",
            rationale="Inert file transition, not a verified repair.",
            assumptions=["Only synthetic owned files are used."],
            uncertainties=["No runtime observation."],
            limitations=["No execution or authorization assurance."],
            proposal=dict(
                source_path="pkg/app.py",
                before_sha256=request.to_dict()["selection"]["files"][0]["sha256"],
                after_text=AFTER,
                test_path=TEST_PATH,
                test_text=TEST,
            ),
        )
        copy_plan = prepare_repository_copy_plan(request, response)
        clock = clock or Clock()
        session = RepositoryFileSession(
            origin, request, response, copy_plan, _clock=clock, _parent=parent
        )
        sessions.append(session)
        return session, origin, clock, request, response, copy_plan

    yield root, parent, create
    for session in sessions:
        with suppress(RepositorySessionError):
            session.close()


def perform(session, step):
    plan = session.prepare(step)
    decision = session.decide(plan, plan.to_dict()["confirmation"])
    return session.perform(decision)


def copy_ready(create):
    session, origin, clock, *rest = create()
    result = perform(session, "copy")
    return session, Path(result["private_root"]), origin, clock, rest


def apply_ready(create):
    session, path, origin, clock, rest = copy_ready(create)
    perform(session, "accept-diff")
    return session, path, origin, clock, rest


def test_complete_private_flow_preserves_original_test_context_and_exact_before(setup):
    root, parent, create = setup
    original = {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    session, origin, _, *_ = create()
    assert list(parent.iterdir()) == []
    assert session.result()["source_observation"]["status"] == "not-copied"
    result = perform(session, "copy")
    path = Path(result["private_root"])
    assert (path / "project/pkg/app.py").read_bytes() == SOURCE.encode()
    assert (path / "project/pkg/__init__.py").read_bytes() == b""
    assert (path / "project/auth.py").read_bytes() == original[Path("auth.py")]
    assert (path / ("project/" + TEST_PATH)).read_bytes() == TEST.encode()
    perform(session, "accept-diff")
    perform(session, "apply")
    assert (path / "project/pkg/app.py").read_bytes() == AFTER.encode()
    result = perform(session, "restore")
    assert (path / "project/pkg/app.py").read_bytes() == SOURCE.encode()
    assert (path / ("project/" + TEST_PATH)).read_bytes() == TEST.encode()
    assert {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()} == original
    record = json.loads((path / "record.json").read_text())
    assert record["state"] == result["state"] == "restored-before"
    assert record["revision"] == 4
    assert record["pending_operation"] is None
    assert (
        record["file_identities"]["project/pkg/app.py"][1]
        == (path / "project/pkg/app.py").stat().st_ino
    )
    assert record["last_confirmed_source"] == "restored-before"
    assert record["verified_fix"] is result["verified_fix"] is False
    assert record["execution_status"] == result["execution_status"] == "not-run"
    assert result["authorization_status"] == "unknown"
    assert result["original_write"] == "not-supported"
    assert [h["step"] for h in result["history"]] == ["copy", "accept-diff", "apply", "restore"]
    session.close()
    assert session.closed and origin.closed and path.is_dir()
    assert session.result()["descriptor_cleanup"] == "confirmed"


def test_plan_contains_exact_current_review_and_repeated_prepare_keeps_deadline(setup):
    root, _, create = setup
    session, _, clock, request, response, _ = create()
    plan = session.prepare("copy")
    data = plan.to_dict()
    assert data["review"]["selection"] == request.to_dict()["selection"]
    assert data["review"]["response"] == response
    assert data["origin_root"] == str(root)
    assert SOURCE in data["review"]["selection"]["files"][0]["text"]
    assert "checked" in data["review"]["diffs"][0]["diff"]
    clock.value += 50
    assert session.prepare("copy") is plan
    assert plan.to_dict()["expires_at"] == data["expires_at"]
    assert data["expires_at"] - data["issued_at"] <= 300
    data["confirmation"] = "forged"
    assert plan.to_dict()["confirmation"] != "forged"


def test_saved_plan_forged_decision_and_cross_session_objects_never_authorize(setup):
    _, parent, create = setup
    first, *_ = create()
    second, *_ = create()
    plan = first.prepare("copy")
    with pytest.raises(RepositorySessionError):
        first.decide(RepositoryFilePlan(plan.payload_json), plan.to_dict()["confirmation"])
    with pytest.raises(RepositorySessionError):
        second.decide(plan, plan.to_dict()["confirmation"])
    decision = first.decide(plan, plan.to_dict()["confirmation"])
    with pytest.raises(RepositorySessionError):
        first.decide(plan, plan.to_dict()["confirmation"])
    with pytest.raises(RepositorySessionError):
        first.perform(RepositoryFileDecision(**asdict(decision)))
    with pytest.raises(RepositorySessionError):
        second.perform(decision)
    assert list(parent.iterdir()) == []
    first.perform(decision)
    with pytest.raises(RepositorySessionError):
        first.perform(decision)
    assert len(list(parent.iterdir())) == 1


@pytest.mark.parametrize("step", ["apply", "restore", "accept-diff", "invalid", None, []])
def test_out_of_order_or_invalid_steps_have_no_effect(setup, step):
    _, parent, create = setup
    session, *_ = create()
    with pytest.raises(RepositorySessionError):
        session.prepare(step)
    assert list(parent.iterdir()) == []
    assert session.state == "captured"


def test_wrong_phrase_and_expired_review_cannot_reset_or_create_copy(setup):
    _, parent, create = setup
    session, _, clock, *_ = create()
    plan = session.prepare("copy")
    with pytest.raises(RepositorySessionError):
        session.decide(plan, "wrong phrase")
    clock.value = plan.to_dict()["expires_at"]
    with pytest.raises(RepositorySessionError, match="expired"):
        session.prepare("copy")
    assert session.state == "refused"
    assert session.result()["failure"]["status"] == "expired-not-extended"
    with pytest.raises(RepositorySessionError, match="unavailable"):
        session.decide(plan, plan.to_dict()["confirmation"])
    assert list(parent.iterdir()) == []


@pytest.mark.parametrize("value", [True, float("nan"), float("inf"), -1, None, "10"])
def test_invalid_clock_latches_refusal_without_allocation(setup, value):
    _, parent, create = setup
    session, _, clock, *_ = create()
    clock.value = value
    with pytest.raises(RepositorySessionError, match="clock"):
        session.prepare("copy")
    assert session.state == "refused" and list(parent.iterdir()) == []
    clock.value = 10
    with pytest.raises(RepositorySessionError):
        session.prepare("copy")


def test_deadline_rounding_and_unrepresentable_deadline_do_not_extend_authority(setup):
    _, parent, create = setup
    session, _, clock, *_ = create()
    clock.value = 1e17
    data = session.prepare("copy").to_dict()
    assert 0 < data["expires_at"] - data["issued_at"] <= 300
    second, _, clock2, *_ = create()
    clock2.value = 1e308
    with pytest.raises(RepositorySessionError, match="representable"):
        second.prepare("copy")
    assert list(parent.iterdir()) == []


@pytest.mark.parametrize("edit", ["bytes", "same-bytes-replacement", "policy"])
def test_origin_drift_after_decision_refuses_copy(setup, edit):
    root, parent, create = setup
    session, *_ = create()
    plan = session.prepare("copy")
    decision = session.decide(plan, plan.to_dict()["confirmation"])
    source = root / "pkg/app.py"
    if edit == "bytes":
        source.write_text(SOURCE + "# changed\n")
    elif edit == "policy":
        (root / "policy.md").write_text("Different intent.\n")
    else:
        changed = root / "pkg/replacement.py"
        changed.write_bytes(source.read_bytes())
        changed.replace(source)
    with pytest.raises(RepositorySessionError):
        session.perform(decision)
    assert session.state == "refused" and list(parent.iterdir()) == []


def test_original_drift_and_closed_origin_after_copy_do_not_prevent_private_restore(setup):
    root, _, create = setup
    session, path, origin, _, _ = apply_ready(create)
    perform(session, "apply")
    (root / "pkg/app.py").write_text("# later original user edit\n")
    (root / "policy.md").unlink()
    origin.close()
    perform(session, "restore")
    assert (path / "project/pkg/app.py").read_bytes() == SOURCE.encode()
    assert (root / "pkg/app.py").read_text() == "# later original user edit\n"


@pytest.mark.parametrize(
    "relative",
    ["project/pkg/app.py", "evidence/source.before", "record.json", "project/" + TEST_PATH],
)
def test_private_edits_block_apply_without_overwriting_user_content(setup, relative):
    _, _, create = setup
    session, path, *_ = apply_ready(create)
    changed = path / relative
    changed.write_bytes(b"# private user edit\n")
    with pytest.raises(RepositorySessionError):
        session.prepare("apply")
    assert changed.read_bytes() == b"# private user edit\n"
    assert session.state == "recovery-required"


def test_late_expiry_after_durable_intent_never_replaces_source(setup, monkeypatch):
    _, _, create = setup
    session, path, _, clock, _ = apply_ready(create)
    plan = session.prepare("apply")
    decision = session.decide(plan, plan.to_dict()["confirmation"])
    original = module.RepositoryFiles.replace

    def expire_after_intent(files, name, data, *, guard):
        original(files, name, data, guard=guard)
        if name == "record.json" and json.loads(data)["pending_operation"] == "apply":
            clock.value = plan.to_dict()["expires_at"]

    monkeypatch.setattr(module.RepositoryFiles, "replace", expire_after_intent)
    with pytest.raises(RepositorySessionEffectError) as caught:
        session.perform(decision)
    assert (path / "project/pkg/app.py").read_bytes() == SOURCE.encode()
    assert json.loads((path / "record.json").read_text())["pending_operation"] == "apply"
    result = caught.value.result
    assert result["state"] == "recovery-required"
    assert result["failure"]["phase"] == "source-replacement"
    assert result["failure"]["commit_attempted"] is False
    with pytest.raises(RepositorySessionError):
        session.prepare("restore")


def test_completion_expiry_preserves_confirmed_after_and_reports_failed_journal(setup, monkeypatch):
    _, _, create = setup
    session, path, _, clock, _ = apply_ready(create)
    plan = session.prepare("apply")
    decision = session.decide(plan, plan.to_dict()["confirmation"])
    original = module.RepositoryFiles.replace

    def expire_after_source(files, name, data, *, guard):
        original(files, name, data, guard=guard)
        if name == "project/pkg/app.py":
            clock.value = plan.to_dict()["expires_at"]

    monkeypatch.setattr(module.RepositoryFiles, "replace", expire_after_source)
    with pytest.raises(RepositorySessionEffectError) as caught:
        session.perform(decision)
    result = caught.value.result
    assert result["source_observation"]["status"] == "after"
    assert result["state"] == "recovery-required"
    assert result["failure"]["phase"] == "completion-journal"
    assert (path / "project/pkg/app.py").read_bytes() == AFTER.encode()
    assert json.loads((path / "record.json").read_text())["pending_operation"] == "apply"


def test_intent_failure_prevents_source_dispatch_and_keeps_failure_metadata(setup, monkeypatch):
    _, _, create = setup
    session, path, *_ = apply_ready(create)
    plan = session.prepare("apply")
    decision = session.decide(plan, plan.to_dict()["confirmation"])

    def fail(*args, **kwargs):
        raise OSError("private failure text must not be exported")

    monkeypatch.setattr(module.RepositoryFiles, "replace", fail)
    with pytest.raises(RepositorySessionEffectError) as caught:
        session.perform(decision)
    assert (path / "project/pkg/app.py").read_bytes() == SOURCE.encode()
    assert caught.value.result["failure"]["phase"] == "intent-journal"
    assert "private failure text" not in json.dumps(caught.value.result)
    assert caught.value.result["verified_fix"] is False


def test_caller_response_edits_cannot_change_frozen_source_or_current_plan(setup):
    _, _, create = setup
    session, _, _, _, response, *_ = create()
    response["proposal"]["after_text"] = "raise SystemExit('MUTATED')\n"
    response["rationale"] = "mutated caller data"
    plan = session.prepare("copy")
    assert plan.to_dict()["review"]["response"]["proposal"]["after_text"] == AFTER
    assert plan.to_dict()["review"]["response"]["rationale"] != response["rationale"]


def test_result_is_historical_detached_and_never_rehydrates_from_journal(setup, monkeypatch):
    _, _, create = setup
    session, path, *_ = copy_ready(create)
    result = session.result()
    result["history"][0]["status"] = "forged"
    result["state"] = "restored-before"
    monkeypatch.setattr(
        module.RepositoryFiles, "verify", lambda self: pytest.fail("result must not read files")
    )
    assert session.result()["history"][0]["status"] == "completed"
    assert session.result()["state"] == "copied-before"
    assert (
        session.result()["source_observation"]["basis"] == "last-confirmed-not-refreshed-by-result"
    )
    session.close()
    assert path.exists()
    with pytest.raises(RepositorySessionError):
        session.prepare("accept-diff")


def test_live_session_cannot_be_copied_pickled_or_used_from_another_pid(setup, monkeypatch):
    _, parent, create = setup
    session, *_ = create()
    for operation in (copy.copy, copy.deepcopy, pickle.dumps):
        with pytest.raises(TypeError):
            operation(session)
    with monkeypatch.context() as change:
        change.setattr(module.os, "getpid", lambda: -1)
        with pytest.raises(RepositorySessionError):
            session.prepare("copy")
    assert list(parent.iterdir()) == []


def test_reentrant_clock_cannot_create_another_plan_or_close_the_session(setup):
    _, _, create = setup
    owner = {}

    def clock():
        if owner:
            with pytest.raises(RepositorySessionError):
                owner["session"].prepare("copy")
            with pytest.raises(RepositorySessionError):
                owner["session"].close()
        return 10.0

    session, *_ = create(clock=clock)
    owner["session"] = session
    plan = session.prepare("copy")
    assert plan.to_dict()["expires_at"] == 310.0


def test_clock_interrupt_is_propagated_and_latches_session(setup):
    _, parent, create = setup

    def interrupt():
        raise KeyboardInterrupt

    session, *_ = create(clock=interrupt)
    with pytest.raises(KeyboardInterrupt):
        session.prepare("copy")
    assert session.state == "refused" and list(parent.iterdir()) == []


def test_cleanup_failure_is_separate_from_closed_liveness_and_preserves_files(setup, monkeypatch):
    _, _, create = setup
    session, path, *_ = copy_ready(create)
    original = session._origin.close

    def close_then_fail():
        original()
        raise OSError("close result unconfirmed")

    monkeypatch.setattr(type(session._origin), "close", lambda self: close_then_fail())
    with pytest.raises(RepositorySessionError, match="cleanup"):
        session.close()
    assert session.closed
    assert session.result()["descriptor_cleanup"] == "unconfirmed"
    assert path.is_dir()


def test_same_origin_cannot_transfer_to_a_second_session(setup):
    _, parent, create = setup
    session, origin, _, request, response, plan = create()
    with pytest.raises(RepositoryOriginError, match="already-owned"):
        RepositoryFileSession(origin, request, response, plan, _parent=parent)
    assert origin.verify().to_dict() == request.to_dict()["selection"]
    assert perform(session, "copy")["state"] == "copied-before"


def test_guard_samples_time_after_all_review_parsing(setup, monkeypatch):
    _, parent, create = setup
    session, _, clock, *_ = create()
    plan = session.prepare("copy")
    decision = session.decide(plan, plan.to_dict()["confirmation"])
    # A final guard must consult its stored expiry, not parse a large review AFTER sampling time.
    with monkeypatch.context() as change:
        change.setattr(
            RepositoryFilePlan, "to_dict", lambda self: pytest.fail("guard parsed review")
        )
        clock.value = session._expires
        with pytest.raises(RepositorySessionError, match="expired"):
            session._guard()
    assert session.state == "refused" and list(parent.iterdir()) == []
    with pytest.raises(RepositorySessionError):
        session.perform(decision)
