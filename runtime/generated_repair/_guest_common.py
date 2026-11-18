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


def _number(text, *, base=10):
    pattern = r"[0-9a-f]{1,16}" if base == 16 else r"[0-9]{1,16}"
    if type(text) is not str or re.fullmatch(pattern, text, re.ASCII) is None:
        raise ValueError("guest-kernel-controls")
    return int(text, base)


def _size(text):
    if type(text) is not str:
        raise ValueError("guest-kernel-controls")
    match = re.fullmatch(r"([0-9]{1,12})([kmg]?)", text, re.ASCII)
    if match is None:
        raise ValueError("guest-kernel-controls")
    return int(match[1]) * {"": 1, "k": 1024, "m": 1024**2, "g": 1024**3}[match[2]]


def _options(text):
    result = {}
    for token in text.split(","):
        name, separator, value = token.partition("=")
        if not name or name in result:
            raise ValueError("guest-kernel-controls")
        result[name] = value if separator else None
    return result


def check_kernel_controls(role, observation) -> None:
    """Check bounded supplied kernel facts; no I/O or attestation in this function.

    The fixed image entry calls the actual reader before importing any target.
    These are supported kernel control settings, not resource stress benchmarks,
    escape proof, a host-observed report or permission from imported JSON.
    """
    fields = {
        "pid",
        "uid",
        "gid",
        "status",
        "cgroup",
        "memory",
        "swap",
        "pids",
        "cpu",
        "mountinfo",
        "network",
        "tmp_mode",
        "tmp_uid",
        "tmp_gid",
        "input_readonly",
    }
    if type(role) is not str or role not in _SCRIPTS:
        raise ValueError("guest-kernel-controls")
    if type(observation) is not dict or set(observation) != fields:
        raise ValueError("guest-kernel-controls")
    for key, expected in (
        ("pid", 1),
        ("uid", 65532),
        ("gid", 65532),
        ("tmp_mode", 0o700),
        ("tmp_uid", 65532),
        ("tmp_gid", 65532),
    ):
        if type(observation[key]) is not int or observation[key] != expected:
            raise ValueError("guest-kernel-controls")
    for key in ("status", "cgroup", "memory", "swap", "pids", "cpu", "mountinfo", "network"):
        text = observation[key]
        if (
            type(text) is not str
            or len(text) > 65_536
            or not text.isascii()
            or any((ord(char) < 32 and char not in "\t\n") or ord(char) == 127 for char in text)
        ):
            raise ValueError("guest-kernel-controls")
    status = {}
    for line in observation["status"].splitlines():
        key, separator, value = line.partition(":")
        if not separator or key in status or len(status) >= 128:
            raise ValueError("guest-kernel-controls")
        status[key] = value.strip()
    for key, expected in (
        ("NoNewPrivs", "1"),
        ("Seccomp", "2"),
        ("Pid", "1"),
        ("PPid", "0"),
        ("NSpid", "1"),
    ):
        if status.get(key) != expected:
            raise ValueError("guest-kernel-controls")
    for key in ("Uid", "Gid"):
        if status.get(key, "").split() != ["65532"] * 4:
            raise ValueError("guest-kernel-controls")
    if not 1 <= _number(status.get("Seccomp_filters")) <= 64:
        raise ValueError("guest-kernel-controls")
    for key in ("CapInh", "CapPrm", "CapEff", "CapBnd", "CapAmb"):
        if _number(status.get(key), base=16) != 0:
            raise ValueError("guest-kernel-controls")
    small = role == "B"
    if (
        observation["cgroup"] != "0::/\n"
        or _number(observation["memory"].strip()) != (134_217_728 if small else 536_870_912)
        or _number(observation["swap"].strip()) != 0
        or _number(observation["pids"].strip()) != (32 if small else 64)
    ):
        raise ValueError("guest-kernel-controls")
    cpu = observation["cpu"].split()
    if len(cpu) != 2:
        raise ValueError("guest-kernel-controls")
    quota, period = map(_number, cpu)
    if not 1000 <= period <= 1_000_000 or quota * (2 if small else 1) != period:
        raise ValueError("guest-kernel-controls")
    interfaces = []
    lines = observation["network"].splitlines()
    if len(lines) != 3:
        raise ValueError("guest-kernel-controls")
    for line in lines[2:]:
        name, separator, _ = line.partition(":")
        if not separator:
            raise ValueError("guest-kernel-controls")
        interfaces.append(name.strip())
    if interfaces != ["lo"]:
        raise ValueError("guest-kernel-controls")
    mounts = {}
    for line in observation["mountinfo"].splitlines():
        columns = line.split()
        if len(columns) < 10 or len(mounts) >= 128 or columns.count("-") != 1:
            raise ValueError("guest-kernel-controls")
        split = columns.index("-")
        if split < 6 or len(columns) != split + 4 or columns[4] in mounts:
            raise ValueError("guest-kernel-controls")
        mounts[columns[4]] = (_options(columns[5]), columns[split + 1], _options(columns[-1]))
    if "/" not in mounts or "ro" not in mounts["/"][0] or "rw" in mounts["/"][0]:
        raise ValueError("guest-kernel-controls")
    for target, size in (("/tmp", 8_388_608 if small else 33_554_432), ("/dev/shm", 8_388_608)):
        flags, kind, options = mounts.get(target, ({}, "", {}))
        if (
            kind != "tmpfs"
            or not {"rw", "nosuid", "nodev", "noexec"} <= set(flags)
            or "ro" in flags
            or _size(options.get("size", "")) != size
        ):
            raise ValueError("guest-kernel-controls")
        if target == "/tmp" and (
            options.get("uid") != "65532"
            or options.get("gid") != "65532"
            or options.get("mode") not in ("700", "0700")
        ):
            raise ValueError("guest-kernel-controls")
    expected_inputs = [] if small else ["/input/app.py"]
    if role == "T":
        expected_inputs.append("/input/tests/test_generated_ownership.py")
    if sorted(name for name in mounts if name == "/input" or name.startswith("/input/")) != sorted(
        expected_inputs
    ):
        raise ValueError("guest-kernel-controls")
    if (
        type(observation["input_readonly"]) is not list
        or len(observation["input_readonly"]) != len(expected_inputs)
        or any(value is not True for value in observation["input_readonly"])
    ):
        raise ValueError("guest-kernel-controls")
    for target in expected_inputs:
        if "ro" not in mounts[target][0] or "rw" in mounts[target][0]:
            raise ValueError("guest-kernel-controls")


def require_kernel_controls(role) -> None:
    """Read only fixed Linux kernel/filesystem paths, before any target import.

    No process, network, writes, retries or target contents are used. An absent
    property is unsupported. Blocking kernel operations still rely on the host
    phase deadline/cleanup, rather than a universal guest-side wall-time bound.
    """
    import os
    import stat

    if type(role) is not str or role not in _SCRIPTS:
        raise ValueError("guest-kernel-controls")

    def read(path):
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        failure = None
        try:
            data = bytearray()
            while True:
                chunk = os.read(fd, min(4096, 65_537 - len(data)))
                data.extend(chunk)
                if len(data) > 65_536:
                    raise ValueError("guest-kernel-controls")
                if not chunk:
                    return bytes(data).decode("ascii")
        except BaseException as exc:
            failure = exc
            raise
        finally:
            try:
                os.close(fd)
            except BaseException as exc:
                if (
                    failure is None
                    or isinstance(failure, Exception)
                    and not isinstance(exc, Exception)
                ):
                    raise
                failure.guest_kernel_descriptor_cleanup_unconfirmed = True

    folder = os.stat("/tmp", follow_symlinks=False)
    if not stat.S_ISDIR(folder.st_mode):
        raise ValueError("guest-kernel-controls")
    inputs = [] if role == "B" else ["/input/app.py"]
    if role == "T":
        inputs.append("/input/tests/test_generated_ownership.py")
    observation = {
        "pid": os.getpid(),
        "uid": os.getuid(),
        "gid": os.getgid(),
        "status": read("/proc/self/status"),
        "cgroup": read("/proc/self/cgroup"),
        "memory": read("/sys/fs/cgroup/memory.max"),
        "swap": read("/sys/fs/cgroup/memory.swap.max"),
        "pids": read("/sys/fs/cgroup/pids.max"),
        "cpu": read("/sys/fs/cgroup/cpu.max"),
        "mountinfo": read("/proc/self/mountinfo"),
        "network": read("/proc/net/dev"),
        "tmp_mode": stat.S_IMODE(folder.st_mode),
        "tmp_uid": folder.st_uid,
        "tmp_gid": folder.st_gid,
        "input_readonly": [bool(os.statvfs(path).f_flag & os.ST_RDONLY) for path in inputs],
    }
    check_kernel_controls(role, observation)
