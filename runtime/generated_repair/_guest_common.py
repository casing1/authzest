"""Diagnostic entry guards, not a sandbox or proof of a reviewed container."""

from __future__ import annotations

import posixpath
import re

GUEST_ROOT = "/opt/authzest-guest"
_SCRIPTS = {"T": "test_launcher.py", "A": "app_launcher.py", "B": "relay_launcher.py"}


def entry_allowed(
    role, *, script_path, argv, platform, isolated, dont_write_bytecode, uid, gid
) -> bool:
    """Refuse accidental host invocation; immutable images remain a separate gate."""
    if type(role) is not str or role not in _SCRIPTS:
        return False
    expected = GUEST_ROOT + "/" + _SCRIPTS[role]
    if (
        type(script_path) is not str
        or script_path != expected
        or type(argv) is not list
        or len(argv) != (2 if role == "B" else 1)
        or any(type(value) is not str for value in argv)
        or argv[0] != expected
        or type(platform) is not str
        or platform != "linux"
        or type(isolated) not in (int, bool)
        or isolated != 1
        or type(dont_write_bytecode) not in (int, bool)
        or dont_write_bytecode != 1
        or type(uid) is not int
        or type(gid) is not int
        or uid != 65532
        or gid != 65532
    ):
        return False
    if role == "B":
        value = argv[1]
        return (
            len(value) <= 5
            and re.fullmatch(r"[1-9][0-9]*", value) is not None
            and int(value) <= 40000
        )
    return True


def prepare_environment(environ, search_path) -> None:
    """Clear inherited configuration before importing trusted installed tools."""
    if type(search_path) is not list or any(type(value) is not str for value in search_path):
        raise ValueError("guest-search-path")
    kept = []
    for value in search_path:
        if not value.startswith("/"):
            continue
        normalized = posixpath.normpath("/" + value.lstrip("/"))
        if normalized != "/input" and not normalized.startswith("/input/"):
            kept.append(value)
    search_path[:] = kept
    environ.clear()
    environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
