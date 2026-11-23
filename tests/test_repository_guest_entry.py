"""Guest foundations exercised with data and fake tools, never an app or guest."""

from __future__ import annotations

import ast
import builtins
import copy
import importlib
import io
import os
import socket
import stat
import subprocess
import sys
from enum import IntEnum
from hashlib import sha256
from types import SimpleNamespace

import pytest
from runtime.repository import _guest_common as common
from runtime.repository import app_launcher, test_launcher

from authzest.codex.contracts import canonical, identity
from authzest.codex.repository_test_interface import build_repository_test_request
from authzest.runner import _repository_manifest as manifest_api
from test_generated_repair_kernel_controls import facts as old_facts
from test_repository_test_interface import _base


@pytest.fixture(autouse=True)
def fake_only(monkeypatch):
    original_import, original_compile = builtins.__import__, builtins.compile

    def forbidden(*args, **kwargs):
        raise AssertionError("Guest foundation tests permit fake collaborators only")

    def guarded_import(name, *args, **kwargs):
        if name.split(".")[0] in {"app", "docker", "fastapi", "httpx", "uvicorn", "openai"}:
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
        (subprocess, ("Popen", "run", "call", "check_call", "check_output")),
    ):
        for name in names:
            if hasattr(owner, name):
                monkeypatch.setattr(owner, name, forbidden)
    for name, value in (("O_NOFOLLOW", 131072), ("O_NONBLOCK", 2048), ("O_CLOEXEC", 524288)):
        if not hasattr(os, name):
            monkeypatch.setattr(os, name, value, raising=False)
    monkeypatch.setattr(common, "_manifest_api", lambda: manifest_api)


def descriptor(path, text):
    data = text.encode("utf-8")
    return {"path": path, "sha256": sha256(data).hexdigest(), "size_bytes": len(data)}


def manifest(role="T", *, source="main.py", contexts=(), import_root=".", app="app"):
    request = build_repository_test_request(
        _base(source_path=source, contexts=contexts),
        entry_source=source,
        import_root=import_root,
        app_attribute=app,
    )
    payload = request.to_dict()
    files = [
        descriptor(item["path"], item["text"])
        for item in payload["selection"]["files"]
        if item["path"] != payload["selection"]["policy"]
    ]
    test = descriptor(manifest_api.TEST_PATH, "def test_read(client):\n    assert client\n")
    return manifest_api.build_guest_manifest(
        request.request_id,
        payload["test_interface"],
        files,
        test if role == "T" else None,
        role=role,
    )


def rehash(data):
    body = {key: value for key, value in data.items() if key != "manifest_id"}
    data["manifest_id"] = "repository-guest-input-" + identity(body)
    return data


@pytest.mark.parametrize(
    ("source", "contexts", "root", "module"),
    [
        ("main.py", (), ".", "main"),
        ("pkg/server.py", (("pkg/__init__.py", ""),), ".", "pkg.server"),
        ("src/pkg/__init__.py", (), "src", "pkg"),
        ("src/pkg/server.py", (("src/pkg/__init__.py", ""),), "src", "pkg.server"),
    ],
    ids=["flat", "package", "src-package-entry", "src-module"],
)
def test_manifest_matches_s3_interface_and_canonical_round_trip(source, contexts, root, module):
    data = manifest(source=source, contexts=contexts, import_root=root, app="api")
    assert data["test_interface"]["module"] == module
    assert data["test_interface"]["app_attribute"] == "api"
    assert manifest_api.validate_guest_manifest(canonical(data).encode(), "T") == data
    copied = manifest_api.validate_guest_manifest(data, "T")
    copied["source_files"][0]["path"] = "other.py"
    assert data["source_files"][0]["path"] == source
    assert not any(key in canonical(data) for key in ("policy.md", "expected", "journal"))
    assert manifest_api.expected_input_paths(data, "T") == (
        "/input/manifest.json",
        *("/input/project/" + item["path"] for item in data["source_files"]),
        "/input/tests/test_authzest_regression.py",
    )
    with pytest.raises(ValueError, match="repository-guest-manifest"):
        manifest_api.validate_guest_manifest(data, "A")
    assert manifest("A")["test"] is None


@pytest.mark.parametrize(
    "change",
    [
        "extra",
        "bool-size",
        "too-large",
        "missing-test",
        "request-id",
        "interface-id",
        "module",
        "factory",
        "lifespan",
        "override",
        "duplicate-source",
        "escape",
        "missing-init",
        "module-package-alias",
        "old-id",
    ],
)
def test_manifest_rejects_tamper_even_after_rehash(change):
    data = manifest()
    interface = data["test_interface"]
    if change == "extra":
        data["expected"] = {"allowed": True}
    elif change == "bool-size":
        data["source_files"][0]["size_bytes"] = True
    elif change == "too-large":
        data["source_files"][0]["size_bytes"] = 16_385
    elif change == "missing-test":
        data["test"] = None
    elif change == "request-id":
        data["request_id"] = "repository-proposal-request-" + "a" * 64
    elif change == "interface-id":
        data["interface_id"] = "repository-test-interface-" + "0" * 64
    elif change == "module":
        interface["module"] = "another"
    elif change == "factory":
        interface["app_attribute"] = "create_app()"
    elif change == "lifespan":
        interface["lifespan"] = "on"
    elif change == "override":
        interface["auth_overrides"] = "owner"
    elif change == "duplicate-source":
        data["source_files"].append(copy.deepcopy(data["source_files"][0]))
    elif change == "escape":
        data["source_files"][0]["path"] = "../main.py"
    elif change == "missing-init":
        data["source_files"][0]["path"] = "pkg/main.py"
        interface.update(entry_source="pkg/main.py", module="pkg.main")
    elif change == "module-package-alias":
        data["source_files"].append(descriptor("main/__init__.py", ""))
    elif change == "old-id":
        data["source_files"][0]["sha256"] = "1" * 64
        with pytest.raises(ValueError):
            manifest_api.validate_guest_manifest(data, "T")
        return
    interface["interface_id"] = "repository-test-interface-" + identity(
        {key: value for key, value in interface.items() if key != "interface_id"}
    )
    if change != "interface-id":
        data["interface_id"] = interface["interface_id"]
    with pytest.raises(ValueError, match="repository-guest-manifest"):
        manifest_api.validate_guest_manifest(rehash(data), "T")


@pytest.mark.parametrize("kind", ["duplicate-key", "whitespace", "oversize", "non-json", "bool"])
def test_manifest_json_boundary_is_closed_and_bounded(kind):
    data = manifest()
    raw = canonical(data)
    if kind == "duplicate-key":
        raw = raw[:-1] + ',"schema_version":"1.0"}'
    elif kind == "whitespace":
        raw += "\n"
    elif kind == "oversize":
        raw = "x" * 16_385
    elif kind == "non-json":
        raw = "{"
    else:
        raw = True
    with pytest.raises(ValueError, match="repository-guest-manifest"):
        manifest_api.validate_guest_manifest(raw, "T")


def facts(role="T", data=None):
    observation = old_facts(role)
    paths = () if role == "B" else manifest_api.expected_input_paths(data, role)
    mounts = [
        line
        for line in observation["mountinfo"].splitlines()
        if not line.split()[4].startswith("/input/")
    ]
    for index, path in enumerate(paths, 4):
        mounts.append(f"{index} 1 0:4 /captured {common._mount_path(path)} ro - ext4 /dev/test rw")
    observation["mountinfo"] = "\n".join(mounts) + "\n"
    observation["input_readonly"] = [True] * len(paths)
    return observation


@pytest.mark.parametrize("role", ["T", "A", "B"])
def test_exact_entry_environment_and_kernel_mount_contract(role):
    data = None if role == "B" else manifest(role, contexts=(("notes source.py", ""),))
    common.check_kernel_controls(role, facts(role, data), data)
    path = common.GUEST_ROOT + "/" + common._SCRIPTS[role]
    args = [path, "40000"] if role == "B" else [path]
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
        ("dont_write_bytecode", 0),
        ("argv", args + ["unexpected"]),
    ):
        assert not common.entry_allowed(role, **{**entry, key: value})
    env = {"PYTHONPATH": "/input", "PYTEST_ADDOPTS": "-p evil", "HTTP_PROXY": "bad"}
    path = ["", ".", "/input", "/input/project/src", "/trusted", "/usr/lib/python"]
    common.prepare_environment(env, path)
    assert env == {"PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}
    assert path == ["/trusted", "/usr/lib/python"]


@pytest.mark.parametrize(
    "change",
    ["extra-mount", "directory-mount", "writable", "no-seccomp", "no-nnp", "root-rw", "bad-role"],
)
def test_external_kernel_guard_refuses_weaker_or_wider_observations(change):
    data = manifest()
    observation = facts("T", data)
    if change == "extra-mount":
        observation["mountinfo"] += "40 1 0:4 /extra /input/record.json ro - ext4 /dev/test rw\n"
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
    with pytest.raises(ValueError):
        common.check_kernel_controls("unknown" if change == "bad-role" else "T", observation, data)
    with pytest.raises(ValueError):
        common.check_kernel_controls("B", facts("B"), data)


@pytest.mark.parametrize("role", ["T", "A", "B"])
def test_actual_kernel_reader_uses_fixed_facts_and_exact_declared_input_stats(monkeypatch, role):
    data = None if role == "B" else manifest(role)
    observation = facts(role, data)
    paths = {
        "/proc/self/status": observation["status"],
        "/proc/self/cgroup": observation["cgroup"],
        "/sys/fs/cgroup/memory.max": observation["memory"],
        "/sys/fs/cgroup/memory.swap.max": observation["swap"],
        "/sys/fs/cgroup/pids.max": observation["pids"],
        "/sys/fs/cgroup/cpu.max": observation["cpu"],
        "/proc/self/mountinfo": observation["mountinfo"],
        "/proc/net/dev": observation["network"],
    }
    fds, opened, closed, stats = {}, [], [], []
    imports = builtins.__import__

    def native_open(path, flags):
        assert path in paths and flags == 3
        fd = len(opened) + 10
        opened.append(path)
        fds[fd] = paths[path].encode()
        return fd

    def native_read(fd, limit):
        value, fds[fd] = fds[fd][:limit], fds[fd][limit:]
        return value

    def native_statvfs(path):
        stats.append(path)
        return SimpleNamespace(f_flag=1)

    fake_os = SimpleNamespace(
        O_RDONLY=0,
        O_NOFOLLOW=1,
        O_NONBLOCK=2,
        ST_RDONLY=1,
        open=native_open,
        read=native_read,
        close=closed.append,
        getpid=lambda: 1,
        getuid=lambda: 65532,
        getgid=lambda: 65532,
        statvfs=native_statvfs,
        stat=lambda path, **kwargs: SimpleNamespace(
            st_mode=stat.S_IFDIR | 0o700, st_uid=65532, st_gid=65532
        ),
    )
    monkeypatch.setattr(
        builtins,
        "__import__",
        lambda name, *a, **k: fake_os if name == "os" else imports(name, *a, **k),
    )
    assert common.require_kernel_controls(role, data) is None
    assert set(opened) == set(paths) and sorted(closed) == sorted(fds)
    assert stats == ([] if role == "B" else list(manifest_api.expected_input_paths(data, role)))


def test_source_bytes_and_test_checked_without_import_or_policy_reads(monkeypatch):
    data = manifest()
    texts = {
        "/input/project/main.py": _base().to_dict()["selection"]["files"][0]["text"].encode(),
        "/input/tests/test_authzest_regression.py": b"def test_read(client):\n    assert client\n",
    }
    reads = []

    def read(path, limit):
        reads.append((path, limit))
        return texts[path]

    monkeypatch.setattr(common, "_read_input", read)
    assert common.verify_input_files(data, "T") == data
    assert reads == [(path, 16_384) for path in texts]
    texts["/input/project/main.py"] += b"# edited"
    with pytest.raises(ValueError, match="repository-guest-input"):
        common.verify_input_files(data, "T")


def test_fixed_manifest_loader_and_bounded_regular_reader_use_fake_descriptors(monkeypatch):
    data = manifest()
    raw = canonical(data).encode()
    calls, chunks = [], [raw, b""]
    monkeypatch.setattr(os, "open", lambda path, flags: calls.append((path, flags)) or 42)
    monkeypatch.setattr(
        os, "fstat", lambda fd: SimpleNamespace(st_mode=stat.S_IFREG, st_size=len(raw))
    )
    monkeypatch.setattr(os, "read", lambda fd, limit: chunks.pop(0))
    monkeypatch.setattr(os, "close", lambda fd: calls.append(("close", fd)))
    assert common.load_manifest("T") == data
    assert calls[0][0] == "/input/manifest.json" and calls[-1] == ("close", 42)
    assert calls[0][1] & os.O_NOFOLLOW and calls[0][1] & os.O_NONBLOCK
    chunks[:] = [b"x" * 6]
    monkeypatch.setattr(os, "fstat", lambda fd: SimpleNamespace(st_mode=stat.S_IFREG, st_size=4))
    with pytest.raises(ValueError, match="repository-guest-input"):
        common._read_input("/input/manifest.json", 4)
    assert calls[-1] == ("close", 42)


def test_input_reader_rejects_nonregular_files_and_preserves_cancellation(monkeypatch):
    closed = []
    monkeypatch.setattr(os, "open", lambda *args: 42)
    monkeypatch.setattr(os, "close", closed.append)
    monkeypatch.setattr(os, "fstat", lambda fd: SimpleNamespace(st_mode=stat.S_IFDIR, st_size=0))
    with pytest.raises(ValueError, match="repository-guest-input"):
        common._read_input("/input/manifest.json", 16_384)
    assert closed == [42]
    first = KeyboardInterrupt("cancel")

    def cancelled(*args):
        raise first

    def failed_close(fd):
        closed.append(fd)
        raise OSError("close not confirmed")

    monkeypatch.setattr(os, "fstat", lambda fd: SimpleNamespace(st_mode=stat.S_IFREG, st_size=1))
    monkeypatch.setattr(os, "read", cancelled)
    monkeypatch.setattr(os, "close", failed_close)
    with pytest.raises(KeyboardInterrupt) as caught:
        common._read_input("/input/manifest.json", 16_384)
    assert caught.value is first and first.guest_input_descriptor_cleanup_unconfirmed is True
    assert closed == [42, 42]


def test_import_root_and_exact_entry_are_bound_after_trusted_preload():
    data = manifest(
        source="src/pkg/server.py",
        contexts=(("src/pkg/__init__.py", ""),),
        import_root="src",
        app="api",
    )
    search, app, imported = ["/trusted"], object(), []

    def importer(name):
        assert search[0] == "/input/project/src"
        imported.append(name)
        return SimpleNamespace(__file__="/input/project/src/pkg/server.py", api=app)

    assert (
        common.import_application(
            data,
            "T",
            import_module=importer,
            modules={"pytest": object()},
            search_path=search,
            stdlib_names={"json"},
        )
        is app
    )
    assert imported == ["pkg.server"]


@pytest.mark.parametrize("kind", ["cached", "stdlib", "trusted", "wrong-origin", "old-root"])
def test_import_refuses_cached_shadowed_or_wrong_source_without_fallback(kind):
    source = "json.py" if kind == "stdlib" else "pytest.py" if kind == "trusted" else "main.py"
    data = manifest(source=source)
    calls = []

    def importer(name):
        calls.append(name)
        return SimpleNamespace(__file__="/elsewhere/main.py", app=object())

    with pytest.raises(ValueError, match="repository-guest-import"):
        common.import_application(
            data,
            "T",
            import_module=importer,
            modules={"main.submodule": object()} if kind == "cached" else {},
            search_path=["/input/project"] if kind == "old-root" else ["/trusted"],
            stdlib_names={"json"},
        )
    assert calls == (["main"] if kind == "wrong-origin" else [])


def fixture_marker(**settings):
    assert settings == {"name": "client"}
    return lambda function: function


def test_trusted_client_fixture_has_no_lifespan_context_or_auth_override():
    app = SimpleNamespace(dependency_overrides={"existing": "untouched"})
    events = []

    class Client:
        def __init__(self, supplied_app):
            assert supplied_app is app
            events.append("client")

        def __enter__(self):
            pytest.fail("Lifespan context must remain off")

        def close(self):
            events.append("close")

    class Code(IntEnum):
        FAILED = 1

    def pytest_main(args, *, plugins):
        assert args == list(test_launcher.PYTEST_ARGS) and len(plugins) == 1
        generator = plugins[0].client()
        assert isinstance(next(generator), Client)
        events.append("test")
        with pytest.raises(StopIteration):
            next(generator)
        return Code.FAILED

    assert (
        test_launcher.run_test(
            app, pytest_main=pytest_main, fixture=fixture_marker, test_client=Client
        )
        == 1
    )
    assert events == ["client", "test", "close"]
    assert app.dependency_overrides == {"existing": "untouched"}
    assert "--noconftest" in test_launcher.PYTEST_ARGS
    assert "--import-mode=importlib" in test_launcher.PYTEST_ARGS
    assert test_launcher.PYTEST_ARGS[-1] == "/input/tests/test_authzest_regression.py"


@pytest.mark.parametrize("code", [True, None, -1, 6, "0"])
def test_pytest_return_contract_rejects_nonexit_values(code):
    with pytest.raises(ValueError, match="repository-guest-test-exit"):
        test_launcher.run_test(
            object(),
            pytest_main=lambda *a, **k: code,
            fixture=fixture_marker,
            test_client=lambda app: None,
        )


def test_app_object_fixed_server_controls_and_startup_hint_are_auxiliary():
    events = []

    async def app(scope, receive, send):
        events.append((scope, receive, send))

    def config(supplied_app, **settings):
        # Simulate Uvicorn's factory probe: it must never reach the target.
        with pytest.raises(TypeError):
            supplied_app()
        assert events == []
        coroutine = supplied_app("scope", "receive", "send")
        with pytest.raises(StopIteration):
            coroutine.send(None)
        assert settings == app_launcher.SERVER_SETTINGS
        assert settings["lifespan"] == "off" and settings["factory"] is False
        assert settings["reload"] is False and settings["env_file"] is None
        return object()

    class Server:
        started, should_exit = True, False

        def __init__(self, config):
            events.append("configured")

        async def startup(self, sockets=None):
            events.append("startup")

        def run(self):
            coroutine = self.startup()
            with pytest.raises(StopIteration):
                coroutine.send(None)

    def write(text):
        events.append(text)
        return len(text)

    app_launcher.run_ready_app(
        app, config, Server, write=write, flush=lambda: events.append("flush")
    )
    assert events == [
        ("scope", "receive", "send"),
        "configured",
        "startup",
        app_launcher.READY_MARKER,
        "flush",
    ]


@pytest.mark.parametrize("role", ["T", "A"])
@pytest.mark.parametrize("kernel_failure", [False, True], ids=["guarded", "refused"])
def test_real_entry_control_flow_uses_fake_guards_tools_and_imports(
    monkeypatch, role, kernel_failure
):
    launcher = test_launcher if role == "T" else app_launcher
    data, events = manifest(role), []
    monkeypatch.setattr(launcher, "__file__", launcher.SCRIPT_PATH)
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(sys, "flags", SimpleNamespace(isolated=1, dont_write_bytecode=1))
    monkeypatch.setattr(sys, "dont_write_bytecode", True)
    monkeypatch.setattr(sys, "argv", [launcher.SCRIPT_PATH])
    monkeypatch.setattr(sys, "path", ["/trusted"])
    monkeypatch.setattr(os, "environ", {})
    monkeypatch.setattr(os, "getuid", lambda: 65532, raising=False)
    monkeypatch.setattr(os, "getgid", lambda: 65532, raising=False)

    def kernel(*args):
        events.append("kernel")
        if kernel_failure:
            raise ValueError("unsupported")

    def import_app(*args, **kwargs):
        events.append("app")
        assert all("tool:" + name in events for name in launcher.TRUSTED_PRELOAD)
        return object()

    fake_common = SimpleNamespace(
        entry_allowed=common.entry_allowed,
        prepare_environment=common.prepare_environment,
        load_manifest=lambda role: events.append("manifest") or data,
        require_kernel_controls=kernel,
        verify_input_files=lambda *args: events.append("bytes"),
        import_application=import_app,
    )
    monkeypatch.setitem(sys.modules, "_guest_common", fake_common)

    def trusted_import(name):
        assert "kernel" in events and "bytes" in events and "app" not in events
        events.append("tool:" + name)
        return SimpleNamespace(
            main=lambda *a, **k: 0,
            fixture=fixture_marker,
            TestClient=object,
            Config=object,
            Server=object,
        )

    monkeypatch.setattr(importlib, "import_module", trusted_import)
    if role == "A":
        monkeypatch.setattr(app_launcher, "run_ready_app", lambda *a, **k: events.append("serve"))
    assert launcher._script_main() == (78 if kernel_failure else 0)
    assert events[:2] == ["manifest", "kernel"]
    assert ("app" in events) is not kernel_failure
    assert not any(event.startswith("tool:") for event in events) if kernel_failure else True


def test_accidental_host_entry_refuses_before_any_input_or_tool():
    assert test_launcher._script_main() == 64
    assert app_launcher._script_main() == 64
