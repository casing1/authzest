"""Fixed T entry source. Reports and exit status are untrusted auxiliary data."""

from __future__ import annotations

from enum import IntEnum
from types import CoroutineType

SCRIPT_PATH = "/opt/authzest-guest/test_launcher.py"
PYTEST_ARGS = (
    "-c",
    "/dev/null",
    "--rootdir=/input",
    "--confcutdir=/input",
    "--noconftest",
    "--override-ini=addopts=",
    "--import-mode=importlib",
    "-p",
    "no:cacheprovider",
    "/input/tests/test_generated_ownership.py",
)


def run_test(pytest_main) -> int:
    """Call an explicit trusted pytest entry; never interpret its output as proof."""
    code = pytest_main(list(PYTEST_ARGS), plugins=[])
    if type(code) is CoroutineType:
        code.close()
    if type(code) is int or isinstance(code, IntEnum):
        native = int.__int__(code)
        if 0 <= native <= 5:
            return native
    raise ValueError("guest-test-exit-contract")


def _script_main() -> int:
    import os
    import sys

    if __file__ != SCRIPT_PATH or sys.platform != "linux":
        return 64
    sys.path.insert(0, "/opt/authzest-guest")
    from _guest_common import entry_allowed, prepare_environment

    if not entry_allowed(
        "T",
        script_path=__file__,
        argv=sys.argv,
        platform=sys.platform,
        isolated=sys.flags.isolated,
        dont_write_bytecode=sys.dont_write_bytecode,
        uid=os.getuid(),
        gid=os.getgid(),
    ):
        return 64
    prepare_environment(os.environ, sys.path)
    import pytest

    # Only after trusted pytest is loaded may the generated module be importable.
    sys.path.insert(0, "/input")
    return run_test(pytest.main)


if __name__ == "__main__":
    raise SystemExit(_script_main())
