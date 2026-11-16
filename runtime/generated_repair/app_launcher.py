"""Fixed A entry and untrusted startup hint, not a readiness attestation."""

from __future__ import annotations

from types import CoroutineType

SCRIPT_PATH = "/opt/authzest-guest/app_launcher.py"
READY_MARKER = "AUTHZEST_A_STARTED\n"


def run_app(uvicorn_run) -> None:
    """Invoke only the explicit trusted installed server with fixed settings."""
    answer = uvicorn_run(
        "app:app",
        app_dir="/input",
        host="127.0.0.1",
        port=8765,
        workers=1,
        reload=False,
        interface="asgi3",
        loop="asyncio",
        http="h11",
        ws="none",
        lifespan="off",
        access_log=False,
        proxy_headers=False,
        env_file=None,
        log_config=None,
        server_header=False,
        date_header=False,
        forwarded_allow_ips="",
    )
    if type(answer) is CoroutineType:
        answer.close()
    if answer is not None:
        raise ValueError("guest-server-return-contract")


def run_ready_app(config_factory, server_type, *, add_path, write, flush) -> None:
    """Continue serving after the trusted server's startup emits one fixed hint.

    Generated app code shares these streams and can forge the marker. It cannot
    prove readiness, isolation, authorization or a repair; the host still needs
    complete independent B observations and its original time/output limits.
    Collaborators are trusted maintained-test seams, not selectable app inputs.
    """

    class StartedServer(server_type):
        async def startup(self, sockets=None):
            await super().startup(sockets=sockets)
            if self.started is True and self.should_exit is False:
                count = write(READY_MARKER)
                if type(count) is CoroutineType:
                    count.close()
                if type(count) is not int or count != len(READY_MARKER):
                    raise ValueError("guest-readiness-write-contract")
                answer = flush()
                if type(answer) is CoroutineType:
                    answer.close()
                if answer is not None:
                    raise ValueError("guest-readiness-flush-contract")

    def run_configured(app, *, app_dir, **settings):
        # Like uvicorn.run, add the app path only after importing trusted tools.
        add_path(app_dir)
        return StartedServer(config_factory(app, **settings)).run()

    run_app(run_configured)


def _script_main() -> int:
    import os
    import sys

    if __file__ != SCRIPT_PATH or sys.platform != "linux":
        return 64
    sys.path.insert(0, "/opt/authzest-guest")
    from _guest_common import entry_allowed, prepare_environment, require_kernel_controls

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
        require_kernel_controls("A")
    except (OSError, ValueError):
        return 78
    import uvicorn

    run_ready_app(
        uvicorn.Config,
        uvicorn.Server,
        add_path=lambda path: sys.path.insert(0, path),
        write=sys.stdout.write,
        flush=sys.stdout.flush,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(_script_main())
