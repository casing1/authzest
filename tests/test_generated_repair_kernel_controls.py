"""Supplied kernel facts and fixed fake file readers; no guest or target run."""

from __future__ import annotations

import builtins
import copy
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


# Recorded kernel fallback forms. This is deliberately independent of the
# implementation's table; counters are not evidence that a device is down.
_FALLBACK_FORMS = {
    "tunl0": (768, 0x80),
    "gre0": (778, 0x80),
    "gretap0": (1, 0x1002),
    "erspan0": (1, 0x1002),
    "ip_vti0": (768, 0x80),
    "ip6_vti0": (769, 0x80),
    "sit0": (776, 0x80),
    "ip6tnl0": (769, 0x80),
    "ip6gre0": (823, 0x80),
}


def fallback_facts(role="T", names=None):
    names = list(_FALLBACK_FORMS) if names is None else list(names)
    data = facts(role)
    data["network"] = (
        "\n".join(
            [*data["network"].splitlines()[:2], " lo: 400 4 0 0"]
            + [f" {name}: 500 5 0 0" for name in names]
        )
        + "\n"
    )
    snapshot = {
        "lo": {"flags": 0x9, "operstate": "unknown", "type": 772, "ifindex": 1, "iflink": 1}
    }
    for index, name in enumerate(names, 2):
        kind, flags = _FALLBACK_FORMS[name]
        snapshot[name] = {
            "flags": flags,
            "operstate": "down",
            "type": kind,
            "ifindex": index,
            "iflink": 0,
        }
    data["network_interfaces"] = {
        "before": copy.deepcopy(snapshot),
        "after": copy.deepcopy(snapshot),
        "names_after": list(snapshot),
    }
    return data


@pytest.mark.parametrize("role", ["T", "A", "B"])
@pytest.mark.parametrize("names", [*_FALLBACK_FORMS, "all"])
def test_closed_down_fallbacks_require_stable_native_facts_not_zero_counters(role, names):
    selected = None if names == "all" else [names]
    assert common.check_kernel_controls(role, fallback_facts(role, selected)) is None


def test_optional_loopback_snapshot_validates_its_own_index_not_literal_one():
    data = fallback_facts(names=[])
    for snapshot in ("before", "after"):
        data["network_interfaces"][snapshot]["lo"].update(ifindex=47, iflink=47)
    assert common.check_kernel_controls("T", data) is None


@pytest.mark.parametrize("detail", [None, {}, [], {"before": {}, "after": {}, "names_after": []}])
@pytest.mark.parametrize("with_fallback", [False, True])
def test_explicit_missing_or_malformed_detail_never_uses_the_loopback_fast_path(
    detail, with_fallback
):
    data = fallback_facts(names=["gre0"] if with_fallback else [])
    data["network_interfaces"] = detail
    with pytest.raises(ValueError, match="guest-kernel-controls"):
        common.check_kernel_controls("T", data)


def test_fallback_names_without_current_metadata_cannot_be_accepted():
    data = fallback_facts()
    del data["network_interfaces"]
    with pytest.raises(ValueError):
        common.check_kernel_controls("T", data)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("flags", 0x81),
        ("flags", 0xC0),
        ("flags", 0x10080),
        ("flags", 0),
        ("flags", True),
        ("flags", "0x80"),
        ("type", 1),
        ("type", True),
        ("operstate", "up"),
        ("operstate", "unknown"),
        ("operstate", "lowerlayerdown"),
        ("operstate", "down\n"),
        ("operstate", None),
        ("iflink", 2),
        ("iflink", False),
        ("ifindex", 0),
        ("ifindex", -1),
        ("ifindex", 2**31),
        ("ifindex", True),
    ],
)
def test_fallback_scalar_properties_are_exact_in_both_snapshots(field, value):
    data = fallback_facts(names=["tunl0"])
    for snapshot in ("before", "after"):
        data["network_interfaces"][snapshot]["tunl0"][field] = value
    with pytest.raises(ValueError):
        common.check_kernel_controls("T", data)


@pytest.mark.parametrize(
    ("field", "value"),
    [("flags", 0x8), ("flags", 0x49), ("operstate", "down"), ("type", 1), ("iflink", 0)],
)
def test_loopback_properties_are_exact_when_the_fallback_branch_is_used(field, value):
    data = fallback_facts()
    for snapshot in ("before", "after"):
        data["network_interfaces"][snapshot]["lo"][field] = value
    with pytest.raises(ValueError):
        common.check_kernel_controls("T", data)


@pytest.mark.parametrize("change", ["index", "boolean-index", "missing", "extra", "extra-field"])
def test_changed_snapshots_and_ambiguous_indexes_refuse(change):
    data = fallback_facts()
    after = data["network_interfaces"]["after"]
    if change == "index":
        after["tunl0"]["ifindex"] = 99
    elif change == "boolean-index":
        after["lo"]["ifindex"] = True
    elif change == "missing":
        del after["tunl0"]
    elif change == "extra":
        after["eth0"] = copy.deepcopy(after["lo"])
    else:
        after["lo"]["other"] = "ignored?"
    with pytest.raises(ValueError):
        common.check_kernel_controls("T", data)


def test_duplicate_indexes_refuse_even_when_snapshots_equal():
    data = fallback_facts()
    for snapshot in ("before", "after"):
        data["network_interfaces"][snapshot]["tunl0"]["ifindex"] = 1
    with pytest.raises(ValueError):
        common.check_kernel_controls("T", data)


@pytest.mark.parametrize("after", [["lo"], ["lo", "lo"], ["lo", True], ["lo", "eth0"], "lo"])
def test_post_collection_name_set_must_be_the_same_native_unique_set(after):
    data = fallback_facts(names=["gre0"])
    data["network_interfaces"]["names_after"] = after
    with pytest.raises(ValueError):
        common.check_kernel_controls("T", data)


@pytest.mark.parametrize(
    "row",
    [
        " eth0: 0 0\n",
        " lo: 0 0\n",
        " gre0: 0 0\n",
        " ../gre0: 0 0\n",
        " gre0:bad: 0\n",
        " gre0 0 0\n",
        " : 0 0\n",
        " gre0: garbage\n",
    ],
)
def test_unknown_duplicate_and_malformed_proc_rows_refuse(row):
    data = fallback_facts(names=["gre0"])
    data["network"] += row
    with pytest.raises(ValueError):
        common.check_kernel_controls("T", data)


def test_reordered_names_and_changed_counter_values_do_not_masquerade_as_state_changes():
    data = fallback_facts()
    data["network_interfaces"]["names_after"].reverse()
    assert common.check_kernel_controls("T", data) is None


def test_other_kernel_controls_remain_required_with_inert_fallbacks():
    for field, value in (("swap", "1\n"), ("uid", 0), ("input_readonly", [True, False])):
        data = fallback_facts()
        data[field] = value
        with pytest.raises(ValueError):
            common.check_kernel_controls("T", data)
    data = fallback_facts()
    data["status"] = data["status"].replace(
        "CapEff:\t0000000000000000", "CapEff:\t0000000000000001"
    )
    with pytest.raises(ValueError):
        common.check_kernel_controls("T", data)


def fake_fallback_reader(monkeypatch, data, transform=None, close_error=None):
    """Supply fixed kernel bytes only, including two separate scalar snapshots."""
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
    for name, entry in data["network_interfaces"]["before"].items():
        for field, value in entry.items():
            paths[f"/sys/class/net/{name}/{field}"] = (
                hex(value) if field == "flags" else str(value)
            ) + "\n"
    opened, closed, fds, occurrences = [], [], {}, {}
    original_import = builtins.__import__

    def native_open(path, flags):
        assert path in paths and flags == os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
        occurrences[path] = occurrences.get(path, 0) + 1
        number = len(opened) + 10
        opened.append(path)
        value = paths[path].encode()
        fds[number] = (path, value, occurrences[path])
        return number

    def native_read(fd, count):
        path, value, occurrence = fds[fd]
        if transform is not None:
            value = transform(path, occurrence, value)
        chunk, rest = value[:count], value[count:]
        fds[fd] = (path, rest, occurrence)
        return chunk

    def native_close(fd):
        closed.append(fd)
        if close_error is not None:
            close_error(*fds[fd])

    fake = SimpleNamespace(
        O_RDONLY=os.O_RDONLY,
        O_NOFOLLOW=os.O_NOFOLLOW,
        O_NONBLOCK=os.O_NONBLOCK,
        ST_RDONLY=1,
        open=native_open,
        read=native_read,
        close=native_close,
        getpid=lambda: 1,
        getuid=lambda: 65532,
        getgid=lambda: 65532,
        stat=lambda *_args, **_kwargs: SimpleNamespace(
            st_mode=stat.S_IFDIR | 0o700, st_uid=65532, st_gid=65532
        ),
        statvfs=lambda _path: SimpleNamespace(f_flag=1),
    )
    monkeypatch.setattr(
        builtins,
        "__import__",
        lambda name, *args, **kwargs: (
            fake if name == "os" else original_import(name, *args, **kwargs)
        ),
    )
    return paths, opened, closed, fds


@pytest.mark.parametrize("role", ["T", "A", "B"])
def test_fallback_reader_uses_closed_paths_twice_between_proc_name_observations(monkeypatch, role):
    data = fallback_facts(role)
    paths, opened, closed, fds = fake_fallback_reader(monkeypatch, data)
    assert common.require_kernel_controls(role) is None
    base = list(paths)[:8]
    attributes = list(paths)[8:]
    assert opened == base + attributes + attributes + ["/proc/net/dev"]
    assert sorted(closed) == sorted(fds)


@pytest.mark.parametrize("change", ["new-interface", "flags", "late-read", "oversized-attribute"])
def test_fallback_reader_changed_missing_or_oversized_late_facts_refuse_and_close(
    monkeypatch, change
):
    data = fallback_facts()
    last = "/sys/class/net/ip6gre0/iflink"

    def transform(path, occurrence, raw):
        if change == "new-interface" and path == "/proc/net/dev" and occurrence == 2 and raw:
            return raw + b" eth0: 0 0\n"
        if change == "flags" and path == "/sys/class/net/tunl0/flags" and occurrence == 2 and raw:
            return b"0x81\n"
        if change == "late-read" and path == last and occurrence == 2:
            raise OSError("late fixed sysfs read")
        if change == "oversized-attribute" and path == last and occurrence == 2:
            return b"1" * 65
        return raw

    _, opened, closed, fds = fake_fallback_reader(monkeypatch, data, transform)
    with pytest.raises((OSError, ValueError)):
        common.require_kernel_controls("T")
    assert sorted(closed) == sorted(fds)
    assert opened.count(last) == 2


def test_unknown_interface_refuses_before_any_sysfs_path_is_selected(monkeypatch):
    data = fallback_facts()
    data["network"] += " eth0: 0\n"
    _, opened, closed, fds = fake_fallback_reader(monkeypatch, data)
    with pytest.raises(ValueError):
        common.require_kernel_controls("T")
    assert all(not path.startswith("/sys/class/net/") for path in opened)
    assert sorted(closed) == sorted(fds)


def test_second_snapshot_cancellation_keeps_original_and_marks_close_uncertainty(monkeypatch):
    data = fallback_facts()
    last = "/sys/class/net/ip6gre0/iflink"
    interruption = KeyboardInterrupt("late read")

    def transform(path, occurrence, raw):
        if path == last and occurrence == 2:
            raise interruption
        return raw

    def close_error(path, _raw, occurrence):
        if path == last and occurrence == 2:
            raise OSError("late descriptor close")

    _, _, closed, fds = fake_fallback_reader(monkeypatch, data, transform, close_error)
    with pytest.raises(KeyboardInterrupt) as caught:
        common.require_kernel_controls("T")
    assert caught.value is interruption
    assert interruption.guest_kernel_descriptor_cleanup_unconfirmed is True
    assert sorted(closed) == sorted(fds)
