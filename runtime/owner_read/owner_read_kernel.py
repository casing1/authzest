"""Check this owner-read guest's fixed Linux controls before importing test code."""

from __future__ import annotations

import os
import stat
import sys

if __package__ == "runtime.owner_read":
    from runtime.generated_repair import _guest_common as common
else:
    # The image installs these trusted helpers beside this module.
    import _guest_common as common

_INPUTS = ("availability.py", "test_owner_archived_read.py")
_UID = 65532


def _refuse() -> None:
    raise ValueError("owner-read-guest-controls")


def _read(path: str, limit: int = 65_536) -> str:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        _refuse()
    return common._kernel_text(data.decode("ascii"))


def _check_process(status: str) -> None:
    fields = {}
    for line in status.splitlines():
        name, sep, value = line.partition(":")
        if not sep or name in fields or len(fields) >= 128:
            _refuse()
        fields[name] = value.strip()
    for name, expected in (
        ("NoNewPrivs", "1"),
        ("Seccomp", "2"),
        ("Pid", "1"),
        ("PPid", "0"),
        ("NSpid", "1"),
    ):
        if fields.get(name) != expected:
            _refuse()
    if not 1 <= common._number(fields.get("Seccomp_filters")) <= 64:
        _refuse()
    for name in ("CapInh", "CapPrm", "CapEff", "CapBnd", "CapAmb"):
        if common._number(fields.get(name), base=16) != 0:
            _refuse()
    for name in ("Uid", "Gid"):
        if fields.get(name, "").split() != [str(_UID)] * 4:
            _refuse()
    if "Groups" not in fields or set(fields["Groups"].split()) - {str(_UID)}:
        _refuse()


def _check_limits() -> None:
    if _read("/proc/self/cgroup", 256) != "0::/\n":
        _refuse()
    for name, expected in (
        ("memory.max", 512 * 1024**2),
        ("memory.swap.max", 0),
        ("pids.max", 64),
    ):
        if common._number(_read("/sys/fs/cgroup/" + name, 64).strip()) != expected:
            _refuse()
    quota = _read("/sys/fs/cgroup/cpu.max", 64).split()
    if len(quota) != 2:
        _refuse()
    limit, period = map(common._number, quota)
    if not 1_000 <= period <= 1_000_000 or limit != period:
        _refuse()


def _check_mounts(mountinfo: str) -> None:
    mounts = {}
    for line in mountinfo.splitlines():
        columns = line.split()
        if len(columns) < 10 or len(mounts) >= 128 or columns.count("-") != 1:
            _refuse()
        split = columns.index("-")
        if split < 6 or len(columns) != split + 4 or columns[4] in mounts:
            _refuse()
        mounts[columns[4]] = (common._options(columns[5]), columns[split + 1], columns[-1])
    inputs = {"/input/" + name for name in _INPUTS}
    if {name for name in mounts if name == "/input" or name.startswith("/input/")} != inputs:
        _refuse()
    for path in {"/", *inputs}:
        flags = mounts.get(path, ({}, "", ""))[0]
        if "ro" not in flags or "rw" in flags:
            _refuse()
    for path, size in (("/tmp", 32 << 20), ("/dev/shm", 8 << 20)):
        flags, kind, raw = mounts.get(path, ({}, "", ""))
        if (
            kind != "tmpfs"
            or "ro" in flags
            or not {"rw", "nodev", "noexec", "nosuid"} <= flags.keys()
        ):
            _refuse()
        opts = common._options(raw)
        if common._size(opts.get("size", "")) != size:
            _refuse()
        if path == "/tmp" and (
            opts.get("uid") != str(_UID)
            or opts.get("gid") != str(_UID)
            or opts.get("mode") not in {"0700", "700"}
        ):
            _refuse()


def _check_inputs() -> None:
    directory = os.open("/input", os.O_RDONLY | os.O_NOFOLLOW | os.O_DIRECTORY)
    try:
        names = set()
        with os.scandir(directory) as entries:
            for entry in entries:
                if entry.name not in _INPUTS or entry.name in names:
                    _refuse()
                names.add(entry.name)
        if names != set(_INPUTS):
            _refuse()
        for name in _INPUTS:
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
            try:
                info = os.fstat(fd)
                if (
                    not stat.S_ISREG(info.st_mode)
                    or info.st_nlink != 1
                    or not 0 < info.st_size <= 4096
                    or not os.fstatvfs(fd).f_flag & os.ST_RDONLY
                ):
                    _refuse()
            finally:
                os.close(fd)
    finally:
        os.close(directory)


def require_guest_controls() -> None:
    """Observe this process only. Host-side image, mount-source and cleanup checks are separate."""
    if (
        sys.platform != "linux"
        or sys.flags.isolated != 1
        or not sys.flags.dont_write_bytecode
        or sys.flags.optimize != 0
        or os.getpid() != 1
        or os.getuid() != _UID
        or os.getgid() != _UID
    ):
        _refuse()
    _check_process(_read("/proc/self/status"))
    _check_limits()
    network = _read("/proc/net/dev")
    names = common._network_names(network)
    before = common._read_network_snapshot(names, _read)
    after = common._read_network_snapshot(names, _read)
    common._check_network(
        {
            "network": network,
            "network_interfaces": {
                "before": before,
                "after": after,
                "names_after": common._network_names(_read("/proc/net/dev")),
            },
        }
    )
    _check_mounts(_read("/proc/self/mountinfo"))
    temp = os.stat("/tmp", follow_symlinks=False)
    if (
        not stat.S_ISDIR(temp.st_mode)
        or stat.S_IMODE(temp.st_mode) != 0o700
        or (temp.st_uid, temp.st_gid) != (_UID, _UID)
    ):
        _refuse()
    _check_inputs()
