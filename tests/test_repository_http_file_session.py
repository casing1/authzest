"""Current HTTP private bytes and checkpoints only; no target code is executed."""

import builtins
import copy
import json
import os
import pickle
import socket
import subprocess
from contextlib import suppress
from dataclasses import replace
from pathlib import Path

import pytest
from tests.helpers.repository_http_file_data import make_http_file_session, perform
from tests.helpers.repository_http_verification_data import AFTER, POLICY, SOURCE

from authzest.analyzer.repository_origin import RepositoryOriginError, capture_repository_origin
from authzest.codex.contracts import canonical
from authzest.runner.repository_http_file_session import (
    RepositoryHttpFileSession,
    RepositoryHttpSessionError,
)

pytestmark = pytest.mark.skipif(os.name != "posix", reason="POSIX HTTP private files")


@pytest.fixture(autouse=True)
def no_target_or_external_effects(monkeypatch):
    original_import = builtins.__import__

    def forbidden(*args, **kwargs):
        pytest.fail("HTTP session tests may only operate on owned inert bytes")

    def guarded_import(name, *args, **kwargs):
        if name.split(".")[0] in {"app", "fastapi", "httpx", "uvicorn", "docker", "openai"}:
            forbidden()
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(os, "system", forbidden)


@pytest.fixture
def setup(tmp_path):
    sessions = []

    def create(*, clock=None):
        values = make_http_file_session(tmp_path, clock=clock, prefix="case-" + str(len(sessions)))
        sessions.append(values[0])
        return values

    yield create
    for session in sessions:
        with suppress(RepositoryHttpSessionError):
            session.close()


def private_root(session):
    return Path(session.result()["private_root"])


def decision(session, step):
    plan = session.prepare(step)
    return session.decide(plan, plan.to_dict()["confirmation"])


def test_complete_source_only_cycle_and_current_checkpoints(setup):
    session, origin, _, request, response, cases, copy_plan = setup()
    assert session.state == "captured" and session.result()["private_root"] is None
    perform(session, "copy")
    root = private_root(session)
    assert {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()} == {
        "project/app.py",
        "evidence/source.before",
        "evidence/source.after",
        "evidence/policy.txt",
        "record.json",
    }
    before = session._capture_runtime_checkpoint("before")
    assert before is session._capture_runtime_checkpoint("before")
    assert before.request == request and before.response == response and before.cases == cases
    assert before.copy_plan == copy_plan
    assert before.source_path == "app.py" and before.source_bytes == SOURCE.encode()
    assert before.materials == (("app.py", SOURCE.encode()),)
    assert not hasattr(before, "test_path") and not hasattr(before, "test_bytes")
    session._recheck_runtime_checkpoint(before)
    perform(session, "accept-diff")
    with pytest.raises(RepositoryHttpSessionError):
        session._recheck_runtime_checkpoint(before)
    perform(session, "apply")
    assert (root / "project/app.py").read_bytes() == AFTER.encode()
    after = session._capture_runtime_checkpoint("after")
    assert after is not before and after.revision == 3
    assert after.source_bytes == AFTER.encode()
    session._recheck_runtime_checkpoint(after)
    journal = json.loads(after.journal_bytes)
    assert journal["state"] == "applied-after" and journal["pending_operation"] is None
    assert journal["case_set_id"] == cases.case_set_id
    assert journal["verification_plan_id"] == after.verification_plan.plan_id
    perform(session, "restore")
    assert (root / "project/app.py").read_bytes() == SOURCE.encode()
    with pytest.raises(RepositoryHttpSessionError):
        session._recheck_runtime_checkpoint(after)
    assert (origin.snapshot.root / "app.py").read_bytes() == SOURCE.encode()
    assert (origin.snapshot.root / "policy.md").read_bytes() == POLICY.encode()
    result = session.result()
    assert result["kind"] == "repository-http-file-session" and result["schema_version"] == "2.0"
    assert result["execution_status"] == "not-run" and result["authorization_status"] == "unknown"
    assert result["verified_fix"] is False and result["original_write"] == "not-supported"
    session.close()
    assert root.exists() and session.closed and result["closed"] is False


@pytest.mark.parametrize("step", ["accept-diff", "apply", "restore", "before", "copy ", "", None])
def test_wrong_initial_stage_has_no_private_effect(setup, step):
    session, _, _, _, _, _, _ = setup()
    with pytest.raises(RepositoryHttpSessionError):
        session.prepare(step)
    assert session.result()["private_root"] is None


@pytest.mark.parametrize(
    "how",
    ["equal-plan", "saved-plan", "wrong-phrase", "equal-decision", "saved-decision", "replay"],
)
def test_only_current_local_review_and_decision_objects_can_be_used(setup, how):
    session, *_ = setup()
    plan = session.prepare("copy")
    if how in {"equal-plan", "saved-plan", "wrong-phrase"}:
        supplied = (
            replace(plan)
            if how == "equal-plan"
            else plan.to_dict()
            if how == "saved-plan"
            else plan
        )
        phrase = "wrong" if how == "wrong-phrase" else plan.to_dict()["confirmation"]
        with pytest.raises(RepositoryHttpSessionError):
            session.decide(supplied, phrase)
        assert session.result()["private_root"] is None
        return
    chosen = session.decide(plan, plan.to_dict()["confirmation"])
    if how == "replay":
        session.perform(chosen)
        with pytest.raises(RepositoryHttpSessionError):
            session.perform(chosen)
        assert session.state == "copied-before"
    else:
        supplied = (
            replace(chosen)
            if how == "equal-decision"
            else chosen.__dict__
            if hasattr(chosen, "__dict__")
            else {"step": chosen.step}
        )
        with pytest.raises(RepositoryHttpSessionError):
            session.perform(supplied)
        assert session.result()["private_root"] is None


def test_different_sessions_cannot_exchange_decisions_or_checkpoints(setup):
    first, *_ = setup()
    second, *_ = setup()
    chosen = decision(first, "copy")
    with pytest.raises(RepositoryHttpSessionError):
        second.perform(chosen)
    first.perform(chosen)
    perform(second, "copy")
    checkpoint = first._capture_runtime_checkpoint("before")
    with pytest.raises(RepositoryHttpSessionError):
        second._recheck_runtime_checkpoint(checkpoint)
    first._recheck_runtime_checkpoint(checkpoint)


@pytest.mark.parametrize("position", ["before-copy", "after-copy"])
def test_repeated_preparation_does_not_extend_the_300_second_window(setup, position):
    session, _, clock, *_ = setup()
    if position == "after-copy":
        perform(session, "copy")
    step = "copy" if position == "before-copy" else "accept-diff"
    plan = session.prepare(step)
    start = plan.to_dict()
    assert start["expires_at"] - start["issued_at"] <= 300
    clock.value += 299
    assert session.prepare(step) is plan
    assert session.prepare(step).to_dict()["expires_at"] == start["expires_at"]
    clock.value += 1
    with pytest.raises(RepositoryHttpSessionError):
        session.decide(plan, start["confirmation"])
    assert session.state == ("refused" if position == "before-copy" else "recovery-required")


@pytest.mark.parametrize(
    "value",
    [None, True, -1, float("nan"), float("inf"), pytest.param(10**1000, id="oversized-int"), "10"],
)
def test_invalid_clock_refuses_before_copy(setup, value):
    session, *_ = setup(clock=lambda: value)
    with pytest.raises(RepositoryHttpSessionError):
        session.prepare("copy")
    assert session.state == "refused" and session.result()["private_root"] is None


@pytest.mark.parametrize("phase", ["after", "unknown", None])
def test_wrong_phase_is_not_a_checkpoint(setup, phase):
    session, *_ = setup()
    perform(session, "copy")
    with pytest.raises(RepositoryHttpSessionError):
        session._capture_runtime_checkpoint(phase)
    assert session.state == "copied-before"


@pytest.mark.parametrize("step", ["accept-diff", "apply", "restore"])
def test_pending_decision_prevents_checkpoint_adoption(setup, step):
    session, *_ = setup()
    perform(session, "copy")
    if step in {"apply", "restore"}:
        perform(session, "accept-diff")
    if step == "restore":
        perform(session, "apply")
    phase = "after" if step == "restore" else "before"
    checkpoint = session._capture_runtime_checkpoint(phase) if step != "apply" else None
    plan = session.prepare(step)
    with pytest.raises(RepositoryHttpSessionError):
        session._capture_runtime_checkpoint(phase)
    if checkpoint is not None:
        with pytest.raises(RepositoryHttpSessionError):
            session._recheck_runtime_checkpoint(checkpoint)
    session.decide(plan, plan.to_dict()["confirmation"])
    with pytest.raises(RepositoryHttpSessionError):
        session._capture_runtime_checkpoint(phase)


@pytest.mark.parametrize(
    "change", ["source", "policy", "before", "after", "journal", "same-byte-inode", "extra"]
)
def test_private_material_or_membership_edits_invalidate_checkpoint(setup, change):
    session, *_ = setup()
    perform(session, "copy")
    checkpoint = session._capture_runtime_checkpoint("before")
    root = private_root(session)
    mapping = {
        "source": "project/app.py",
        "policy": "evidence/policy.txt",
        "before": "evidence/source.before",
        "after": "evidence/source.after",
        "journal": "record.json",
    }
    if change == "same-byte-inode":
        target = root / "project/app.py"
        target.unlink()
        target.write_bytes(SOURCE.encode())
        target.chmod(0o600)
    elif change == "extra":
        (root / "unexpected").write_bytes(b"owned edit")
    else:
        (root / mapping[change]).write_bytes(b"owned user edit")
    with pytest.raises(RepositoryHttpSessionError):
        session._recheck_runtime_checkpoint(checkpoint)
    assert session.state == "recovery-required"
    assert (root / "project/app.py").read_bytes() != AFTER.encode()


@pytest.mark.parametrize(
    "field",
    [
        "kind",
        "schema_version",
        "revision",
        "source_transition",
        "file_identities",
        "execution_status",
        "verified_fix",
        "extra",
    ],
)
def test_even_self_committed_wrong_journal_is_not_current_completed_state(setup, field):
    session, *_ = setup()
    perform(session, "copy")
    record = json.loads(session._files.read("record.json"))
    record[field] = "tampered"
    session._files.replace("record.json", canonical(record).encode(), guard=lambda: None)
    with pytest.raises(RepositoryHttpSessionError):
        session._capture_runtime_checkpoint("before")
    assert session.state == "recovery-required"


@pytest.mark.parametrize("how", ["clone", "dict", "copy", "deepcopy", "pickle"])
def test_checkpoint_is_neither_copyable_nor_reconstructable_authority(setup, how):
    session, *_ = setup()
    perform(session, "copy")
    checkpoint = session._capture_runtime_checkpoint("before")
    if how in {"copy", "deepcopy", "pickle"}:
        operation = {"copy": copy.copy, "deepcopy": copy.deepcopy, "pickle": pickle.dumps}[how]
        with pytest.raises(TypeError):
            operation(checkpoint)
    else:
        supplied = replace(checkpoint) if how == "clone" else {"session_id": checkpoint.session_id}
        with pytest.raises(RepositoryHttpSessionError):
            session._recheck_runtime_checkpoint(supplied)
    session._recheck_runtime_checkpoint(checkpoint)


@pytest.mark.parametrize("how", ["copy", "deepcopy", "pickle"])
def test_live_session_cannot_be_copied_or_serialized(setup, how):
    session, *_ = setup()
    with pytest.raises(TypeError):
        {"copy": copy.copy, "deepcopy": copy.deepcopy, "pickle": pickle.dumps}[how](session)


@pytest.mark.parametrize("actor", ["process", "thread", "closed"])
def test_checkpoint_recheck_requires_same_live_actor(setup, monkeypatch, actor):
    session, *_ = setup()
    perform(session, "copy")
    checkpoint = session._capture_runtime_checkpoint("before")
    if actor == "closed":
        session.close()
    else:
        monkeypatch.setattr(session, "_pid" if actor == "process" else "_thread", -1)
    with pytest.raises(RepositoryHttpSessionError):
        session._recheck_runtime_checkpoint(checkpoint)


def test_origin_drift_after_copy_does_not_rewrite_private_binding(setup):
    session, origin, *_ = setup()
    perform(session, "copy")
    (origin.snapshot.root / "app.py").write_bytes(b"later original edit\n")
    checkpoint = session._capture_runtime_checkpoint("before")
    session._recheck_runtime_checkpoint(checkpoint)
    assert checkpoint.source_bytes == SOURCE.encode()
    perform(session, "accept-diff")
    perform(session, "apply")
    perform(session, "restore")
    assert (origin.snapshot.root / "app.py").read_bytes() == b"later original edit\n"


def test_origin_change_before_copy_refuses_without_allocating(setup):
    session, origin, *_ = setup()
    (origin.snapshot.root / "policy.md").write_bytes(b"changed original policy")
    with pytest.raises(RepositoryHttpSessionError):
        session.prepare("copy")
    assert session.result()["private_root"] is None


def test_origin_ownership_cannot_be_claimed_again(setup):
    session, origin, clock, request, response, cases, copy_plan = setup()
    with pytest.raises(RepositoryOriginError):
        RepositoryHttpFileSession(origin, request, response, cases, copy_plan, _clock=clock)
    perform(session, "copy")


@pytest.mark.parametrize("field", ["rationale", "cases", "verification-plan"])
def test_full_contract_change_is_detected_even_when_repair_bytes_are_unchanged(setup, field):
    session, *_ = setup()
    perform(session, "copy")
    checkpoint = session._capture_runtime_checkpoint("before")
    if field == "rationale":
        session._response["rationale"] = "A different full response with identical source."
    elif field == "cases":
        data = session._cases.to_dict()
        data["authorship"] = "Changed declarations."
        session._cases = replace(session._cases, payload_json=canonical(data))
    else:
        data = session._verification_plan.to_dict()
        data["requirements"]["case_review"] = "changed"
        session._verification_plan = replace(
            session._verification_plan, payload_json=canonical(data)
        )
    with pytest.raises(RepositoryHttpSessionError):
        session._recheck_runtime_checkpoint(checkpoint)
    assert session.state == "recovery-required"


def test_constructor_nonproposal_does_not_claim_new_origin_or_create_files(setup):
    session, origin, clock, request, response, cases, _ = setup()
    fresh = capture_repository_origin(origin.snapshot.root, "app.py", "policy.md")
    response["status"], response["proposal"] = "unknown", None
    try:
        with pytest.raises(RepositoryHttpSessionError):
            RepositoryHttpFileSession(fresh, request, response, cases, None, _clock=clock)
        assert fresh._owner is None
    finally:
        fresh.close()
    assert session.result()["private_root"] is None
