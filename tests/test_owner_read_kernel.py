"""Supplied Linux observations and disposable input files for the dedicated owner-read guest."""

import os
import stat
from types import SimpleNamespace

import pytest
from runtime.owner_read import owner_read_kernel as kernel

_STATUS = """Pid: 1
PPid: 0
NSpid: 1
Uid: 65532 65532 65532 65532
Gid: 65532 65532 65532 65532
Groups: 65532
NoNewPrivs: 1
Seccomp: 2
Seccomp_filters: 1
CapInh: 0
CapPrm: 0
CapEff: 0
CapBnd: 0
CapAmb: 0
"""
_MOUNTS = """1 0 0:1 / / ro,relatime - overlay overlay rw
2 1 0:2 / /tmp rw,nodev,nosuid,noexec - tmpfs tmpfs rw,size=32768k,mode=700,uid=65532,gid=65532
3 1 0:3 / /dev/shm rw,nodev,nosuid,noexec - tmpfs shm rw,size=8192k
4 1 0:4 /source /input/availability.py ro - ext4 /dev/disk rw
5 1 0:4 /test /input/test_owner_archived_read.py ro - ext4 /dev/disk rw
"""
_NETWORK = "Inter-| Receive | Transmit\n face |bytes packets\n lo: 0 0 0 0\n"


@pytest.fixture
def observations(monkeypatch):
    raw = {
        "/proc/self/status": _STATUS,
        "/proc/self/mountinfo": _MOUNTS,
        "/proc/self/cgroup": "0::/\n",
        "/sys/fs/cgroup/memory.max": "536870912\n",
        "/sys/fs/cgroup/memory.swap.max": "0\n",
        "/sys/fs/cgroup/pids.max": "64\n",
        "/sys/fs/cgroup/cpu.max": "100000 100000\n",
        "/proc/net/dev": _NETWORK,
        "/sys/class/net/lo/flags": "0x9\n",
        "/sys/class/net/lo/operstate": "unknown\n",
        "/sys/class/net/lo/type": "772\n",
        "/sys/class/net/lo/ifindex": "1\n",
        "/sys/class/net/lo/iflink": "1\n",
    }

    def read(path, limit=65536):
        assert path in raw and len(raw[path]) <= limit
        return raw[path]

    monkeypatch.setattr(kernel, "_read", read)
    monkeypatch.setattr(kernel, "_check_inputs", lambda: None)
    monkeypatch.setattr(
        kernel,
        "sys",
        SimpleNamespace(
            platform="linux", flags=SimpleNamespace(isolated=1, dont_write_bytecode=1, optimize=0)
        ),
    )
    monkeypatch.setattr(
        kernel,
        "os",
        SimpleNamespace(
            getpid=lambda: 1,
            getuid=lambda: 65532,
            getgid=lambda: 65532,
            stat=lambda *a, **kw: SimpleNamespace(
                st_mode=stat.S_IFDIR | 0o700, st_uid=65532, st_gid=65532
            ),
        ),
    )
    return raw


def test_exact_controls_and_dormant_fallback(observations):
    kernel.require_guest_controls()
    observations["/proc/net/dev"] += " tunl0: 0 0 0 0\n"
    for key, value in (
        ("flags", "0x80"),
        ("operstate", "down"),
        ("type", "768"),
        ("ifindex", "2"),
        ("iflink", "0"),
    ):
        observations["/sys/class/net/tunl0/" + key] = value + "\n"
    kernel.require_guest_controls()
    observations["/sys/class/net/tunl0/operstate"] = "up\n"
    with pytest.raises(ValueError):
        kernel.require_guest_controls()


@pytest.mark.parametrize(
    ("path", "old", "new"),
    [
        ("/proc/self/status", "NoNewPrivs: 1", "NoNewPrivs: 0"),
        ("/proc/self/status", "Seccomp: 2", "Seccomp: 1"),
        ("/proc/self/status", "Seccomp_filters: 1", "Seccomp_filters: 0"),
        ("/proc/self/status", "CapBnd: 0", "CapBnd: 1"),
        ("/proc/self/status", "NSpid: 1", "NSpid: 53 1"),
        ("/proc/self/status", "Gid: 65532", "Gid: 0"),
        ("/proc/self/status", "Groups: 65532", "Groups: 65532 0"),
        ("/proc/self/cgroup", "0::/", "0::/other"),
        ("/sys/fs/cgroup/memory.max", "536870912", "max"),
        ("/sys/fs/cgroup/memory.swap.max", "0", "1"),
        ("/sys/fs/cgroup/pids.max", "64", "max"),
        ("/sys/fs/cgroup/cpu.max", "100000 100000", "200000 100000"),
        ("/proc/net/dev", " lo:", " eth0:"),
        ("/sys/class/net/lo/type", "772", "1"),
        ("/proc/self/mountinfo", "/ / ro,", "/ / rw,"),
        ("/proc/self/mountinfo", "rw,nodev,nosuid,noexec", "rw,nodev,nosuid"),
        ("/proc/self/mountinfo", "32768k", "65536k"),
        ("/proc/self/mountinfo", "8192k", "32768k"),
        ("/proc/self/mountinfo", "mode=700", "mode=755"),
        ("/proc/self/mountinfo", "availability.py ro", "availability.py rw"),
        (
            "/proc/self/mountinfo",
            "test_owner_archived_read.py",
            "tests/test_generated_ownership.py",
        ),
        ("/proc/self/mountinfo", "/source /input/", "/source /"),
        (
            "/proc/self/mountinfo",
            "/dev/disk rw\n",
            "/dev/disk rw\n9 1 0:9 /x /input/other ro - ext4 /dev/test rw\n",
        ),
    ],
)
def test_guest_refuses_changed_controls(observations, path, old, new):
    assert old in observations[path]
    observations[path] = observations[path].replace(old, new, 1)
    with pytest.raises(ValueError):
        kernel.require_guest_controls()


@pytest.mark.parametrize(
    ("field", "value"), [("isolated", 0), ("optimize", 1), ("dont_write_bytecode", 0)]
)
def test_interpreter_flags_are_required(observations, field, value):
    setattr(kernel.sys.flags, field, value)
    with pytest.raises(ValueError):
        kernel.require_guest_controls()


@pytest.mark.skipif(os.name != "posix", reason="Input mount checks require POSIX descriptors")
@pytest.mark.parametrize(
    "change",
    ["none", "extra", "absent", "symlink", "hardlink", "fifo", "empty", "oversize", "writable"],
)
def test_fixed_input_files(tmp_path, monkeypatch, change):
    parent = tmp_path / "input"
    parent.mkdir()
    source = parent / "availability.py"
    source.write_bytes(b"a" * 4096)
    test = parent / "test_owner_archived_read.py"
    test.write_bytes(b"b")
    if change == "extra":
        (parent / "other").touch()
    elif change == "absent":
        test.unlink()
    elif change == "symlink":
        test.unlink()
        test.symlink_to(source)
    elif change == "hardlink":
        os.link(test, tmp_path / "other")
    elif change == "fifo":
        test.unlink()
        os.mkfifo(test)
    elif change in {"empty", "oversize"}:
        source.write_bytes(b"" if change == "empty" else b"a" * 4097)

    def open_input(path, flags, **kwargs):
        return os.open(parent if path == "/input" else path, flags, **kwargs)

    monkeypatch.setattr(
        kernel,
        "os",
        SimpleNamespace(
            open=open_input,
            close=os.close,
            fstat=os.fstat,
            scandir=os.scandir,
            O_RDONLY=os.O_RDONLY,
            O_DIRECTORY=os.O_DIRECTORY,
            O_NOFOLLOW=os.O_NOFOLLOW,
            O_NONBLOCK=os.O_NONBLOCK,
            ST_RDONLY=1,
            fstatvfs=lambda fd: SimpleNamespace(f_flag=0 if change == "writable" else 1),
        ),
    )
    if change == "none":
        kernel._check_inputs()
    else:
        with pytest.raises((OSError, ValueError)):
            kernel._check_inputs()
