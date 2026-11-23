"""Selected external-source proposals with scripted adapters, never account use."""

import asyncio
import json
from hashlib import sha256
from types import SimpleNamespace

import pytest
from click import unstyle
from typer.testing import CliRunner

from authzest.analyzer import repository_input
from authzest.cli import app
from authzest.codex.contracts import ContractError
from authzest.codex.repository_proposal import TEST_PATH
from authzest.runner import repository_suggestion as flow

pytestmark = pytest.mark.skipif(
    not repository_input._supported(),
    reason="Selected-file capture requires POSIX source operations",
)
MODEL = "offline-repository-model"
SOURCE = (
    "from fastapi import FastAPI\n"
    "app = FastAPI()\n"
    '@app.get("/parcels/{parcel_id}")\n'
    "def read_parcel(parcel_id: str):\n"
    '    return {"owner": "unverified"}\n'
)
POLICY = "Only a parcel owner may read it; anonymous and other users must be denied.\n"
CONTEXT = "def authenticated_owner(identity):\n    return identity\n"
TEST = 'def test_owner_access(client):\n    assert client.get("/parcels/one").status_code == 200\n'


def response_for(request, status="proposed-change"):
    data = request.to_dict()
    source = data["selection"]["files"][0]
    return {
        "schema_version": "1.0",
        "request_id": request.request_id,
        "status": status,
        "rationale": "Scripted external-source proposal; not observed behavior.",
        "assumptions": ["A representative authenticated client fixture must be provided."],
        "uncertainties": ["No runtime observations exist."]
        if status in {"unknown", "refused"}
        else [],
        "limitations": ["The generated code has not been executed or applied."],
        "proposal": {
            "source_path": source["path"],
            "before_sha256": source["sha256"],
            "after_text": source["text"] + "\nproposal_marker = True\n",
            "test_path": TEST_PATH,
            "test_text": TEST,
        }
        if status == "proposed-change"
        else None,
    }


class Exchange:
    def __init__(self, root):
        self.root = root
        self.preview = None
        self.constructed = []
        self.calls = []

    def emit(self, raw):
        assert self.preview is None
        self.preview = json.loads(raw)

    def approve(self, prompt):
        phrase = "share " + self.preview["sharing_id"]
        assert phrase in prompt
        return phrase

    @staticmethod
    def forbid_adapter(**_kwargs):
        pytest.fail("Unexpected account-backed adapter construction")

    def factory(self, *, status="proposed-change", mutate=None):
        def construct(**kwargs):
            self.constructed.append(kwargs)
            assert kwargs == {
                "approved_request_id": self.preview["request_id"],
                "timeout_seconds": self.preview["limits"]["timeout_seconds"],
            }

            async def suggest(request):
                self.calls.append(request.to_dict())
                assert request.to_dict() == self.preview["request"]
                result = response_for(request, status)
                return mutate(result) if mutate else result

            return SimpleNamespace(
                suggest_repository=suggest, warnings_seen=2, retry_notifications_seen=1
            )

        return construct

    def run(self, *, read=None, adapter=None, contexts=(), timeout=120, emit=None):
        return asyncio.run(
            flow.run_repository_suggestion(
                self.root,
                "main.py",
                "policy.md",
                MODEL,
                contexts=contexts,
                timeout_seconds=timeout,
                emit=emit or self.emit,
                read=read or self.approve,
                adapter_factory=adapter or self.forbid_adapter,
            )
        )


@pytest.fixture
def project(tmp_path):
    root = tmp_path.resolve()
    (root / "main.py").write_text(SOURCE)
    (root / "policy.md").write_text(POLICY)
    (root / "auth.py").write_text(CONTEXT)
    return root


@pytest.fixture
def exchange(project):
    return Exchange(project)


def test_preview_contains_only_complete_selected_source_context_and_policy(project):
    (project / ".env").write_text("NEVER-SHARE-THIS-SECRET")
    (project / "unselected.py").write_text("unselected invalid syntax ???")
    one = flow.build_repository_sharing_preview(
        project, "main.py", "policy.md", MODEL, contexts=("auth.py",)
    )
    two = flow.build_repository_sharing_preview(
        project, "main.py", "policy.md", MODEL, contexts=("auth.py",)
    )
    assert one["sharing_id"] != two["sharing_id"]
    assert one["sharing_content_id"] == two["sharing_content_id"]
    files = one["request"]["selection"]["files"]
    assert [file["path"] for file in files] == ["main.py", "policy.md", "auth.py"]
    assert [file["text"] for file in files] == [SOURCE, POLICY, CONTEXT]
    assert all(file["sha256"] == sha256(file["text"].encode()).hexdigest() for file in files)
    raw = json.dumps(one)
    assert str(project) not in raw and "NEVER-SHARE-THIS-SECRET" not in raw
    assert "unselected.py" not in raw and "available_to_owner" not in raw
    assert one["limits"]["application_retries"] == 0
    assert one["limits"]["model_fallback"] is False
    assert one["limits"]["codex_internal_transport_retries_hard_capped"] is False
    assert one["request"]["prompt"] and one["request"]["output_schema"]
    assert one["request"]["host_instructions"]


def test_different_external_folders_use_their_actual_source_and_diff(project):
    other = project / "other"
    other.mkdir()
    other_source = SOURCE.replace("/parcels/", "/documents/").replace("parcel_id", "document_id")
    (other / "main.py").write_text(other_source)
    (other / "policy.md").write_text(POLICY.replace("parcel", "document"))
    first, second = Exchange(project), Exchange(other)
    result1 = first.run(adapter=first.factory())
    result2 = second.run(adapter=second.factory())
    assert result1["request_id"] != result2["request_id"]
    change1 = result1["proposal_preview"]["changes"][0]
    change2 = result2["proposal_preview"]["changes"][0]
    assert change1["before_text"] == SOURCE and change2["before_text"] == other_source
    assert change1["before_sha256"] != change2["before_sha256"]
    assert "/parcels/" in change1["diff"] and "/documents/" in change2["diff"]


@pytest.mark.parametrize("choice", ["", "yes", "cancel", "old", "eof", "interrupt"])
def test_only_exact_current_confirmation_can_construct_an_adapter(exchange, choice):
    previous = flow.build_repository_sharing_preview(exchange.root, "main.py", "policy.md", MODEL)

    def answer(_prompt):
        if choice == "eof":
            raise EOFError
        if choice == "interrupt":
            raise KeyboardInterrupt
        if choice == "old":
            return "share " + previous["sharing_id"]
        return choice

    result = exchange.run(read=answer)
    cancelled = choice in {"cancel", "eof", "interrupt"}
    assert result["status"] == ("cancelled" if cancelled else "not-shared")
    assert result["exit_code"] == (130 if cancelled else 0)
    assert result["application_turn_attempts"] == 0
    assert result["proposal"] is None and result["proposal_preview"] is None


@pytest.mark.parametrize("status", ["proposed-change", "no-change", "unknown", "refused"])
def test_single_approved_scripted_proposal_is_never_applied_or_executed(exchange, status):
    before = {p.name: p.read_bytes() for p in exchange.root.iterdir()}
    result = exchange.run(adapter=exchange.factory(status=status), contexts=("auth.py",))
    assert result["status"] == "proposal-ready" and result["exit_code"] == 0
    assert result["proposal"]["status"] == status
    assert (
        len(exchange.constructed) == len(exchange.calls) == result["application_turn_attempts"] == 1
    )
    assert result["execution_status"] == result["patch_application"] == "not-run"
    assert result["restoration_status"] == "not-run"
    assert result["original_checkout_modified"] is False
    assert result["authorization_status"] == "unknown" and result["usage"] is None
    assert (
        result["provider_warning_count"] == 2 and result["provider_retry_notification_count"] == 1
    )
    assert {p.name: p.read_bytes() for p in exchange.root.iterdir()} == before
    assert len(result["proposal_preview"]["changes"]) == (2 if status == "proposed-change" else 0)


@pytest.mark.parametrize("changed", ["main.py", "policy.md", "auth.py"])
def test_every_selected_input_is_recaptured_before_adapter_creation(exchange, changed):
    def approve_then_edit(prompt):
        path = exchange.root / changed
        path.write_text(
            path.read_text() + ("\n# Edited\n" if path.suffix == ".py" else "\nEdited policy.\n")
        )
        return exchange.approve(prompt)

    result = exchange.run(read=approve_then_edit, contexts=("auth.py",))
    assert result["status"] == "inputs-changed" and result["exit_code"] == 1
    assert result["application_turn_attempts"] == 0


def test_disappearing_source_after_confirmation_refuses_the_transport(exchange):
    def approve_then_remove(prompt):
        (exchange.root / "main.py").unlink()
        return exchange.approve(prompt)

    result = exchange.run(read=approve_then_remove)
    assert result["status"] == "inputs-changed" and result["application_turn_attempts"] == 0


@pytest.mark.parametrize("expiry_point", ["read", "recapture"])
def test_original_sharing_deadline_is_not_extended_by_read_or_recapture(
    exchange, monkeypatch, expiry_point
):
    now = [10.0]
    monkeypatch.setattr(flow, "monotonic", lambda: now[0])
    original = flow.build_repository_sharing_preview
    builds = []

    def build(*args, **kwargs):
        result = original(*args, **kwargs)
        builds.append(result)
        if len(builds) == 2 and expiry_point == "recapture":
            now[0] = 310.0
        return result

    monkeypatch.setattr(flow, "build_repository_sharing_preview", build)

    def approve(prompt):
        now[0] = 310.0 if expiry_point == "read" else 309.9
        return exchange.approve(prompt)

    result = exchange.run(read=approve)
    assert result["status"] == "sharing-expired" and result["application_turn_attempts"] == 0
    assert len(builds) == (1 if expiry_point == "read" else 2)


@pytest.mark.parametrize("mode", ["setup", "provider-error", "malformed", "timeout", "cancelled"])
def test_failure_is_redacted_single_attempt_and_has_no_implicit_retry(exchange, mode):
    constructions, calls = [], []

    def factory(**_kwargs):
        constructions.append(True)
        if mode == "setup":
            raise RuntimeError("PRIVATE-CONSTRUCTOR-DATA")

        async def suggest(_request):
            calls.append(True)
            if mode == "provider-error":
                raise RuntimeError("PRIVATE-PROVIDER-DATA")
            if mode == "timeout":
                await asyncio.sleep(60)
            if mode == "cancelled":
                raise asyncio.CancelledError
            return {"PRIVATE-RAW-OUTPUT": "PRIVATE-PAYLOAD"}

        return SimpleNamespace(suggest_repository=suggest)

    result = exchange.run(adapter=factory, timeout=0.02 if mode == "timeout" else 120)
    assert constructions == [True]
    assert len(calls) == result["application_turn_attempts"] == (0 if mode == "setup" else 1)
    assert result["status"] == ("cancelled" if mode == "cancelled" else "generation-failed")
    assert result["exit_code"] == (130 if mode == "cancelled" else 1)
    assert "PRIVATE" not in json.dumps(result)
    assert result["proposal"] is None and result["proposal_preview"] is None
    if mode == "timeout":
        assert result["failure"]["code"] == "timeout"


@pytest.mark.parametrize("timeout", [False, -1, 0, 121, float("nan"), float("inf"), 10**400])
def test_invalid_timeout_is_rejected_before_reading_or_constructing_an_adapter(exchange, timeout):
    with pytest.raises(ContractError):
        exchange.run(timeout=timeout)
    assert exchange.preview is None


def test_neither_source_context_nor_generated_code_is_imported_or_executed(exchange):
    marker = exchange.root / "ran-code"
    payload = f"\nopen({str(marker)!r}, 'w').write('ran')\n"
    (exchange.root / "main.py").write_text(SOURCE + payload)
    (exchange.root / "auth.py").write_text(CONTEXT + payload)

    def malicious_test(result):
        result["proposal"]["test_text"] = TEST + payload
        return result

    result = exchange.run(adapter=exchange.factory(mutate=malicious_test), contexts=("auth.py",))
    assert result["status"] == "proposal-ready" and not marker.exists()
    assert result["execution_status"] == "not-run"


def _arguments(root):
    return [
        "repo-suggest",
        str(root),
        "--source",
        "main.py",
        "--policy",
        "policy.md",
        "--model",
        MODEL,
        "--context",
        "auth.py",
    ]


def test_cli_offline_preview_never_constructs_an_adapter_and_emits_one_json(project, monkeypatch):
    monkeypatch.setattr(flow, "_default_adapter_factory", Exchange.forbid_adapter)
    result = CliRunner().invoke(app, [*_arguments(project), "--preview-only", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    assert data["kind"] == "repository-sharing-preview"
    assert data["request"]["selection"]["files"][0]["text"] == SOURCE
    assert str(project) not in result.stdout
    assert result.stderr == ""


def test_cli_single_final_json_keeps_sharing_preview_and_prompt_on_stderr(project, monkeypatch):
    monkeypatch.setattr(flow.secrets, "token_hex", lambda _size: "1" * 32)
    expected = flow.build_repository_sharing_preview(
        project, "main.py", "policy.md", MODEL, contexts=("auth.py",)
    )
    calls = []

    def factory(**_kwargs):
        async def suggest(request):
            calls.append(request.request_id)
            return response_for(request)

        return SimpleNamespace(suggest_repository=suggest)

    monkeypatch.setattr(flow, "_default_adapter_factory", factory)
    result = CliRunner().invoke(
        app, [*_arguments(project), "--json"], input=f"share {expected['sharing_id']}\n"
    )
    assert result.exit_code == 0, result.output
    data, end = json.JSONDecoder().raw_decode(result.stdout)
    assert not result.stdout[end:].strip()
    assert data["kind"] == "repository-suggestion" and data["status"] == "proposal-ready"
    assert calls == [expected["request_id"]]
    assert '"kind": "repository-sharing-preview"' in result.stderr
    assert "Type 'share " in result.stderr


def test_cli_human_output_displays_real_paths_diff_and_escapes_untrusted_text(project, monkeypatch):
    monkeypatch.setattr(flow.secrets, "token_hex", lambda _size: "2" * 32)
    preview = flow.build_repository_sharing_preview(
        project, "main.py", "policy.md", MODEL, contexts=("auth.py",)
    )

    def factory(**_kwargs):
        async def suggest(request):
            return response_for(request) | {"rationale": "untrusted\u202e text\rline"}

        return SimpleNamespace(suggest_repository=suggest)

    monkeypatch.setattr(flow, "_default_adapter_factory", factory)
    result = CliRunner().invoke(app, _arguments(project), input=f"share {preview['sharing_id']}\n")
    assert result.exit_code == 0, result.output
    assert "External repository proposal" in result.stdout
    assert "main.py" in result.stdout and "policy.md" in result.stdout
    assert "Exact proposed diff (not applied)" in result.stdout
    assert "proposal_marker" in result.stdout
    assert "\\u202e" in result.stdout and "\\r" in result.stdout
    assert "\u202e" not in result.stdout and "\r" not in result.stdout


@pytest.mark.parametrize("source", ["../PRIVATE-OUTSIDE.py", "/PRIVATE-ABSOLUTE.py", "missing.py"])
def test_cli_invalid_input_has_safe_exit_two_and_single_json(project, monkeypatch, source):
    monkeypatch.setattr(flow, "_default_adapter_factory", Exchange.forbid_adapter)
    args = _arguments(project)
    args[args.index("--source") + 1] = source
    result = CliRunner().invoke(app, [*args, "--json"])
    assert result.exit_code == 2
    data = json.loads(result.stdout)
    assert data["status"] == "invalid-input"
    assert data["execution_status"] == data["patch_application"] == "not-run"
    assert str(project) not in result.stdout and "PRIVATE" not in result.stdout


def test_cli_eof_cancels_without_account_use(project, monkeypatch):
    monkeypatch.setattr(flow, "_default_adapter_factory", Exchange.forbid_adapter)
    result = CliRunner().invoke(app, [*_arguments(project), "--json"])
    assert result.exit_code == 130
    assert json.loads(result.stdout)["status"] == "cancelled"


@pytest.mark.parametrize("colored", [False, True])
def test_cli_help_distinguishes_external_proposals_from_execution(monkeypatch, colored):
    import typer.rich_utils

    # Model both a plain terminal and CI's forced Rich styling, independently of
    # this host's NO_COLOR / terminal defaults. Styling can split option names.
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm")
    monkeypatch.setattr(typer.rich_utils, "FORCE_TERMINAL", colored)
    result = CliRunner().invoke(app, ["repo-suggest", "--help"], color=True)
    assert result.exit_code == 0
    assert ("\x1b[" in result.stdout) is colored
    text = unstyle(result.stdout)
    assert "external" in text and "unexecuted" in text
    assert "--context" in text and "--preview-only" in text
