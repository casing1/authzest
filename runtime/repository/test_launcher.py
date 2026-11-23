"""Opt-in external T entry; generated pytest output is auxiliary, not proof."""

from __future__ import annotations

from enum import IntEnum
from types import CoroutineType

SCRIPT_PATH = "/opt/authzest-repository-guest/test_launcher.py"
PYTEST_ARGS = (
    "-c",
    "/dev/null",
    "--rootdir=/input/tests",
    "--confcutdir=/input/tests",
    "--noconftest",
    "--override-ini=addopts=",
    "--import-mode=importlib",
    "-p",
    "no:cacheprovider",
    "/input/tests/test_authzest_regression.py",
)
TRUSTED_PRELOAD = (
    "pytest",
    "fastapi.testclient",
    "httpx",
    "httpcore",
    "h11",
    "anyio._backends._asyncio",
)


def run_test(app, *, pytest_main, fixture, test_client) -> int:
    """Supply one trusted client fixture; never start lifespan or change auth."""

    class ClientPlugin:
        @fixture(name="client")
        def client(self):
            # Deliberately no context manager: TestClient's lifespan runs only
            # on context entry. No dependency overrides are installed.
            client = test_client(app)
            try:
                yield client
            finally:
                client.close()

    code = pytest_main(list(PYTEST_ARGS), plugins=[ClientPlugin()])
    if type(code) is CoroutineType:
        code.close()
    if type(code) is int or isinstance(code, IntEnum):
        native = int.__int__(code)
        if 0 <= native <= 5:
            return native
    raise ValueError("repository-guest-test-exit")


def _script_main() -> int:
    import importlib
    import os
    import sys

    if __file__ != SCRIPT_PATH or sys.platform != "linux":
        return 64
    # Only immutable image code is visible here; project paths remain absent.
    sys.path.insert(0, "/opt/authzest-repository-guest")
    from _guest_common import (
        entry_allowed,
        import_application,
        load_manifest,
        prepare_environment,
        require_kernel_controls,
        verify_input_files,
    )

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
    try:
        manifest = load_manifest("T")
        require_kernel_controls("T", manifest)
        verify_input_files(manifest, "T")
    except (OSError, ValueError):
        return 78
    trusted = {name: importlib.import_module(name) for name in TRUSTED_PRELOAD}
    app = import_application(
        manifest,
        "T",
        import_module=importlib.import_module,
        modules=sys.modules,
        search_path=sys.path,
        stdlib_names=sys.stdlib_module_names,
    )
    return run_test(
        app,
        pytest_main=trusted["pytest"].main,
        fixture=trusted["pytest"].fixture,
        test_client=trusted["fastapi.testclient"].TestClient,
    )


if __name__ == "__main__":
    raise SystemExit(_script_main())
