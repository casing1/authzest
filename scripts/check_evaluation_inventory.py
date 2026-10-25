"""Check historical artifact bytes, not labels, consent, or benchmark readiness.

This source-checkout utility never imports or executes inventoried sources. It
expects a stable local checkout, not a hostile concurrently changing filesystem.
"""

import argparse
import hashlib
import json
import re
import stat
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = "tests/fixtures/evaluation_inventory.json"
MAX_MANIFEST_BYTES = 256 * 1024
MAX_ARTIFACT_BYTES = 4 * 1024 * 1024
MAX_FILES = 64
MAX_GROUPS = 16
KINDS = {
    "declaration-mock",
    "developer-cases",
    "label-review-record",
    "historical-observations",
    "repair-pair-reference",
}


class InventoryError(ValueError):
    """An inventory is malformed or its recorded artifact bytes do not match."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise InventoryError(message)


def _keys(value: object, expected: set[str], context: str) -> None:
    _require(type(value) is dict and set(value) == expected, f"invalid {context} fields")


def _text(value: object) -> bool:
    return (
        type(value) is str
        and 0 < len(value) <= 2048
        and bool(value.strip())
        and all(character.isprintable() for character in value)
    )


def _slug(value: object) -> bool:
    return type(value) is str and re.fullmatch(r"[a-z][a-z0-9-]{0,79}", value) is not None


def _read(root: Path, relative: object, limit: int) -> bytes:
    _require(
        type(relative) is str
        and len(relative) <= 240
        and re.fullmatch(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+", relative) is not None
        and all(part not in {".", ".."} for part in relative.split("/"))
        and relative.startswith(("tests/fixtures/", "src/authzest/codex/")),
        "invalid artifact path (expected a canonical fixture or Codex source path)",
    )
    current = root
    try:
        parts = relative.split("/")
        for index, part in enumerate(parts):
            current = current / part
            mode = current.lstat().st_mode
            _require(not stat.S_ISLNK(mode), f"symlink not allowed: {relative}")
            expected = stat.S_ISREG if index == len(parts) - 1 else stat.S_ISDIR
            _require(expected(mode), f"non-regular artifact path: {relative}")
        with current.open("rb") as stream:
            data = stream.read(limit + 1)
    except OSError as error:
        raise InventoryError(f"cannot read artifact: {relative}") from error
    _require(len(data) <= limit, f"artifact exceeds byte limit: {relative}")
    return data


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        _require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def _manifest(root: Path, path: str) -> dict:
    raw = _read(root, path, MAX_MANIFEST_BYTES)
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeError, ValueError, RecursionError) as error:
        raise InventoryError("invalid manifest JSON") from error
    _keys(
        value,
        {"schema_version", "kind", "candidate_status", "independent_benchmark_review", "groups"},
        "manifest",
    )
    _require(value["schema_version"] == "1.0", "unsupported manifest schema")
    _require(value["kind"] == "historical-evaluation-inventory", "unsupported manifest kind")
    _require(value["candidate_status"] == "not-selected", "inventory cannot select a benchmark")
    _require(
        value["independent_benchmark_review"] == "not-established",
        "inventory cannot establish independent benchmark review",
    )
    _require(
        type(value["groups"]) is list and 1 <= len(value["groups"]) <= MAX_GROUPS,
        "invalid group count",
    )
    return value


def check_inventory(root: Path, manifest_path: str = DEFAULT_MANIFEST) -> dict:
    """Return matched byte integrity and separately declared reference metadata.

    SHA256 detects drift relative to this manifest, not authenticity: editing both
    an artifact and its digest can still match. Metadata is not independently verified.
    """
    root = root.resolve()
    value = _manifest(root, manifest_path)
    ids: set[str] = set()
    paths: set[str] = set()
    groups = []
    for group in value["groups"]:
        _keys(
            group,
            {
                "id",
                "evidence_kind",
                "declared_counts",
                "authorship",
                "review",
                "split",
                "observations",
                "files",
            },
            "group",
        )
        _require(_slug(group["id"]) and group["id"] not in ids, "invalid or duplicate group id")
        ids.add(group["id"])
        _require(
            type(group["evidence_kind"]) is str and group["evidence_kind"] in KINDS,
            "unsupported evidence kind",
        )
        counts = group["declared_counts"]
        _require(
            type(counts) is dict
            and 1 <= len(counts) <= 8
            and all(
                _slug(key) and type(count) is int and 1 <= count <= 10000
                for key, count in counts.items()
            ),
            "invalid declared counts",
        )
        _require(
            all(_text(group[key]) for key in ("authorship", "review", "split", "observations")),
            "invalid declared metadata",
        )
        _require(
            type(group["files"]) is list and 1 <= len(group["files"]) <= MAX_FILES,
            "invalid artifact count",
        )
        for artifact in group["files"]:
            _keys(artifact, {"path", "sha256"}, "artifact")
            path, digest = artifact["path"], artifact["sha256"]
            _require(
                type(path) is str and path not in paths and path != manifest_path,
                "invalid, duplicate, or self-referencing artifact path",
            )
            _require(
                type(digest) is str and re.fullmatch(r"[0-9a-f]{64}", digest) is not None,
                "invalid SHA256 digest",
            )
            paths.add(path)
            _require(len(paths) <= MAX_FILES, "too many artifacts")
            actual = hashlib.sha256(_read(root, path, MAX_ARTIFACT_BYTES)).hexdigest()
            _require(actual == digest, f"artifact drift: {path}")
        groups.append(group)
    return {
        "kind": "historical-evaluation-inventory-check",
        "schema_version": "1.0",
        "status": "matched",
        "groups": groups,
        "artifact_count": len(paths),
        "candidate_status": "not-selected",
        "independent_benchmark_review": "not-established",
        "metadata_validation": "declared-not-attested",
        "provider_calls": 0,
        "execution_status": "not-run",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--json", action="store_true", help="emit a machine-readable result")
    args = parser.parse_args(argv)
    try:
        result = check_inventory(ROOT)
    except InventoryError as error:
        result = {
            "kind": "historical-evaluation-inventory-check",
            "schema_version": "1.0",
            "status": "invalid",
            "error": str(error),
            "provider_calls": 0,
            "execution_status": "not-run",
        }
        print(json.dumps(result, sort_keys=True) if args.json else f"Inventory invalid: {error}")
        return 1
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(
            f"Historical inventory: {len(result['groups'])} groups, "
            f"{result['artifact_count']} artifact hashes matched."
        )
        for group in result["groups"]:
            counts = ", ".join(
                f"{key}={count}" for key, count in sorted(group["declared_counts"].items())
            )
            print(f"  {group['id']} ({group['evidence_kind']}): {counts} [declared]")
        print(
            "Metadata: declared, not attested. New benchmark: not selected; "
            "independent review: not established."
        )
        print("No AI calls or target execution. A match is not an accuracy or security result.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
