"""Fixed Linux guest entry for the synthetic owner's archived-note check."""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import stat
import sys
from pathlib import Path
from types import CodeType, FunctionType, ModuleType

_ENTRY = "/opt/authzest-owner/guest.py"
_RULE = Path("/input/availability.py")
_TEST = Path("/input/test_owner_archived_read.py")
_IDENTITIES = {"source_sha256", "test_sha256"}
_LIMIT = 4096


def _identities(raw: bytes) -> dict[str, str]:
    from authzest.codex.contracts import decode

    if not 0 < len(raw) <= 1024:
        raise ValueError("Invalid manifest size")
    value = decode(raw.decode("ascii"))
    if value.keys() != _IDENTITIES or not all(
        type(digest) is str and re.fullmatch(r"[0-9a-f]{64}", digest) for digest in value.values()
    ):
        raise ValueError("Invalid manifest")
    return value


def _snapshot_info(info):
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_nlink,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


def _read_fixed(path: Path, expected: str) -> bytes:
    if path not in (_RULE, _TEST):
        raise ValueError("Unknown input")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb", buffering=0) as stream:
        initial = os.fstat(stream.fileno())
        if (
            not stat.S_ISREG(initial.st_mode)
            or initial.st_nlink != 1
            or not 0 < initial.st_size <= _LIMIT
        ):
            raise ValueError("Invalid input type or size")
        data = bytearray()
        while len(data) <= initial.st_size:
            part = stream.read(initial.st_size + 1 - len(data))
            if not part:
                break
            data.extend(part)
        if (
            len(data) != initial.st_size
            or not data.isascii()
            or hashlib.sha256(data).hexdigest() != expected
            or _snapshot_info(os.fstat(stream.fileno())) != _snapshot_info(initial)
            or _snapshot_info(path.stat(follow_symlinks=False)) != _snapshot_info(initial)
        ):
            raise ValueError("Input identity changed")
    return bytes(data)


def _captured_code(fn: ast.FunctionDef, path: Path) -> FunctionType:
    # Only a function from the closed grammar reaches compilation. Never run the module code.
    module = compile(
        ast.Module(body=[fn], type_ignores=[]),
        str(path),
        "exec",
        dont_inherit=True,
        optimize=0,
    )
    (code,) = (c for c in module.co_consts if isinstance(c, CodeType) and c.co_name == fn.name)
    return FunctionType(code, {"__builtins__": {}, "__name__": "owner_read_capture"})


def _test_observation(rule: FunctionType, test: FunctionType) -> dict:
    import pytest

    from authzest.owner_read_demo import rehearsal
    from authzest.owner_read_demo.app import _app_with_rule

    module = ModuleType("owner_read_capture")
    setattr(module, test.__name__, test)

    class CaptureCollector:
        @pytest.hookimpl(tryfirst=True)
        def pytest_pycollect_makemodule(self, module_path, parent):
            # Use the installed sample as a carrier. Pytest never imports the mounted artifact.
            if module_path.resolve() == rehearsal._SAMPLE:
                collector = pytest.Module.from_parent(parent, path=module_path)
                collector.obj = module
                return collector
            return None

    recorder = rehearsal._PytestObservation(_app_with_rule(rule), captured_test=test)
    return rehearsal._record_pytest(recorder, plugins=[CaptureCollector()])


def _observe(role: str, manifest: bytes) -> dict:
    from authzest.codex.owner_read_suggestion import _validate_rule, _validate_test
    from authzest.owner_read_demo.app import _app_with_rule
    from authzest.owner_read_demo.rehearsal import _collect_controls

    ids = _identities(manifest)
    if role not in ("test", "controls"):
        raise ValueError("Unsupported role")
    rule_bytes = _read_fixed(_RULE, ids["source_sha256"])
    test_bytes = _read_fixed(_TEST, ids["test_sha256"])
    rule_fn = _validate_rule(rule_bytes.decode("ascii"))
    test_fn = _validate_test(test_bytes.decode("ascii")) if role == "test" else None
    rule = _captured_code(rule_fn, _RULE)
    result = {"kind": "owner-read-guest-observation", "schema_version": "1.0", "role": role, **ids}
    if test_fn is not None:
        regression = _test_observation(rule, _captured_code(test_fn, _TEST))
        if regression["status"] == "error":
            raise ValueError("Incomplete pytest observation")
        result["regression"] = regression
    else:
        result["observations"] = _collect_controls(lambda: _app_with_rule(rule))
    return result


def _permitted_entry() -> bool:
    return (
        __file__ == _ENTRY
        and sys.platform == "linux"
        and len(sys.argv) == 2
        and sys.argv[0] == _ENTRY
        and sys.argv[1] in ("test", "controls")
        and sys.flags.isolated == 1
        and sys.flags.dont_write_bytecode == 1
        and sys.flags.optimize == 0
        and os.getuid() == os.geteuid() == 65532
        and os.getgid() == os.getegid() == 65532
    )


def main() -> int:
    if not _permitted_entry():
        return 64
    sys.path.insert(0, "/opt/authzest-owner")
    try:
        from owner_read_kernel import require_guest_controls

        require_guest_controls()
    except Exception:
        print("owner-read-isolation-refused", file=sys.stderr)
        return 78
    try:
        os.environ.clear()
        os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
        result = _observe(sys.argv[1], sys.stdin.buffer.read(1025))
        print(json.dumps(result, ensure_ascii=True, allow_nan=False, separators=(",", ":")))
    except Exception:
        print("owner-read-observation-failed", file=sys.stderr)
        return 65
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
