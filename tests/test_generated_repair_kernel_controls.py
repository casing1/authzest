"""Supplied kernel facts and fixed fake file readers; no guest or target run."""

from __future__ import annotations

import builtins
import os
import stat
from types import SimpleNamespace

import pytest
from runtime.generated_repair import _guest_common as common


def facts(role="T"):
    small = role == "B"
    status = {
        "Name": "python",
        "Pid": "1",
        "PPid": "0",
        "NSpid": "1",
        "Uid": "65532\t65532\t65532\t65532",
        "Gid": "65532\t65532\t65532\t65532",
        "NoNewPrivs": "1",
        "Seccomp": "2",
        "Seccomp_filters": "1",
        **dict.fromkeys(("CapInh", "CapPrm", "CapEff", "CapBnd", "CapAmb"), "0000000000000000"),
    }
    mounts = [
        "1 0 0:1 / / ro,relatime - overlay overlay rw,lowerdir=/trusted",
        "2 1 0:2 / /tmp rw,nosuid,nodev,noexec - tmpfs tmpfs rw,size="
        + ("8192k" if small else "32768k")
        + ",mode=700,uid=65532,gid=65532,inode64",
        "3 1 0:3 / /dev/shm rw,nosuid,nodev,noexec - tmpfs shm rw,size=8192k",
    ]
    inputs = [] if small else ["/input/app.py"]
    if role == "T":
        inputs.append("/input/tests/test_generated_ownership.py")
    for index, path in enumerate(inputs, 4):
        mounts.append(f"{index} 1 0:4 /captured {path} ro,relatime - ext4 /dev/test rw")
    return {
        "pid": 1,
        "uid": 65532,
        "gid": 65532,
        "status": "".join(key + ":\t" + value + "\n" for key, value in status.items()),
        "cgroup": "0::/\n",
        "memory": "134217728\n" if small else "536870912\n",
        "swap": "0\n",
        "pids": "32\n" if small else "64\n",
        "cpu": "50000 100000\n" if small else "100000 100000\n",
        "mountinfo": "\n".join(mounts) + "\n",
        "network": "Inter-| Receive | Transmit\n face |bytes packets\n lo: 0 0 0 0\n",
        "tmp_mode": 0o700,
        "tmp_uid": 65532,
        "tmp_gid": 65532,
        "input_readonly": [True] * len(inputs),
    }


@pytest.mark.parametrize("role", ["T", "A", "B"])
def test_expected_per_role_facts_pass_without_io(role, monkeypatch):
    monkeypatch.setattr(os, "open", lambda *_: pytest.fail("Pure comparison must not open files"))
    assert common.check_kernel_controls(role, facts(role)) is None


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("pid", 2),
        ("pid", True),
        ("uid", 0),
        ("gid", 0),
        ("tmp_uid", 0),
        ("tmp_gid", 0),
        ("tmp_mode", 0o777),
        ("cgroup", "0::/host\n"),
        ("memory", "max\n"),
        ("memory", "1073741824\n"),
        ("swap", "1024\n"),
        ("pids", "max\n"),
        ("cpu", "max 100000\n"),
        ("cpu", "200000 100000\n"),
        ("cpu", "0 0"),
        ("cpu", "1 1 1"),
        ("cpu", "1 1"),
        ("network", "header\nheader\nlo: 0\neth0: 0\n"),
        ("input_readonly", [True, False]),
        ("input_readonly", [1, True]),
        ("input_readonly", [True]),
        ("status", "x" * 65537),
        ("status", "한글"),
        ("status", "Name:\tpython\x7f\n"),
        ("mountinfo", "invalid"),
        ("mountinfo", ""),
        ("status", "Uid: 65532\r\n"),
    ],
)
def test_wrong_or_missing_properties_are_unsupported(key, value):
    data = facts()
    data[key] = value
    with pytest.raises(ValueError, match="guest-kernel-controls"):
        common.check_kernel_controls("T", data)


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("NoNewPrivs:\t1", "NoNewPrivs:\t0"),
        ("Seccomp:\t2", "Seccomp:\t0"),
        ("Seccomp_filters:\t1", "Seccomp_filters:\t0"),
        ("CapEff:\t0000000000000000", "CapEff:\t0000000000000001"),
        ("CapBnd:\t0000000000000000", "CapBnd:\t0000000000000001"),
        ("PPid:\t0", "PPid:\t2"),
        ("NSpid:\t1", "NSpid:\t42 1"),
        ("Uid:\t65532\t65532\t65532\t65532", "Uid:\t65532\t65532\t0\t65532"),
        ("Pid:\t1", "Pid:\t1\nPid:\t1"),
    ],
)
def test_process_security_properties_are_mandatory(old, new):
    data = facts()
    data["status"] = data["status"].replace(old, new)
    with pytest.raises(ValueError):
        common.check_kernel_controls("T", data)


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("/ / ro,relatime", "/ / rw,relatime"),
        ("nosuid,", ""),
        ("nodev,", ""),
        ("noexec", "exec"),
        ("size=32768k", "size=65536k"),
        ("mode=700", "mode=777"),
        ("uid=65532", "uid=0"),
        ("gid=65532", "gid=0"),
        ("size=8192k", "size=16384k"),
        ("/input/app.py ro", "/input/app.py rw"),
        ("rw,size=32768k", "rw,size=32768k,size=32768k"),
    ],
)
def test_effective_mount_properties_must_match(old, new):
    data = facts()
    data["mountinfo"] = data["mountinfo"].replace(old, new)
    with pytest.raises(ValueError):
        common.check_kernel_controls("T", data)


def test_duplicate_or_extra_input_mount_and_boolean_shapes_refuse():
    for extra in (
        "4 1 0:4 /captured /input/app.py ro - ext4 /dev/test rw\n",
        "9 1 0:4 /captured /input/secret ro - ext4 /dev/test rw\n",
    ):
        data = facts()
        data["mountinfo"] += extra
        with pytest.raises(ValueError):
            common.check_kernel_controls("T", data)
    for role in (None, True, "C"):
        with pytest.raises(ValueError):
            common.check_kernel_controls(role, facts())


@pytest.mark.parametrize("role", ["T", "A", "B"])
def test_actual_reader_uses_only_fixed_paths_and_closes_every_fake_descriptor(monkeypatch, role):
    data = facts(role)
    paths = {
        "/proc/self/status": data["status"],
        "/proc/self/cgroup": data["cgroup"],
        "/sys/fs/cgroup/memory.max": data["memory"],
        "/sys/fs/cgroup/memory.swap.max": data["swap"],
        "/sys/fs/cgroup/pids.max": data["pids"],
        "/sys/fs/cgroup/cpu.max": data["cpu"],
        "/proc/self/mountinfo": data["mountinfo"],
        "/proc/net/dev": data["network"],
    }
    fds, opened, closed = {}, [], []
    original_import = builtins.__import__

    def native_open(path, flags):
        assert path in paths and flags == os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
        number = len(opened) + 10
        opened.append(path)
        fds[number] = paths[path].encode()
        return number

    def native_read(fd, count):
        value, fds[fd] = fds[fd][:count], fds[fd][count:]
        return value

    fake = SimpleNamespace(
        O_RDONLY=os.O_RDONLY,
        O_NOFOLLOW=os.O_NOFOLLOW,
        O_NONBLOCK=os.O_NONBLOCK,
        ST_RDONLY=1,
        open=native_open,
        read=native_read,
        close=lambda fd: closed.append(fd),
        getpid=lambda: 1,
        getuid=lambda: 65532,
        getgid=lambda: 65532,
        stat=lambda path, **kwargs: SimpleNamespace(
            st_mode=stat.S_IFDIR | 0o700, st_uid=65532, st_gid=65532
        ),
        statvfs=lambda path: SimpleNamespace(f_flag=1),
    )

    def imports(name, *args, **kwargs):
        return fake if name == "os" else original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", imports)
    assert common.require_kernel_controls(role) is None
    assert set(opened) == set(paths) and sorted(closed) == sorted(fds)


def test_reader_size_error_closes_descriptor_before_refusal(monkeypatch):
    closed = []
    original_import = builtins.__import__
    fake = SimpleNamespace(
        O_RDONLY=0,
        O_NOFOLLOW=1,
        O_NONBLOCK=2,
        ST_RDONLY=1,
        stat=lambda *_args, **_kwargs: SimpleNamespace(
            st_mode=stat.S_IFDIR | 0o700, st_uid=65532, st_gid=65532
        ),
        open=lambda *_: 42,
        read=lambda _fd, count: b"x" * count,
        close=closed.append,
        getpid=lambda: 1,
        getuid=lambda: 65532,
        getgid=lambda: 65532,
    )
    monkeypatch.setattr(
        builtins,
        "__import__",
        lambda name, *a, **k: fake if name == "os" else original_import(name, *a, **k),
    )
    with pytest.raises(ValueError, match="guest-kernel-controls"):
        common.require_kernel_controls("T")
    assert closed == [42]


@pytest.mark.parametrize(
    ("original", "closing", "expected"),
    [
        (OSError, OSError, OSError),
        (KeyboardInterrupt, OSError, KeyboardInterrupt),
        (KeyboardInterrupt, SystemExit, KeyboardInterrupt),
        (OSError, KeyboardInterrupt, KeyboardInterrupt),
    ],
)
def test_reader_preserves_first_cancellation_and_marks_cleanup_uncertainty(
    monkeypatch, original, closing, expected
):
    first, later = original("first"), closing("later")
    imports = builtins.__import__
    closed = []

    def fail_read(*_):
        raise first

    def fail_close(fd):
        closed.append(fd)
        raise later

    native = SimpleNamespace(
        O_RDONLY=0,
        O_NOFOLLOW=1,
        O_NONBLOCK=2,
        ST_RDONLY=1,
        stat=lambda *_a, **_k: SimpleNamespace(
            st_mode=stat.S_IFDIR | 0o700, st_uid=65532, st_gid=65532
        ),
        open=lambda *_: 42,
        read=fail_read,
        close=fail_close,
        getpid=lambda: 1,
        getuid=lambda: 65532,
        getgid=lambda: 65532,
    )
    monkeypatch.setattr(
        builtins,
        "__import__",
        lambda name, *a, **k: native if name == "os" else imports(name, *a, **k),
    )
    with pytest.raises(expected) as captured:
        common.require_kernel_controls("T")
    assert closed == [42]
    if isinstance(first, expected):
        assert captured.value is first
        assert first.guest_kernel_descriptor_cleanup_unconfirmed is True
    else:
        assert captured.value is later
