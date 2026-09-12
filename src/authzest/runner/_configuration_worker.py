"""Fixed, stdlib-only checker source; fixture bytes are data, never executable code."""

from hashlib import sha256

CHECK_ID = "owned-fixture-debug-disabled-v1"
MAX_INPUT_BYTES = 1024

# This fixed program is shared by isolated Python and the frozen CLI entry point.
# Its two accepted hashes are pinned to the maintained fixture, not caller input.
WORKER_SOURCE = r"""
import ast
import hashlib
import json
import sys

CHECK_ID = "owned-fixture-debug-disabled-v1"
ALLOWED_HASHES = {
    "c10770594e77cd1c1ec93c19ef2b810aea34ed873d8dbf392b57e50a1c2729df",
    "e010818e7259ad5c1ebfc5dfcb6dc046100376c778a70d0657d7ebb1ed7fdcfe",
}


def _main():
    try:
        source = sys.stdin.buffer.read(1025)
        digest = hashlib.sha256(source).hexdigest()
        if len(source) > 1024 or digest not in ALLOWED_HASHES:
            return 2
        tree = ast.parse(source.decode("utf-8"), filename="<owned-fixture>")
        assignments = [
            node for node in tree.body
            if isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "app"
        ]
        if len(assignments) != 1:
            return 2
        call = assignments[0].value
        if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Name):
            return 2
        if call.func.id != "FastAPI" or call.args or len(call.keywords) != 1:
            return 2
        keyword = call.keywords[0]
        if keyword.arg != "debug" or not isinstance(keyword.value, ast.Constant):
            return 2
        debug = keyword.value.value
        if type(debug) is not bool:
            return 2
        result = {
            "schema_version": "1.0",
            "check_id": CHECK_ID,
            "source_sha256": digest,
            "status": "failed" if debug else "passed",
            "reason": "debug-enabled" if debug else "debug-disabled",
        }
        sys.stdout.write(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
        return 0
    except Exception:
        return 2


if __name__ == "__main__":
    raise SystemExit(_main())
""".lstrip()

WORKER_SHA256 = sha256(WORKER_SOURCE.encode("utf-8")).hexdigest()


def worker_main() -> int:
    """Run the same trusted checker in a frozen child; no input is passed to exec."""
    namespace = {"__name__": "authzest_fixed_configuration_worker"}
    exec(compile(WORKER_SOURCE, "<authzest-fixed-configuration-worker>", "exec"), namespace)
    return namespace["_main"]()
