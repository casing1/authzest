"""Fixed independent A entry source, not a host server or health-check command."""

from __future__ import annotations

from types import CoroutineType

SCRIPT_PATH = "/opt/authzest-guest/app_launcher.py"


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


def _script_main() -> int:
    import os
    import sys

    if __file__ != SCRIPT_PATH or sys.platform != "linux":
        return 64
    sys.path.insert(0, "/opt/authzest-guest")
    from _guest_common import entry_allowed, prepare_environment

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
    import uvicorn

    run_app(uvicorn.run)
    return 0


if __name__ == "__main__":
    raise SystemExit(_script_main())
