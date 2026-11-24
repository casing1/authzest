"""HTTP-only guest code checked with owned fake kernel/tools/streams only."""

from __future__ import annotations

import ast
import builtins
import importlib
import io
import os
import socket
import stat
import subprocess
import sys
from hashlib import sha256
from types import SimpleNamespace

import pytest
from runtime.repository_http import _guest_common as common
from runtime.repository_http import app_launcher, relay_launcher

from authzest.codex.contracts import canonical, identity
from authzest.runner import _repository_http_manifest as manifests
from test_generated_repair_kernel_controls import facts as old_facts

SOURCE = b"raise RuntimeError('never imported on host')\n"


def manifest():
    interface = {
        "schema_version": "1.0",
        "entry_source": "main.py",
        "import_root": ".",
        "module": "main",
        "app_attribute": "app",
        "lifespan": "off",
        "auth_overrides": "none",
    }
    interface["interface_id"] = "repository-http-interface-" + identity(interface)
    return manifests.build_guest_manifest(
        "repository-http-proposal-request-" + "a" * 64,
        interface,
        {"path": "main.py", "sha256": sha256(SOURCE).hexdigest(), "size_bytes": len(SOURCE)},
    )


def facts(role="A", data=None):
    observation = old_facts(role)
    paths = () if role == "B" else manifests.expected_input_paths(data)
    mounts = [
        line
        for line in observation["mountinfo"].splitlines()
        if not line.split()[4].startswith("/input/")
    ]
    for i, path in enumerate(paths, 4):
        mounts.append(f"{i} 1 0:4 /captured {path} ro - ext4 /dev/test rw")
    observation["mountinfo"] = "\n".join(mounts) + "\n"
    observation["input_readonly"] = [True] * len(paths)
    return observation


@pytest.fixture(autouse=True)
def fake_only(monkeypatch):
    original_import, original_compile = builtins.__import__, builtins.compile

    def forbidden(*args, **kwargs):
        pytest.fail("Guest tests permit only owned fake collaborators")

    def guarded_import(name, *args, **kwargs):
        if name.split(".")[0] in {"main", "docker", "fastapi", "uvicorn", "httpx", "openai"}:
            forbidden()
        return original_import(name, *args, **kwargs)

    def ast_only(source, filename, mode, flags=0, *args, **kwargs):
        if not flags & ast.PyCF_ONLY_AST:
            forbidden()
        return original_compile(source, filename, mode, flags, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    monkeypatch.setattr(builtins, "compile", ast_only)
    for owner, names in (
        (builtins, ("open", "eval", "exec")),
        (io, ("open",)),
        (os, ("open", "system", "fork", "execv", "execve", "posix_spawn")),
        (socket, ("socket", "create_connection")),
        (subprocess, ("Popen", "run", "call", "check_output")),
    ):
        for name in names:
            if hasattr(owner, name):
                monkeypatch.setattr(owner, name, forbidden)
    for name, value in (("O_NOFOLLOW", 131072), ("O_NONBLOCK", 2048), ("O_CLOEXEC", 524288)):
        if not hasattr(os, name):
            monkeypatch.setattr(os, name, value, raising=False)
    monkeypatch.setattr(common, "_manifest_api", lambda: manifests)


@pytest.mark.parametrize("role", ["A", "B"])
def test_exact_A_B_kernel_and_entry_contract_and_environment(role):
    data = manifest() if role == "A" else None
    common.check_kernel_controls(role, facts(role, data), data)
    path = common.GUEST_ROOT + "/" + common._SCRIPTS[role]
    args = [path] if role == "A" else [path, "40000"]
    entry = dict(
        script_path=path,
        argv=args,
        platform="linux",
        isolated=1,
        dont_write_bytecode=1,
        uid=65532,
        gid=65532,
    )
    assert common.entry_allowed(role, **entry)
    for key, value in (
        ("uid", 0),
        ("platform", "darwin"),
        ("isolated", 0),
        ("argv", args + ["extra"]),
    ):
        assert not common.entry_allowed(role, **{**entry, key: value})
    assert not common.entry_allowed("T", **entry)
    env = {"PYTHONPATH": "/input", "HTTP_PROXY": "bad", "AUTH_TOKEN": "untrusted"}
    paths = ["", ".", "/input", "/input/project", "/trusted", "/usr/lib/python"]
    common.prepare_environment(env, paths)
    assert env == {} and paths == ["/trusted", "/usr/lib/python"]


@pytest.mark.parametrize(
    "change",
    [
        "extra-mount",
        "directory-mount",
        "writable",
        "no-seccomp",
        "no-nnp",
        "root-rw",
        "host-pid",
        "wrong-memory",
        "bad-network",
        "tmp-exec",
        "old-role",
    ],
)
def test_kernel_refuses_weaker_or_wider_observations(change):
    data = manifest()
    observation = facts("A", data)
    if change == "extra-mount":
        observation["mountinfo"] += "40 1 0:4 /extra /input/policy.txt ro - ext4 /dev/test rw\n"
    elif change == "directory-mount":
        observation["mountinfo"] = observation["mountinfo"].replace(
            "/input/project/main.py", "/input/project"
        )
    elif change == "writable":
        observation["input_readonly"][0] = False
    elif change == "no-seccomp":
        observation["status"] = observation["status"].replace("Seccomp:\t2", "Seccomp:\t0")
    elif change == "no-nnp":
        observation["status"] = observation["status"].replace("NoNewPrivs:\t1", "NoNewPrivs:\t0")
    elif change == "root-rw":
        observation["mountinfo"] = observation["mountinfo"].replace("/ / ro,", "/ / rw,")
    elif change == "host-pid":
        observation["pid"] = 44
    elif change == "wrong-memory":
        observation["memory"] = "max\n"
    elif change == "bad-network":
        observation["network"] += "eth0: 0 0 0\n"
    elif change == "tmp-exec":
        observation["mountinfo"] = observation["mountinfo"].replace("noexec", "exec")
    with pytest.raises(ValueError):
        common.check_kernel_controls("T" if change == "old-role" else "A", observation, data)
    with pytest.raises(ValueError):
        common.check_kernel_controls("B", facts("B"), data)


def test_source_verification_reads_only_the_one_hash_bound_file(monkeypatch):
    data = manifest()
    reads = []

    def read(path, limit):
        reads.append((path, limit))
        return SOURCE

    monkeypatch.setattr(common, "_read_input", read)
    assert common.verify_input_files(data, "A") == data
    assert reads == [("/input/project/main.py", 16384)]
    monkeypatch.setattr(common, "_read_input", lambda *_: SOURCE + b"edited")
    with pytest.raises(ValueError):
        common.verify_input_files(data, "A")
    with pytest.raises(ValueError):
        common.verify_input_files(data, "B")


def test_manifest_loader_uses_exact_fake_regular_file_and_closes_descriptor(monkeypatch):
    data = manifest()
    raw = canonical(data).encode()
    calls = []
    chunks = [raw, b""]
    monkeypatch.setattr(os, "open", lambda path, flags: calls.append((path, flags)) or 42)
    monkeypatch.setattr(
        os, "fstat", lambda _: SimpleNamespace(st_mode=stat.S_IFREG, st_size=len(raw))
    )
    monkeypatch.setattr(os, "read", lambda *_: chunks.pop(0))
    monkeypatch.setattr(os, "close", lambda fd: calls.append(("close", fd)))
    assert common.load_manifest("A") == data
    assert calls[0][0] == "/input/manifest.json" and calls[-1] == ("close", 42)
    with pytest.raises(ValueError):
        common.load_manifest("B")
    chunks[:] = [b"long"]
    monkeypatch.setattr(os, "fstat", lambda _: SimpleNamespace(st_mode=stat.S_IFREG, st_size=2))
    with pytest.raises(ValueError):
        common._read_input("/input/manifest.json", 2)
    assert calls[-1] == ("close", 42)


def test_import_is_explicit_flat_source_and_attribute_without_factory():
    data = manifest()
    calls = []
    app = object()
    paths = ["/trusted"]

    def load(name):
        calls.append(name)
        return SimpleNamespace(__file__="/input/project/main.py", app=app)

    assert (
        common.import_application(
            data, "A", import_module=load, modules={}, search_path=paths, stdlib_names=frozenset()
        )
        is app
    )
    assert calls == ["main"] and paths == ["/input/project", "/trusted"]
    for loaded, stdlib in (({"main": object()}, frozenset()), ({}, frozenset({"main"}))):
        with pytest.raises(ValueError):
            common.import_application(
                data,
                "A",
                import_module=load,
                modules=loaded,
                search_path=["/trusted"],
                stdlib_names=stdlib,
            )
    with pytest.raises(ValueError):
        common.import_application(
            data,
            "B",
            import_module=load,
            modules={},
            search_path=["/trusted"],
            stdlib_names=frozenset(),
        )
    with pytest.raises(ValueError):
        common.import_application(
            data,
            "A",
            import_module=lambda _: SimpleNamespace(__file__="/other/main.py", app=app),
            modules={},
            search_path=["/trusted"],
            stdlib_names=frozenset(),
        )


def test_kernel_reader_uses_only_fixed_fake_kernel_and_manifest_paths(monkeypatch):
    data = manifest()
    observation = facts("A", data)
    inputs = {
        "/proc/self/status": observation["status"],
        "/proc/self/cgroup": observation["cgroup"],
        "/sys/fs/cgroup/memory.max": observation["memory"],
        "/sys/fs/cgroup/memory.swap.max": observation["swap"],
        "/sys/fs/cgroup/pids.max": observation["pids"],
        "/sys/fs/cgroup/cpu.max": observation["cpu"],
        "/proc/self/mountinfo": observation["mountinfo"],
        "/proc/net/dev": observation["network"],
    }
    fds = {}
    opened = []
    closed = []
    observed = []

    def open_file(path, flags):
        assert path in inputs and flags == 3
        fd = len(opened) + 10
        opened.append(path)
        fds[fd] = inputs[path].encode()
        return fd

    def read(fd, limit):
        value, fds[fd] = fds[fd][:limit], fds[fd][limit:]
        return value

    fake_os = SimpleNamespace(
        O_RDONLY=0,
        O_NOFOLLOW=1,
        O_NONBLOCK=2,
        ST_RDONLY=1,
        open=open_file,
        read=read,
        close=closed.append,
        getpid=lambda: 1,
        getuid=lambda: 65532,
        getgid=lambda: 65532,
        statvfs=lambda path: observed.append(path) or SimpleNamespace(f_flag=1),
        stat=lambda *_args, **_kwargs: SimpleNamespace(
            st_mode=stat.S_IFDIR | 0o700, st_uid=65532, st_gid=65532
        ),
    )
    imports = builtins.__import__
    monkeypatch.setattr(
        builtins,
        "__import__",
        lambda name, *a, **k: fake_os if name == "os" else imports(name, *a, **k),
    )
    assert common.require_kernel_controls("A", data) is None
    assert set(opened) == set(inputs) and sorted(closed) == sorted(fds)
    assert observed == list(manifests.expected_input_paths(data))


def test_app_wrapper_prevents_factory_probe_and_uses_fixed_server_settings():
    events = []

    async def owned_app(scope, receive, send):
        events.append((scope, receive, send))

    def config(app, **settings):
        with pytest.raises(TypeError):
            app()
        assert events == []
        coroutine = app("scope", "receive", "send")
        with pytest.raises(StopIteration):
            coroutine.send(None)
        assert (
            settings == app_launcher.SERVER_SETTINGS
            and settings["lifespan"] == "off"
            and settings["factory"] is False
        )
        return object()

    class Server:
        started = True
        should_exit = False

        def __init__(self, config):
            pass

        async def startup(self, sockets=None):
            events.append("startup")

        def run(self):
            coroutine = self.startup()
            with pytest.raises(StopIteration):
                coroutine.send(None)

    app_launcher.run_ready_app(
        owned_app,
        config,
        Server,
        write=lambda value: events.append(value) or len(value),
        flush=lambda: events.append("flush"),
    )
    assert events == [("scope", "receive", "send"), "startup", app_launcher.READY_MARKER, "flush"]


@pytest.mark.parametrize(
    "failure", [None, "kernel", "bytes"], ids=["guarded", "kernel-refusal", "byte-refusal"]
)
def test_A_entry_verifies_kernel_and_bytes_before_tools_or_target(monkeypatch, failure):
    events = []
    data = manifest()
    monkeypatch.setattr(app_launcher, "__file__", app_launcher.SCRIPT_PATH)
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(sys, "flags", SimpleNamespace(isolated=1, dont_write_bytecode=1))
    monkeypatch.setattr(sys, "dont_write_bytecode", True)
    monkeypatch.setattr(sys, "argv", [app_launcher.SCRIPT_PATH])
    monkeypatch.setattr(sys, "path", ["/trusted"])
    monkeypatch.setattr(os, "environ", {})
    monkeypatch.setattr(os, "getuid", lambda: 65532, raising=False)
    monkeypatch.setattr(os, "getgid", lambda: 65532, raising=False)

    def checkpoint(name):
        events.append(name)
        if failure == name:
            raise ValueError("unsupported")

    def import_app(*args, **kwargs):
        assert all("tool:" + name in events for name in app_launcher.TRUSTED_PRELOAD)
        events.append("app")
        return object()

    fake_common = SimpleNamespace(
        entry_allowed=common.entry_allowed,
        prepare_environment=common.prepare_environment,
        load_manifest=lambda _: events.append("manifest") or data,
        require_kernel_controls=lambda *_: checkpoint("kernel"),
        verify_input_files=lambda *_: checkpoint("bytes"),
        import_application=import_app,
    )
    monkeypatch.setitem(sys.modules, "_guest_common", fake_common)

    def import_tool(name):
        assert events[:3] == ["manifest", "kernel", "bytes"] and "app" not in events
        events.append("tool:" + name)
        return SimpleNamespace(Config=object, Server=object)

    monkeypatch.setattr(importlib, "import_module", import_tool)
    monkeypatch.setattr(app_launcher, "run_ready_app", lambda *a, **k: events.append("serve"))
    assert app_launcher._script_main() == (78 if failure else 0)
    assert ("app" in events) is (failure is None)
    if failure:
        assert not any(event.startswith("tool:") for event in events)


def test_B_schedule_is_bounded_and_uses_the_original_deadline_and_new_codec():
    raw = b'{"owned":"schedule"}'
    calls = []
    codec = SimpleNamespace(
        validate_http_observer_schedule=lambda value: calls.append(value) or {"checked": True}
    )
    assert relay_launcher.read_schedule(
        lambda limit: raw if limit == 16385 else None,
        codec=codec,
        phase_deadline=2.0,
        clock=lambda: 1.0,
    ) == {"checked": True}
    assert calls == [raw.decode()]
    with pytest.raises(TimeoutError):
        relay_launcher.read_schedule(
            lambda _: pytest.fail("Expired before stdin"),
            codec=codec,
            phase_deadline=2.0,
            clock=lambda: 2.0,
        )
    with pytest.raises(ValueError):
        relay_launcher.read_schedule(
            lambda _: b"x" * 16385, codec=codec, phase_deadline=2.0, clock=lambda: 1.0
        )
    ticks = iter([1.0, 2.0])
    with pytest.raises(TimeoutError):
        relay_launcher.read_schedule(
            lambda _: raw, codec=codec, phase_deadline=2.0, clock=lambda: next(ticks)
        )


@pytest.mark.parametrize("kind", ["complete", "partial"])
def test_B_emits_only_bounded_new_capture_data(kind):
    raw = canonical(
        {"schema_version": "2.0", "kind": "repository-http-raw-capture", "status": kind}
    )
    writes = []
    assert relay_launcher.emit_capture(
        SimpleNamespace(payload_json=raw), lambda value: writes.append(value) or len(value)
    ) == (0 if kind == "complete" else 1)
    assert writes == [raw.encode()]
    with pytest.raises(ValueError):
        relay_launcher.emit_capture(SimpleNamespace(payload_json=raw), lambda _: 0)
    old = raw.replace("repository-http-raw-capture", "repository-http-capture")
    with pytest.raises(ValueError):
        relay_launcher.emit_capture(
            SimpleNamespace(payload_json=old), lambda _: pytest.fail("Old kind emitted")
        )


def test_host_entry_refuses_without_reading_target_or_opening_socket():
    assert app_launcher._script_main() == 64
    assert relay_launcher._script_main() == 64


@pytest.mark.parametrize("role", ["A", "B"])
@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("pid", True),
        ("uid", 0),
        ("gid", 0),
        ("tmp_mode", 0o777),
        ("tmp_uid", 0),
        ("tmp_gid", 0),
        ("cgroup", "0::/host\n"),
        ("memory", "1073741824\n"),
        ("swap", "1024\n"),
        ("pids", "max\n"),
        ("cpu", "max 100000\n"),
        ("cpu", "200000 100000\n"),
        ("input_readonly", [1, True]),
        ("status", "Name:\tpython\x7f\n"),
        ("mountinfo", ""),
        ("network", "header\nheader\nlo: 0\neth0: 0\n"),
    ],
    ids=[
        "bool-pid",
        "root-uid",
        "root-gid",
        "tmp-mode",
        "tmp-uid",
        "tmp-gid",
        "host-cgroup",
        "memory",
        "swap",
        "pids",
        "cpu-max",
        "cpu-quota",
        "bool-readonly",
        "control-status",
        "missing-mounts",
        "external-network",
    ],
)
def test_both_roles_require_effective_resource_and_namespace_properties(role, key, value):
    data = manifest() if role == "A" else None
    observation = facts(role, data)
    observation[key] = value
    with pytest.raises(ValueError):
        common.check_kernel_controls(role, observation, data)


@pytest.mark.parametrize(
    "failure", [None, "kernel", "schedule"], ids=["guarded", "kernel-refusal", "schedule-refusal"]
)
def test_B_entry_guards_before_stdin_then_uses_only_new_request_codec(monkeypatch, failure):
    events = []
    stdin = io.BytesIO(b'{"request_only":true}')
    stdout = io.BytesIO()
    monkeypatch.setattr(relay_launcher, "__file__", relay_launcher.SCRIPT_PATH)
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(sys, "flags", SimpleNamespace(isolated=1, dont_write_bytecode=1))
    monkeypatch.setattr(sys, "dont_write_bytecode", True)
    monkeypatch.setattr(sys, "argv", [relay_launcher.SCRIPT_PATH, "40000"])
    monkeypatch.setattr(sys, "path", ["/trusted"])
    monkeypatch.setattr(sys, "stdin", SimpleNamespace(buffer=stdin))
    monkeypatch.setattr(sys, "stdout", SimpleNamespace(buffer=stdout))
    monkeypatch.setattr(os, "environ", {})
    monkeypatch.setattr(os, "getuid", lambda: 65532, raising=False)
    monkeypatch.setattr(os, "getgid", lambda: 65532, raising=False)

    def kernel(role):
        assert role == "B" and stdin.tell() == 0
        events.append("kernel")
        if failure == "kernel":
            raise ValueError("unsupported")

    fake_common = SimpleNamespace(
        entry_allowed=common.entry_allowed,
        prepare_environment=common.prepare_environment,
        require_kernel_controls=kernel,
    )

    def validate(raw):
        assert events == ["kernel"] and raw == '{"request_only":true}'
        events.append("schedule")
        if failure == "schedule":
            raise ValueError("invalid")
        return {"owned": "schedule"}

    codec = SimpleNamespace(validate_http_observer_schedule=validate)
    monkeypatch.setitem(sys.modules, "_guest_common", fake_common)
    monkeypatch.setitem(sys.modules, "repository_http_transport", codec)

    def capture(schedule, **kwargs):
        assert events == ["kernel", "schedule"] and schedule == {"owned": "schedule"}
        assert kwargs["codec"] is codec
        events.append("capture")
        return SimpleNamespace(
            payload_json=canonical(
                {
                    "schema_version": "2.0",
                    "kind": "repository-http-raw-capture",
                    "status": "complete",
                }
            )
        )

    monkeypatch.setattr(relay_launcher, "capture_relay", capture)
    assert relay_launcher._script_main() == ({None: 0, "kernel": 78, "schedule": 65}[failure])
    if failure:
        assert stdout.getvalue() == b"" and "capture" not in events
    else:
        assert events == ["kernel", "schedule", "capture"]
        assert b"repository-http-raw-capture" in stdout.getvalue()
