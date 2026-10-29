"""Offline construction/AST checks only: never execute the new worker or policy.

These checks inspect syntax, embedded registrations and required guard structure.
They are not worker execution acceptance or observations of either policy.
"""

import ast
import asyncio
import builtins
import socket
import subprocess
from dataclasses import replace
from hashlib import sha256

import pytest

from authzest.codex.contracts import ContractError, canonical, identity
from authzest.codex.owner_policy_repair_pair import build_owner_policy_repair_pair
from authzest.runner import _owner_policy_file_worker as worker


@pytest.fixture(autouse=True)
def forbid_real_effects(monkeypatch):
    original_compile = builtins.compile

    def only_ast(source, filename, mode, flags=0, *args, **kwargs):
        if not flags & ast.PyCF_ONLY_AST:
            raise AssertionError("Only AST parsing is permitted, never worker compilation")
        return original_compile(source, filename, mode, flags, *args, **kwargs)

    monkeypatch.setattr(builtins, "compile", only_ast)
    for name in ("open", "exec", "eval"):
        monkeypatch.setattr(builtins, name, _forbidden)
    monkeypatch.setattr(subprocess, "Popen", _forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", _forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_shell", _forbidden)
    monkeypatch.setattr(socket.socket, "connect", _forbidden)


def _tree() -> ast.Module:
    # Parsing syntax is permitted. Never compile or evaluate the returned AST.
    return ast.parse(worker.WORKER_SOURCE)


def _function(name: str) -> ast.FunctionDef:
    return next(
        node for node in _tree().body if isinstance(node, ast.FunctionDef) and node.name == name
    )


def _literal(name: str):
    node = next(
        node
        for node in _tree().body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == name for target in node.targets)
    )
    # Only a constant/container AST is decoded, never executable worker source.
    return ast.literal_eval(node.value)


def _calls(node: ast.AST, name: str) -> list[ast.Call]:
    return [
        child
        for child in ast.walk(node)
        if isinstance(child, ast.Call)
        and isinstance(child.func, ast.Name)
        and child.func.id == name
    ]


def _source(node: ast.AST) -> str:
    return ast.get_source_segment(worker.WORKER_SOURCE, node)


def _forbidden(*args, **kwargs):
    raise AssertionError("Offline worker preparation must not perform an effect")


def test_worker_construction_is_inert_and_revalidates_registration(monkeypatch):
    validated = []
    original = worker.validate_owner_policy_repair_pair

    def validate(raw):
        validated.append(raw)
        return original(raw)

    with monkeypatch.context() as guarded:
        guarded.setattr(worker, "validate_owner_policy_repair_pair", validate)
        for name in ("open", "exec", "eval", "compile"):
            guarded.setattr(builtins, name, _forbidden)
        guarded.setattr(subprocess, "Popen", _forbidden)
        guarded.setattr(socket, "socket", _forbidden)
        rebuilt = worker._build_worker_source()
    assert rebuilt == worker.WORKER_SOURCE
    assert validated == [build_owner_policy_repair_pair().payload_json]


def test_worker_construction_rejects_changed_registered_material(monkeypatch):
    pair = build_owner_policy_repair_pair()
    changed = pair.to_dict()
    changed["content"]["cases"][0]["principal"]["subject"] = "other"
    changed_pair = replace(pair, payload_json=canonical(changed))
    monkeypatch.setattr(worker, "build_owner_policy_repair_pair", lambda: changed_pair)
    with pytest.raises(ContractError):
        worker._build_worker_source()


def test_worker_bytes_match_literal_implementation_pin():
    assert worker.CHECK_ID == "owned-owner-file-repair-check-v1"
    assert worker.MAX_INPUT_BYTES == 256 * 1024
    assert worker.MAX_OUTPUT_BYTES == 16 * 1024
    assert (
        worker.WORKER_SHA256 == "33413d680ac8e00f514d5897aca2289527cfccfd8a1fccdebb179c774377491d"
    )
    assert sha256(worker.WORKER_SOURCE.encode("utf-8")).hexdigest() == worker.WORKER_SHA256
    assert _literal("CHECK_ID") == worker.CHECK_ID
    assert _literal("MAX_DEPTH") == 32
    assert _literal("MAX_NODES") == 8192


@pytest.mark.parametrize("candidate", ["before", "after"])
def test_registration_constants_validate_captured_text_without_evaluating(candidate):
    content = build_owner_policy_repair_pair().to_dict()["content"]
    sources = _literal("POLICY_SOURCES")
    digests = _literal("POLICY_SHA256")
    assert set(sources) == set(digests) == {"before", "after"}
    assert sources[candidate] == content[candidate]["text"]
    assert digests[candidate] == content[candidate]["sha256"]
    assert sha256(sources[candidate].encode("utf-8")).hexdigest() == digests[candidate]


def test_embedded_rows_are_exact_ordered_input_only_cases():
    cases = build_owner_policy_repair_pair().to_dict()["content"]["cases"]
    expected_rows = []
    for case in cases:
        row = {key: case[key] for key in ("case_id", "principal", "report")}
        expected_rows.append({**row, "input_sha256": identity(row)})
    actual = _literal("REGISTERED_INPUT_ROWS")
    assert canonical(actual) == canonical(expected_rows)
    assert len(actual) == 8
    assert actual[-1]["principal"]["subject"] == " alice"
    assert all(set(row) == {"case_id", "input_sha256", "principal", "report"} for row in actual)
    assert _literal("REGISTERED_INPUT_SHA256") == identity(actual)


def test_worker_source_imports_only_fixed_stdlib_modules():
    imports = [node for node in ast.walk(_tree()) if isinstance(node, (ast.Import, ast.ImportFrom))]
    assert all(isinstance(node, ast.Import) for node in imports)
    assert {alias.name for node in imports for alias in node.names} == {
        "hashlib",
        "json",
        "re",
        "sys",
        "types",
    }
    assert not _calls(_tree(), "open")
    assert not _calls(_tree(), "eval")
    assert not _calls(_tree(), "__import__")


def test_complete_validation_precedes_only_policy_compilation_site():
    main = _function("main")
    validate = _calls(main, "_validate")
    observe = _calls(main, "_observe")
    assert len(validate) == len(observe) == 1
    assert validate[0].lineno < observe[0].lineno
    assert _source(observe[0]) == '_observe(payload["source_text"], cases)'
    compilation = _calls(_tree(), "compile")
    execution = _calls(_tree(), "exec")
    assert len(compilation) == len(execution) == 1
    assert len(_calls(_function("_observe"), "compile")) == 1
    # Compare AST shape because separately parsed node objects have different identity.
    assert ast.dump(compilation[0].args[0]) == ast.dump(ast.Name(id="source_text", ctx=ast.Load()))
    assert ast.literal_eval(compilation[0].args[1]) == "<authzest-owned-file-policy>"
    assert ast.literal_eval(compilation[0].args[2]) == "exec"


def test_worker_main_reads_only_bounded_stdin_and_emits_bounded_complete_output():
    text = _source(_function("main"))
    assert "sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)" in text
    assert text.index("len(raw) > MAX_OUTPUT_BYTES") < text.index("sys.stdout.buffer.write(raw)")
    assert "sys.stderr" not in worker.WORKER_SOURCE
    assert "traceback" not in {
        alias.name
        for node in ast.walk(_tree())
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    handlers = [node for node in ast.walk(_function("main")) if isinstance(node, ast.ExceptHandler)]
    assert len(handlers) == 1
    assert isinstance(handlers[0].type, ast.Name)
    assert handlers[0].type.id == "Exception"
    assert len(handlers[0].body) == 1
    assert isinstance(handlers[0].body[0], ast.Return)
    assert ast.literal_eval(handlers[0].body[0].value) == 2


def test_worker_closed_input_and_output_identity_field_sets():
    validation = _function("_validate")
    first_object = _calls(validation, "_object")[0]
    assert ast.literal_eval(first_object.args[1]) == {
        "schema_version",
        "check_id",
        "plan_id",
        "session_id",
        "stage",
        "candidate",
        "file_state_sha256",
        "policy_source_sha256",
        "source_text",
        "worker_sha256",
        "input_sha256",
        "cases",
    }
    main = _function("main")
    result = next(
        node.value
        for node in ast.walk(main)
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "result" for target in node.targets)
    )
    assert isinstance(result, ast.DictComp)
    assert ast.literal_eval(result.generators[0].iter) == (
        "schema_version",
        "check_id",
        "plan_id",
        "session_id",
        "stage",
        "candidate",
        "file_state_sha256",
        "policy_source_sha256",
        "worker_sha256",
        "input_sha256",
    )


@pytest.mark.parametrize(
    "guard",
    [
        'type(candidate) is not str or candidate not in {"before", "after"}',
        'r"owner-file-check-[a-f0-9]{64}"',
        'r"[a-f0-9]{32}"',
        '_digest(payload["file_state_sha256"])',
        'payload["stage"] != candidate + "-check"',
        "type(source_text) is not str or not source_text",
        'source_text.encode("utf-8")',
        "len(source_bytes) > 32768 or source_text != POLICY_SOURCES[candidate]",
        "source_hash != POLICY_SHA256[candidate]",
        'payload["policy_source_sha256"] != source_hash',
        "type(cases) is not list or len(cases) != 8",
        "case_id in identifiers",
        'type(principal["authenticated"]) is not bool',
        "type(scopes) is not list or len(scopes) > 16",
        "len(set(scopes)) != len(scopes)",
        '_identity(input_row) != case["input_sha256"]',
        "_canonical(cases) != _canonical(REGISTERED_INPUT_ROWS)",
        "_identity(cases) != REGISTERED_INPUT_SHA256",
        'payload["input_sha256"] != REGISTERED_INPUT_SHA256',
    ],
)
def test_worker_input_guard_structure_is_present(guard):
    assert guard in _source(_function("_validate"))


def test_json_parser_declares_duplicate_numeric_nonfinite_unicode_and_resource_guards():
    decoder = _function("_decode")
    loads = next(
        node
        for node in ast.walk(decoder)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "json"
        and node.func.attr == "loads"
    )
    assert {keyword.arg: keyword.value.id for keyword in loads.keywords} == {
        "object_pairs_hook": "_pairs",
        "parse_int": "_number",
        "parse_float": "_number",
        "parse_constant": "_number",
    }
    assert any(isinstance(node, ast.Raise) for node in ast.walk(_function("_number")))
    assert "if key in result:" in _source(_function("_pairs"))
    text = _source(decoder)
    for guard in (
        "len(raw) > MAX_INPUT_BYTES",
        "depth > MAX_DEPTH",
        "depth < 0",
        "if depth or quoted",
        "item_depth > MAX_DEPTH or visited > MAX_NODES",
        'item.encode("utf-8")',
        "ord(char) < 32",
        "type(item) is not bool",
    ):
        assert guard in text
    assert text.index("depth > MAX_DEPTH") < text.index("json.loads")


def test_observation_mapping_is_fixed_boolean_and_input_only():
    text = _source(_function("_observe"))
    assert 'name = "_authzest_owned_owner_file_policy"' in text
    assert 'scopes=frozenset(principal["scopes"])' in text
    assert "if type(observed) is not bool:" in text
    assert "module.can_read_report(principal, report)" in text
    assert "del sys.modules[name]" in text
    dictionaries = [node for node in ast.walk(_function("_observe")) if isinstance(node, ast.Dict)]
    assert len(dictionaries) == 1
    assert {ast.literal_eval(key) for key in dictionaries[0].keys} == {
        "case_id",
        "input_sha256",
        "observed",
    }


def test_no_runtime_execution_entrypoint_on_outer_module():
    assert not hasattr(worker, "main")
    assert not hasattr(worker, "_observe")
    assert not hasattr(worker, "_validate")
    assert "self-attestation" in worker.__doc__


def test_source_whitespace_is_allowed_only_before_exact_registration_comparison():
    decoder = _function("_decode")
    guard = next(
        node
        for node in ast.walk(decoder)
        if isinstance(node, ast.Compare) and any(isinstance(op, ast.NotIn) for op in node.ops)
    )
    assert ast.literal_eval(guard.comparators[0]) == "\n\t\r"
    validation = _source(_function("_validate"))
    assert (
        validation.index('source_text = payload["source_text"]')
        < validation.index('source_bytes = source_text.encode("utf-8")')
        < validation.index("source_text != POLICY_SOURCES[candidate]")
    )
    assert validation.index("source_text != POLICY_SOURCES[candidate]") < validation.index(
        "source_hash = hashlib.sha256(source_bytes).hexdigest()"
    )
    assert ".strip()" not in validation and ".replace(" not in validation
    for field in ("_identifier", "_scope"):
        assert "ord(char) < 32" in _source(_function(field))


def test_received_source_is_never_reassigned_before_the_only_compilation():
    observe = _function("_observe")
    assert [argument.arg for argument in observe.args.args] == ["source_text", "cases"]
    assert not any(
        isinstance(node, ast.Name) and node.id == "source_text" and isinstance(node.ctx, ast.Store)
        for node in ast.walk(observe)
    )
    assert "POLICY_SOURCES" not in _source(observe)
    assert 'payload["source_text"]' not in _source(_function("main")).split("result =", 1)[1]
