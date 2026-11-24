"""HTTP proposal CLI checks with owned inert files and fake adapters only."""

import asyncio
import json
from types import SimpleNamespace

import pytest
from click import unstyle
from typer.testing import CliRunner

from authzest.analyzer import repository_input
from authzest.cli import app
from authzest.codex.contracts import ContractError
from authzest.codex.repository_http_proposal import RepositoryHttpRequest
from authzest.runner import repository_suggestion as flow

pytestmark = pytest.mark.skipif(
    not repository_input._supported(),
    reason="Selected-file capture requires POSIX source operations",
)
MODEL = "offline-http-proposal-model"
SOURCE = (
    "from fastapi import FastAPI\n"
    "app = FastAPI()\n"
    '@app.get("/parcels/{parcel_id}")\n'
    "def read_parcel(parcel_id: str):\n"
    '    return {"owner": "unverified"}\n'
)
POLICY = "Only the owner may read a parcel; deny anonymous and other identities.\n"


def response_for(request, status="proposed-change"):
    source = request.to_dict()["selection"]["files"][0]
    return {
        "schema_version": "2.0",
        "kind": "repository-http-proposal",
        "request_id": request.request_id,
        "status": status,
        "rationale": "Scripted proposal, not an observed authorization finding.",
        "assumptions": ["Synthetic identity setup requires independent review."],
        "uncertainties": ["No execution evidence."] if status in {"unknown", "refused"} else [],
        "limitations": ["No target request or repair has been executed."],
        "proposal": {
            "source_path": source["path"],
            "before_sha256": source["sha256"],
            "after_text": source["text"] + "\nproposal_marker = True\n",
            "poc": {
                "method": "GET",
                "path": "/parcels/one",
                "headers": [{"name": "x-user-id", "value": "test-other"}],
            },
        }
        if status == "proposed-change"
        else None,
    }


@pytest.fixture
def project(tmp_path):
    root = tmp_path.resolve()
    (root / "main.py").write_text(SOURCE)
    (root / "policy.md").write_text(POLICY)
    (root / ".env").write_text("UNSELECTED-SECRET")
    (root / "unselected.py").write_text("invalid unselected Python ?")
    return root


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

    def factory(self, status="proposed-change", mutate=None):
        def construct(**kwargs):
            self.constructed.append(kwargs)
            assert kwargs == {
                "approved_request_id": self.preview["request_id"],
                "timeout_seconds": self.preview["limits"]["timeout_seconds"],
            }

            async def suggest(request):
                assert type(request) is RepositoryHttpRequest
                assert request.to_dict() == self.preview["request"]
                self.calls.append(request)
                data = response_for(request, status)
                return mutate(data) if mutate else data

            async def wrong_method(_request):
                pytest.fail("HTTP requests must never use the legacy pytest entry")

            return SimpleNamespace(
                suggest_repository_http=suggest,
                suggest_repository=wrong_method,
                warnings_seen=2,
                retry_notifications_seen=0,
            )

        return construct

    def run(self, *, read=None, adapter=None, timeout=120, **kwargs):
        return asyncio.run(
            flow.run_repository_suggestion(
                self.root,
                "main.py",
                "policy.md",
                MODEL,
                http_poc=True,
                timeout_seconds=timeout,
                emit=self.emit,
                read=self.approve if read is None else read,
                adapter_factory=self.forbid_adapter if adapter is None else adapter,
                **kwargs,
            )
        )


@pytest.fixture
def exchange(project):
    return Exchange(project)


def test_explicit_http_preview_has_new_identity_and_only_selected_content(project):
    kwargs = {"invocation_nonce": "1" * 32}
    legacy = flow.build_repository_sharing_preview(project, "main.py", "policy.md", MODEL, **kwargs)
    explicit_legacy = flow.build_repository_sharing_preview(
        project, "main.py", "policy.md", MODEL, http_poc=False, **kwargs
    )
    http = flow.build_repository_sharing_preview(
        project, "main.py", "policy.md", MODEL, http_poc=True, **kwargs
    )
    assert legacy == explicit_legacy
    assert http["schema_version"] == "2.0"
    assert http["kind"] == "repository-http-sharing-preview"
    assert http["request_id"] != legacy["request_id"]
    assert http["sharing_id"] != legacy["sharing_id"]
    assert [f["path"] for f in http["request"]["selection"]["files"]] == ["main.py", "policy.md"]
    assert http["request"]["selection"]["contexts"] == []
    assert "test_path" not in http["request"]
    raw = json.dumps(http)
    assert "UNSELECTED-SECRET" not in raw and "unselected.py" not in raw and str(project) not in raw
    assert http["limits"]["application_retries"] == 0
    assert http["limits"]["model_fallback"] is False
    assert http["request"]["http_interface"]["app_attribute"] == "app"


@pytest.mark.parametrize(
    "options",
    [
        {"http_poc": 1},
        {"http_poc": "true"},
        {"app_attribute": "api"},
        {"http_poc": True, "contexts": ("unselected.py",)},
        {"http_poc": True, "app_attribute": 1},
    ],
    ids=["integer-selector", "string-selector", "legacy-app-option", "context", "attribute-type"],
)
def test_invalid_mode_is_refused_before_any_capture(project, monkeypatch, options):
    def forbidden(*_args, **_kwargs):
        pytest.fail("Invalid mode must not read source or hidden contexts")

    monkeypatch.setattr(flow, "capture_repository", forbidden)
    with pytest.raises(ContractError):
        flow.build_repository_sharing_preview(project, "main.py", "policy.md", MODEL, **options)


@pytest.mark.parametrize(
    "source,attribute",
    [
        ("main.py", ""),
        ("main.py", "class"),
        ("main.py", "app.child"),
        ("main.py", "app\n"),
        ("main.py", "app\u202e"),
        ("pkg/main.py", "app"),
        ("__init__.py", "app"),
        ("class.py", "app"),
        ("not-module.py", "app"),
        ("앱.py", "app"),
    ],
    ids=[
        "empty-attribute",
        "keyword-attribute",
        "dotted-attribute",
        "control-attribute",
        "bidi-attribute",
        "nested-source",
        "package-source",
        "keyword-source",
        "dashed-source",
        "unicode-source",
    ],
)
def test_invalid_http_source_or_attribute_refuses_before_capture(
    project, monkeypatch, source, attribute
):
    def forbidden(*_args, **_kwargs):
        pytest.fail("Invalid HTTP options must not read selected files")

    monkeypatch.setattr(flow, "capture_repository", forbidden)
    with pytest.raises(ContractError):
        flow.build_repository_sharing_preview(
            project, source, "policy.md", MODEL, http_poc=True, app_attribute=attribute
        )


def test_explicit_app_attribute_changes_both_request_and_sharing_identity(project):
    common = {"http_poc": True, "invocation_nonce": "1" * 32}
    default = flow.build_repository_sharing_preview(
        project, "main.py", "policy.md", MODEL, **common
    )
    custom = flow.build_repository_sharing_preview(
        project, "main.py", "policy.md", MODEL, app_attribute="api", **common
    )
    assert default["request_id"] != custom["request_id"]
    assert default["sharing_id"] != custom["sharing_id"]
    assert custom["request"]["http_interface"]["app_attribute"] == "api"
    with pytest.raises(ContractError):
        flow.build_repository_sharing_preview(
            project, "main.py", "policy.md", MODEL, app_attribute="", **common
        )


def test_http_preview_refuses_frozen_install_before_capture(project, monkeypatch):
    monkeypatch.setattr(flow.sys, "frozen", True, raising=False)

    def forbidden(*_args, **_kwargs):
        pytest.fail("Frozen mode must refuse before reading selected files")

    monkeypatch.setattr(flow, "capture_repository", forbidden)
    with pytest.raises(ContractError, match="non-frozen"):
        flow.build_repository_sharing_preview(project, "main.py", "policy.md", MODEL, http_poc=True)


@pytest.mark.parametrize("choice", ["", "yes", "cancel", "legacy", "eof", "interrupt"])
def test_http_adapter_requires_the_current_http_confirmation(exchange, choice):
    old = flow.build_repository_sharing_preview(exchange.root, "main.py", "policy.md", MODEL)

    def read(_prompt):
        if choice == "eof":
            raise EOFError
        if choice == "interrupt":
            raise KeyboardInterrupt
        if choice == "legacy":
            return "share " + old["sharing_id"]
        return choice

    result = exchange.run(read=read)
    assert result["kind"] == "repository-http-suggestion" and result["schema_version"] == "2.0"
    assert result["status"] == (
        "cancelled" if choice in {"cancel", "eof", "interrupt"} else "not-shared"
    )
    assert result["application_turn_attempts"] == 0
    assert result["proposal"] is result["proposal_preview"] is None


@pytest.mark.parametrize("status", ["proposed-change", "no-change", "unknown", "refused"])
def test_http_fake_proposal_is_one_attempt_with_no_file_or_execution_effects(exchange, status):
    before = {p.name: p.read_bytes() for p in exchange.root.iterdir()}
    result = exchange.run(adapter=exchange.factory(status))
    assert result["status"] == "proposal-ready" and result["exit_code"] == 0
    assert result["proposal"]["status"] == status
    assert (
        len(exchange.calls) == len(exchange.constructed) == result["application_turn_attempts"] == 1
    )
    assert result["authorization_status"] == "unknown"
    assert result["verified_fix"] is False
    assert (
        result["execution_status"]
        == result["patch_application"]
        == result["restoration_status"]
        == "not-run"
    )
    assert result["original_checkout_modified"] is False
    assert result["usage"] is None and result["provider_warning_count"] == 2
    assert {p.name: p.read_bytes() for p in exchange.root.iterdir()} == before
    preview = result["proposal_preview"]
    assert len(preview["changes"]) == (1 if status == "proposed-change" else 0)
    assert preview["verified_fix"] is False
    assert "test_path" not in preview and "pytest" not in preview


@pytest.mark.parametrize("selected", ["main.py", "policy.md"])
def test_changed_selected_input_refuses_before_adapter_construction(exchange, selected):
    def edit_then_approve(prompt):
        path = exchange.root / selected
        path.write_text(path.read_text() + "\n# Changed\n")
        return exchange.approve(prompt)

    result = exchange.run(read=edit_then_approve)
    assert result["status"] == "inputs-changed" and result["application_turn_attempts"] == 0


def test_disappearing_http_source_never_constructs_an_adapter(exchange):
    def delete_then_approve(prompt):
        (exchange.root / "main.py").unlink()
        return exchange.approve(prompt)

    result = exchange.run(read=delete_then_approve)
    assert result["status"] == "inputs-changed" and result["application_turn_attempts"] == 0


@pytest.mark.parametrize("point", ["read", "recapture"])
def test_http_confirmation_retains_original_deadline(exchange, monkeypatch, point):
    now = [10.0]
    monkeypatch.setattr(flow, "monotonic", lambda: now[0])
    original = flow.build_repository_sharing_preview
    builds = []

    def build(*args, **kwargs):
        result = original(*args, **kwargs)
        builds.append(result)
        if len(builds) == 2 and point == "recapture":
            now[0] = 310.0
        return result

    monkeypatch.setattr(flow, "build_repository_sharing_preview", build)

    def approve(prompt):
        now[0] = 310.0 if point == "read" else 309.9
        return exchange.approve(prompt)

    result = exchange.run(read=approve)
    assert result["status"] == "sharing-expired" and result["application_turn_attempts"] == 0


@pytest.mark.parametrize("mode", ["setup", "provider-error", "malformed", "timeout", "cancelled"])
def test_http_failures_are_redacted_without_retries(exchange, mode):
    constructions, calls = [], []

    def factory(**_kwargs):
        constructions.append(True)
        if mode == "setup":
            raise RuntimeError("PRIVATE-CONSTRUCTOR")

        async def suggest(_request):
            calls.append(True)
            if mode == "provider-error":
                raise RuntimeError("PRIVATE-PROVIDER")
            if mode == "timeout":
                await asyncio.sleep(60)
            if mode == "cancelled":
                raise asyncio.CancelledError
            return {"PRIVATE-RAW": "PRIVATE-PAYLOAD"}

        return SimpleNamespace(suggest_repository_http=suggest)

    result = exchange.run(adapter=factory, timeout=0.02 if mode == "timeout" else 120)
    assert constructions == [True]
    assert len(calls) == result["application_turn_attempts"] == (0 if mode == "setup" else 1)
    assert result["status"] == ("cancelled" if mode == "cancelled" else "generation-failed")
    assert "PRIVATE" not in json.dumps(result)
    assert result["proposal"] is result["proposal_preview"] is None


@pytest.mark.parametrize(
    "mutate", ["legacy-response", "extra-test", "expected-answer", "unbound-source"]
)
def test_http_runner_revalidates_untrusted_adapter_response(exchange, mutate):
    def change(data):
        if mutate == "legacy-response":
            data["schema_version"] = "1.0"
        elif mutate == "extra-test":
            data["proposal"]["test_text"] = "PRIVATE-TEST"
        elif mutate == "expected-answer":
            data["proposal"]["poc"]["expected_status"] = 403
        else:
            data["proposal"]["before_sha256"] = "0" * 64
        return data

    result = exchange.run(adapter=exchange.factory(mutate=change))
    assert result["status"] == "generation-failed" and result["application_turn_attempts"] == 1
    assert result["failure"]["stage"] == "result-validation"
    assert "PRIVATE-TEST" not in json.dumps(result)


def test_source_and_proposed_repair_are_never_imported(exchange):
    marker = exchange.root / "code-ran"
    payload = f"\nopen({str(marker)!r}, 'w').write('ran')\n"
    (exchange.root / "main.py").write_text(SOURCE + payload)
    result = exchange.run(adapter=exchange.factory())
    assert result["status"] == "proposal-ready" and not marker.exists()


def arguments(root):
    return [
        "repo-suggest",
        str(root),
        "--source",
        "main.py",
        "--policy",
        "policy.md",
        "--model",
        MODEL,
        "--http-poc",
    ]


def test_http_cli_offline_preview_has_one_json_and_no_adapter(project, monkeypatch):
    monkeypatch.setattr(flow, "_default_adapter_factory", Exchange.forbid_adapter)
    result = CliRunner().invoke(app, [*arguments(project), "--preview-only", "--json"])
    assert result.exit_code == 0, result.output
    value = json.loads(result.stdout)
    assert value["kind"] == "repository-http-sharing-preview" and value["schema_version"] == "2.0"
    assert value["request"]["selection"]["files"][0]["text"] == SOURCE
    assert "test_path" not in value["request"] and result.stderr == ""


def test_http_cli_keeps_preview_on_stderr_and_one_final_json_on_stdout(project, monkeypatch):
    monkeypatch.setattr(flow.secrets, "token_hex", lambda _size: "1" * 32)
    preview = flow.build_repository_sharing_preview(
        project, "main.py", "policy.md", MODEL, http_poc=True
    )
    calls = []

    def factory(**_kwargs):
        async def suggest(request):
            calls.append(request.request_id)
            return response_for(request)

        return SimpleNamespace(suggest_repository_http=suggest)

    monkeypatch.setattr(flow, "_default_adapter_factory", factory)
    result = CliRunner().invoke(
        app, [*arguments(project), "--json"], input="share " + preview["sharing_id"] + "\n"
    )
    assert result.exit_code == 0, result.output
    value, end = json.JSONDecoder().raw_decode(result.stdout)
    assert not result.stdout[end:].strip()
    assert value["kind"] == "repository-http-suggestion" and value["status"] == "proposal-ready"
    assert calls == [preview["request_id"]]
    assert '"kind": "repository-http-sharing-preview"' in result.stderr
    assert "Type 'share " in result.stderr


def test_http_human_output_shows_poc_diff_and_preserves_untrusted_escaping(project, monkeypatch):
    monkeypatch.setattr(flow.secrets, "token_hex", lambda _size: "1" * 32)
    preview = flow.build_repository_sharing_preview(
        project, "main.py", "policy.md", MODEL, http_poc=True
    )

    def factory(**_kwargs):
        async def suggest(request):
            response = response_for(request)
            response["rationale"] = "untrusted\nFORGED-TITLE\nnext"
            return response

        return SimpleNamespace(suggest_repository_http=suggest)

    monkeypatch.setattr(flow, "_default_adapter_factory", factory)
    result = CliRunner().invoke(
        app, arguments(project), input="share " + preview["sharing_id"] + "\n"
    )
    assert result.exit_code == 0, result.output
    human = unstyle(result.stdout)
    assert "External HTTP PoC and repair proposal" in human
    assert "HTTP PoC request data (not dispatched)" in human
    assert "/parcels/one" in human and "Exact proposed diff (not applied)" in human
    assert "Proposed test paths" not in human
    assert "\n  | FORGED-TITLE\n" in human
    assert "\nFORGED-TITLE\n" not in human


@pytest.mark.parametrize("invalid", [["--context", "unselected.py"], ["--app-attribute", ""]])
def test_invalid_http_cli_keeps_mode_correct_redacted_json(project, monkeypatch, invalid):
    monkeypatch.setattr(flow, "_default_adapter_factory", Exchange.forbid_adapter)
    result = CliRunner().invoke(app, [*arguments(project), *invalid, "--preview-only", "--json"])
    assert result.exit_code == 2
    value = json.loads(result.stdout)
    assert value["kind"] == "repository-http-suggestion" and value["schema_version"] == "2.0"
    assert value["status"] == "invalid-input"
    assert value["verified_fix"] is False
    assert result.stderr == ""


def test_app_attribute_without_http_mode_is_a_legacy_shaped_input_error(project, monkeypatch):
    monkeypatch.setattr(flow, "_default_adapter_factory", Exchange.forbid_adapter)
    args = arguments(project)
    args.remove("--http-poc")
    result = CliRunner().invoke(app, [*args, "--app-attribute", "api", "--preview-only", "--json"])
    assert result.exit_code == 2
    value = json.loads(result.stdout)
    assert value["kind"] == "repository-suggestion" and value["schema_version"] == "1.0"
    assert value["status"] == "invalid-input" and "verified_fix" not in value


def test_help_exposes_http_opt_in_and_explicit_app_attribute():
    result = CliRunner().invoke(app, ["repo-suggest", "--help"])
    assert result.exit_code == 0
    text = unstyle(result.stdout)
    assert "--http-poc" in text and "--app-attribute" in text
    assert "unexecuted" in text and "external" in text
