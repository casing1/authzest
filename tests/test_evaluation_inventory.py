import copy
import hashlib
import json
import os
import socket
import subprocess
from pathlib import Path

import pytest
from scripts import check_evaluation_inventory as inventory

MANIFEST_PATH = "tests/fixtures/evaluation_inventory.json"
ARTIFACT_PATH = "tests/fixtures/example/main.py"


def write_manifest(root, manifest):
    path = root / MANIFEST_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def artifact(root, path=ARTIFACT_PATH, content=b"raise AssertionError('must not execute')\n"):
    destination = root / path
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(content)
    return {"path": path, "sha256": hashlib.sha256(content).hexdigest()}


@pytest.fixture
def example(tmp_path):
    manifest = {
        "schema_version": "1.0",
        "kind": "historical-evaluation-inventory",
        "candidate_status": "not-selected",
        "independent_benchmark_review": "not-established",
        "groups": [
            {
                "id": "historical-mock",
                "evidence_kind": "declaration-mock",
                "declared_counts": {"case-count": 1},
                "authorship": "Assistant-authored reference material.",
                "review": "Policy criteria approved; exact independent review not established.",
                "split": "Historical split only; no new evaluation split selected.",
                "observations": "No execution or live model measurement in this check.",
                "files": [artifact(tmp_path)],
            }
        ],
    }
    write_manifest(tmp_path, manifest)
    return tmp_path, manifest


def test_committed_inventory_matches_without_promoting_reference_metadata():
    result = inventory.check_inventory(Path(__file__).resolve().parents[1])
    assert result["kind"] == "historical-evaluation-inventory-check"
    assert result["schema_version"] == "1.0"
    assert result["status"] == "matched"
    assert result["candidate_status"] == "not-selected"
    assert result["independent_benchmark_review"] == "not-established"
    assert result["metadata_validation"] == "declared-not-attested"
    assert result["provider_calls"] == 0
    assert result["execution_status"] == "not-run"
    assert result["artifact_count"] == sum(len(group["files"]) for group in result["groups"])
    assert {group["evidence_kind"] for group in result["groups"]} == {
        "declaration-mock",
        "developer-cases",
        "label-review-record",
        "historical-observations",
        "repair-pair-reference",
    }


def test_only_inventoried_artifacts_have_explicit_lf_checkout_attributes():
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / MANIFEST_PATH).read_text(encoding="utf-8"))
    expected = sorted(
        [item["path"], "text", "eol=lf"] for group in manifest["groups"] for item in group["files"]
    )
    lines = (root / ".gitattributes").read_text(encoding="utf-8").splitlines()
    actual = sorted(
        line.split() for line in lines if line.strip() and not line.lstrip().startswith("#")
    )
    assert actual == expected


def test_bytes_only_deterministic_check_does_not_execute_sources_or_processes(example, monkeypatch):
    root, manifest = example

    def forbidden(*args, **kwargs):
        pytest.fail("Inventory checking must not execute a process or contact a network")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    first = inventory.check_inventory(root)
    assert first == inventory.check_inventory(root)
    assert first["groups"] == manifest["groups"]
    assert first["artifact_count"] == 1
    assert first["provider_calls"] == 0
    assert first["execution_status"] == "not-run"


def test_matching_bytes_do_not_attest_changed_metadata_or_artifact_authenticity(example):
    root, manifest = example
    group = manifest["groups"][0]
    group["review"] = "An arbitrary review claim is declared, not verified by this utility."
    group["declared_counts"] = {"case-count": 999}
    group["files"] = [artifact(root, content=b"replacement source and updated digest\n")]
    write_manifest(root, manifest)
    result = inventory.check_inventory(root)
    assert result["groups"] == manifest["groups"]
    assert result["status"] == "matched"
    assert result["metadata_validation"] == "declared-not-attested"
    assert result["independent_benchmark_review"] == "not-established"


@pytest.mark.parametrize("level", ["root", "group", "file"])
@pytest.mark.parametrize("operation", ["extra", "missing"])
def test_schema_requires_exact_keys(example, level, operation):
    root, manifest = example
    target = {
        "root": manifest,
        "group": manifest["groups"][0],
        "file": manifest["groups"][0]["files"][0],
    }[level]
    if operation == "extra":
        target["extra"] = "unrecognized"
    else:
        del target[next(iter(target))]
    write_manifest(root, manifest)
    with pytest.raises(inventory.InventoryError):
        inventory.check_inventory(root)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("schema_version", "2.0"),
        ("schema_version", 1),
        ("kind", "evaluation-result"),
        ("candidate_status", "frozen"),
        ("independent_benchmark_review", "approved"),
        ("groups", []),
        ("groups", {}),
        ("groups", [None]),
    ],
)
def test_root_values_are_strict(example, key, value):
    root, manifest = example
    manifest[key] = value
    write_manifest(root, manifest)
    with pytest.raises(inventory.InventoryError):
        inventory.check_inventory(root)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("id", ""),
        ("id", "Uppercase"),
        ("id", "space separated"),
        ("id", "한글"),
        ("evidence_kind", "live-benchmark"),
        ("declared_counts", {}),
        ("declared_counts", []),
        ("declared_counts", {"case count": 1}),
        ("declared_counts", {"count": 0}),
        ("declared_counts", {"count": 10_001}),
        ("declared_counts", {"count": True}),
        ("declared_counts", {"count": 1.0}),
        ("declared_counts", {"count": "1"}),
        ("declared_counts", {f"count-{index}": 1 for index in range(9)}),
        ("files", []),
        ("files", {}),
        ("files", [None]),
    ],
)
def test_group_values_are_strict(example, key, value):
    root, manifest = example
    manifest["groups"][0][key] = value
    write_manifest(root, manifest)
    with pytest.raises(inventory.InventoryError):
        inventory.check_inventory(root)


@pytest.mark.parametrize("key", ["authorship", "review", "split", "observations"])
@pytest.mark.parametrize("value", ["", " ", None, {}, True, "x" * 2049, "bad\ntext", "bad\x7f"])
def test_metadata_text_is_nonempty_bounded_and_control_free(example, key, value):
    root, manifest = example
    manifest["groups"][0][key] = value
    write_manifest(root, manifest)
    with pytest.raises(inventory.InventoryError):
        inventory.check_inventory(root)


@pytest.mark.parametrize("value", ["0" * 63, "A" * 64, "g" * 64, None, True, "0" * 65])
def test_digest_is_lowercase_sha256(example, value):
    root, manifest = example
    manifest["groups"][0]["files"][0]["sha256"] = value
    write_manifest(root, manifest)
    with pytest.raises(inventory.InventoryError):
        inventory.check_inventory(root)


@pytest.mark.parametrize(
    "value",
    [
        "../outside.py",
        "/tmp/outside.py",
        "C:/outside.py",
        "tests/fixtures/../outside.py",
        "tests/fixtures/./example/main.py",
        "tests//fixtures/example/main.py",
        "tests/fixtures/example/main.py/",
        "tests\\fixtures\\example\\main.py",
        "tests/fixtures/\x00.py",
        "tests/fixtures/한글.py",
        "tests/test_example.py",
        "src/authzest/runner/example.py",
        "docs/reference/example.json",
        "",
        None,
    ],
)
def test_artifact_paths_are_canonical_and_scoped(example, value):
    root, manifest = example
    manifest["groups"][0]["files"][0]["path"] = value
    write_manifest(root, manifest)
    with pytest.raises(inventory.InventoryError):
        inventory.check_inventory(root)


@pytest.mark.parametrize("duplicate", ["group-id", "within-group", "across-groups"])
def test_duplicate_groups_and_global_paths_are_rejected(example, duplicate):
    root, manifest = example
    group = manifest["groups"][0]
    if duplicate == "within-group":
        group["files"].append(copy.deepcopy(group["files"][0]))
    else:
        second = copy.deepcopy(group)
        if duplicate == "group-id":
            second["files"] = [artifact(root, "tests/fixtures/second.py")]
        else:
            second["id"] = "second-group"
        manifest["groups"].append(second)
    write_manifest(root, manifest)
    with pytest.raises(inventory.InventoryError):
        inventory.check_inventory(root)


@pytest.mark.parametrize("key", ["schema_version", "id", "case-count", "path"])
def test_duplicate_json_keys_are_rejected_at_every_level(example, key):
    root, manifest = example
    path = write_manifest(root, manifest)
    raw = path.read_text(encoding="utf-8")
    raw = raw.replace(f'"{key}":', f'"{key}": null, "{key}":', 1)
    path.write_text(raw, encoding="utf-8")
    with pytest.raises(inventory.InventoryError):
        inventory.check_inventory(root)


@pytest.mark.parametrize(
    "raw",
    [b"{", b"null", b"[]", b"true", b"1", b'"text"', b"\xff", b"[" * 2000 + b"]" * 2000],
)
def test_malformed_json_encoding_and_root_types_are_rejected(example, raw):
    root, _ = example
    (root / MANIFEST_PATH).write_bytes(raw)
    with pytest.raises(inventory.InventoryError):
        inventory.check_inventory(root)


@pytest.mark.parametrize("problem", ["missing-artifact", "changed-bytes", "missing-manifest"])
def test_missing_or_changed_files_fail_closed(example, problem):
    root, _ = example
    if problem == "missing-artifact":
        (root / ARTIFACT_PATH).unlink()
    elif problem == "missing-manifest":
        (root / MANIFEST_PATH).unlink()
    else:
        (root / ARTIFACT_PATH).write_bytes(b"different bytes\r\n")
    with pytest.raises(inventory.InventoryError):
        inventory.check_inventory(root)


def test_manifest_cannot_inventory_itself(example):
    root, manifest = example
    manifest["groups"][0]["files"][0]["path"] = MANIFEST_PATH
    write_manifest(root, manifest)
    with pytest.raises(inventory.InventoryError):
        inventory.check_inventory(root)


def test_artifact_read_error_becomes_a_controlled_inventory_error(example, monkeypatch):
    root, _ = example
    original_open = Path.open

    def denied_open(self, *args, **kwargs):
        if self == root / ARTIFACT_PATH:
            raise PermissionError("test read denial")
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", denied_open)
    with pytest.raises(inventory.InventoryError):
        inventory.check_inventory(root)


@pytest.mark.parametrize("target", ["artifact", "artifact-parent", "manifest"])
def test_symlinks_are_rejected_even_when_the_target_is_within_root(example, target):
    root, _ = example
    path = root / (MANIFEST_PATH if target == "manifest" else ARTIFACT_PATH)
    if target == "artifact-parent":
        path = path.parent
    moved = path.with_name(path.name + "-real")
    path.rename(moved)
    try:
        path.symlink_to(moved, target_is_directory=moved.is_dir())
    except (NotImplementedError, OSError) as error:
        pytest.skip(f"Symlinks unavailable: {error}")
    with pytest.raises(inventory.InventoryError):
        inventory.check_inventory(root)


@pytest.mark.parametrize("target", ["artifact", "manifest"])
def test_directories_are_not_artifacts_or_manifests(example, target):
    root, _ = example
    path = root / (MANIFEST_PATH if target == "manifest" else ARTIFACT_PATH)
    path.unlink()
    path.mkdir()
    with pytest.raises(inventory.InventoryError):
        inventory.check_inventory(root)


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="Named pipes require POSIX")
@pytest.mark.parametrize("target", ["artifact", "manifest"])
def test_named_pipes_are_rejected_without_opening(example, target, monkeypatch):
    root, _ = example
    path = root / (MANIFEST_PATH if target == "manifest" else ARTIFACT_PATH)
    path.unlink()
    os.mkfifo(path)
    original_open = Path.open

    def guarded_open(self, *args, **kwargs):
        if self == path:
            pytest.fail("Inventory must reject a FIFO before attempting to open it")
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)
    with pytest.raises(inventory.InventoryError):
        inventory.check_inventory(root)


def test_manifest_byte_limit_accepts_boundary_and_rejects_one_more_byte(example):
    root, _ = example
    path = root / MANIFEST_PATH
    raw = path.read_bytes()
    path.write_bytes(raw + b" " * (256 * 1024 - len(raw)))
    assert inventory.check_inventory(root)["status"] == "matched"
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(inventory.InventoryError):
        inventory.check_inventory(root)


def test_artifact_byte_limit_accepts_boundary_and_rejects_one_more_byte(example):
    root, manifest = example
    group = manifest["groups"][0]
    for count in [4 * 1024 * 1024, 4 * 1024 * 1024 + 1]:
        group["files"] = [artifact(root, content=b"x" * count)]
        write_manifest(root, manifest)
        if count == 4 * 1024 * 1024:
            assert inventory.check_inventory(root)["status"] == "matched"
        else:
            with pytest.raises(inventory.InventoryError):
                inventory.check_inventory(root)


@pytest.mark.parametrize(
    ("groups", "files", "valid"),
    [(16, 4, True), (17, 1, False), (1, 65, False), (13, 5, False)],
)
def test_group_and_total_file_limits(example, groups, files, valid):
    root, manifest = example
    template = manifest["groups"][0]
    manifest["groups"] = []
    for group_index in range(groups):
        group = copy.deepcopy(template)
        group["id"] = f"group-{group_index}"
        group["files"] = [
            artifact(root, f"tests/fixtures/group-{group_index}/file-{file_index}.json", b"{}")
            for file_index in range(files)
        ]
        manifest["groups"].append(group)
    write_manifest(root, manifest)
    if valid:
        assert inventory.check_inventory(root)["artifact_count"] == 64
    else:
        with pytest.raises(inventory.InventoryError):
            inventory.check_inventory(root)


def test_custom_scoped_manifest_and_source_module_reference(example):
    root, manifest = example
    group = manifest["groups"][0]
    group["files"] = [artifact(root, "src/authzest/codex/reference.py")]
    group["declared_counts"] = {f"count-{index}": 10_000 for index in range(8)}
    group["review"] = "x" * 2048
    path = write_manifest(root, manifest)
    alternate = "tests/fixtures/alternate_inventory.json"
    path.rename(root / alternate)
    assert inventory.check_inventory(root, alternate)["groups"] == manifest["groups"]


def test_cli_json_is_the_same_deterministic_result(example, monkeypatch, capsys):
    root, _ = example
    monkeypatch.setattr(inventory, "ROOT", root)
    assert inventory.main(["--json"]) == 0
    output = capsys.readouterr()
    assert json.loads(output.out) == inventory.check_inventory(root)
    assert not output.err


def test_cli_human_output_is_concise_and_marks_reference_only_status(example, monkeypatch, capsys):
    root, _ = example
    monkeypatch.setattr(inventory, "ROOT", root)
    assert inventory.main([]) == 0
    output = capsys.readouterr()
    assert output.out.strip()
    assert "historical-mock" in output.out
    assert "not selected" in output.out
    assert "not established" in output.out
    assert not output.err


@pytest.mark.parametrize("as_json", [False, True])
def test_cli_errors_return_one_without_traceback(example, monkeypatch, capsys, as_json):
    root, _ = example
    monkeypatch.setattr(inventory, "ROOT", root)
    (root / ARTIFACT_PATH).write_bytes(b"changed")
    assert inventory.main(["--json"] if as_json else []) == 1
    output = capsys.readouterr()
    combined = output.out + output.err
    assert combined.strip()
    assert "Traceback" not in combined
    if as_json:
        result = json.loads(output.out)
        assert result["status"] == "invalid"
        assert isinstance(result["error"], str)
        assert result["provider_calls"] == 0
        assert result["execution_status"] == "not-run"
        assert not output.err


def test_cli_usage_error_returns_argparse_exit_two():
    with pytest.raises(SystemExit) as error:
        inventory.main(["--unrecognized"])
    assert error.value.code == 2
