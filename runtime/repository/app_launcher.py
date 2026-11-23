"""Opt-in external A entry; its startup hint remains untrusted auxiliary data."""

from __future__ import annotations

from types import CoroutineType

SCRIPT_PATH = "/opt/authzest-repository-guest/app_launcher.py"
READY_MARKER = "AUTHZEST_REPOSITORY_A_STARTED\n"
TRUSTED_PRELOAD = (
    "uvicorn",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.lifespan.off",
    "uvicorn.loops.asyncio",
    "fastapi",
)
SERVER_SETTINGS = {
    "host": "127.0.0.1",
    "port": 8765,
    "workers": 1,
    "reload": False,
    "interface": "asgi3",
    "loop": "asyncio",
    "http": "h11",
    "ws": "none",
    "lifespan": "off",
    "access_log": False,
    "proxy_headers": False,
    "env_file": None,
    "log_config": None,
    "server_header": False,
    "date_header": False,
    "forwarded_allow_ips": "",
    "factory": False,
}


def run_ready_app(app, config_factory, server_type, *, write, flush) -> None:
    """Serve the explicit app object with maintained fixed server settings.

    Target code shares streams and can forge the hint. Host-owned independent
    observations and bounded cleanup remain necessary; this is no attestation.
    """

    class StartedServer(server_type):
        async def startup(self, sockets=None):
            await super().startup(sockets=sockets)
            if self.started is True and self.should_exit is False:
                count = write(READY_MARKER)
                if type(count) is CoroutineType:
                    count.close()
                if type(count) is not int or count != len(READY_MARKER):
                    raise ValueError("repository-guest-startup-hint")
                answer = flush()
                if type(answer) is CoroutineType:
                    answer.close()
                if answer is not None:
                    raise ValueError("repository-guest-startup-hint")

    async def explicit_asgi(scope, receive, send):
        # Uvicorn can probe even factory=False with a zero-argument call.
        # The trusted required-argument wrapper refuses that probe before the
        # target is entered; only an actual ASGI request invokes the app.
        await app(scope, receive, send)

    answer = StartedServer(config_factory(explicit_asgi, **SERVER_SETTINGS)).run()
    if type(answer) is CoroutineType:
        answer.close()
    if answer is not None:
        raise ValueError("repository-guest-server-return")


def _script_main() -> int:
    import importlib
    import os
    import sys

    if __file__ != SCRIPT_PATH or sys.platform != "linux":
        return 64
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
        "A",
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
        manifest = load_manifest("A")
        require_kernel_controls("A", manifest)
        verify_input_files(manifest, "A")
    except (OSError, ValueError):
        return 78
    trusted = {name: importlib.import_module(name) for name in TRUSTED_PRELOAD}
    app = import_application(
        manifest,
        "A",
        import_module=importlib.import_module,
        modules=sys.modules,
        search_path=sys.path,
        stdlib_names=sys.stdlib_module_names,
    )
    run_ready_app(
        app,
        trusted["uvicorn"].Config,
        trusted["uvicorn"].Server,
        write=sys.stdout.write,
        flush=sys.stdout.flush,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(_script_main())
