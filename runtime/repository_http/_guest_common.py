"""Separate HTTP-only external entry guards, never an attestation or host authority."""

from __future__ import annotations

import posixpath
import re

GUEST_ROOT = "/opt/authzest-repository-http-guest"
_SCRIPTS = {"A": "app_launcher.py", "B": "relay_launcher.py"}
_MANIFEST_API = None
_TRUSTED_ROOTS = frozenset(
    {
        "pytest",
        "_pytest",
        "pluggy",
        "iniconfig",
        "packaging",
        "fastapi",
        "starlette",
        "pydantic",
        "pydantic_core",
        "typing_extensions",
        "typing_inspection",
        "annotated_types",
        "annotated_doc",
        "anyio",
        "sniffio",
        "httpx",
        "httpcore",
        "h11",
        "uvicorn",
        "click",
        "certifi",
        "idna",
        "exceptiongroup",
    }
)
# Closed kernel fallback devices, not a general interface-name allowlist. The
# values are (ARPHRD type, exact administratively-DOWN sysfs flags).
_FALLBACK_INTERFACES = {
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
_NETWORK_ATTRIBUTES = ("flags", "operstate", "type", "ifindex", "iflink")


def _manifest_api():
    """Load only the maintained helper at its fixed immutable-image location."""
    global _MANIFEST_API
    if _MANIFEST_API is None:
        import importlib.util

        path = GUEST_ROOT + "/repository_http_manifest.py"
        spec = importlib.util.spec_from_file_location("_authzest_repository_http_manifest", path)
        if spec is None or spec.loader is None:
            raise ValueError("repository-http-guest-helper")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _MANIFEST_API = module
    return _MANIFEST_API


def _expected_input_paths(role, manifest):
    if type(role) is not str or role not in _SCRIPTS:
        raise ValueError("repository-http-guest-role")
    if role == "B":
        if manifest is not None:
            raise ValueError("repository-http-guest-manifest")
        return ()
    return _manifest_api().expected_input_paths(manifest)


def _mount_path(path):
    # Linux mountinfo escapes separators inside individual path components.
    return path.replace("\\", "\\134").replace(" ", "\\040")


def _read_input(path, limit):
    """Read one exact, bounded regular input; never discover or follow links."""
    import os
    import stat

    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    failure = None
    try:
        facts = os.fstat(fd)
        if not stat.S_ISREG(facts.st_mode) or not 0 <= facts.st_size <= limit:
            raise ValueError("repository-http-guest-input")
        data = bytearray()
        while True:
            chunk = os.read(fd, min(4096, limit + 1 - len(data)))
            data.extend(chunk)
            if len(data) > limit:
                raise ValueError("repository-http-guest-input")
            if not chunk:
                if len(data) != facts.st_size:
                    raise ValueError("repository-http-guest-input")
                return bytes(data)
    except BaseException as exc:
        failure = exc
        raise
    finally:
        try:
            os.close(fd)
        except BaseException as exc:
            if failure is None or isinstance(failure, Exception) and not isinstance(exc, Exception):
                raise
            failure.guest_input_descriptor_cleanup_unconfirmed = True


def load_manifest(role):
    if role != "A":
        raise ValueError("repository-http-guest-role")
    api = _manifest_api()
    return api.validate_guest_manifest(_read_input(api.MANIFEST_PATH, api.MAX_MANIFEST_BYTES))


def verify_input_files(manifest, role):
    """Verify exactly one captured source after the guest kernel checks."""
    import hashlib

    if role != "A":
        raise ValueError("repository-http-guest-input")
    api = _manifest_api()
    checked = api.validate_guest_manifest(manifest)
    item = checked["source"]
    data = _read_input(api.PROJECT_ROOT + "/" + item["path"], api.MAX_FILE_BYTES)
    if len(data) != item["size_bytes"] or hashlib.sha256(data).hexdigest() != item["sha256"]:
        raise ValueError("repository-http-guest-input")
    return checked


def import_application(manifest, role, *, import_module, modules, search_path, stdlib_names):
    """Import only inside a guarded guest, after trusted tools have been loaded.

    Exact path comparison is a refusal check, not attestation: target code can
    mutate its module metadata and remains untrusted throughout this process.
    """
    if role != "A":
        raise ValueError("repository-http-guest-import")
    checked = _manifest_api().validate_guest_manifest(manifest)
    interface = checked["http_interface"]
    if (
        type(modules) is not dict
        or type(search_path) is not list
        or any(type(value) is not str for value in search_path)
        or type(stdlib_names) not in (set, frozenset)
        or any(type(value) is not str for value in stdlib_names)
    ):
        raise ValueError("repository-http-guest-import")
    root = "/input/project"
    selected_roots = {interface["module"]}
    loaded_roots = {name.split(".")[0] for name in modules if type(name) is str}
    if selected_roots & (loaded_roots | set(stdlib_names) | _TRUSTED_ROOTS):
        raise ValueError("repository-http-guest-import")
    if any(value == "/input" or value.startswith("/input/") for value in search_path):
        raise ValueError("repository-http-guest-import")
    search_path.insert(0, root)
    module = import_module(interface["module"])
    expected = "/input/project/" + interface["entry_source"]
    if getattr(module, "__file__", None) != expected:
        raise ValueError("repository-http-guest-import")
    # No discovery, dotted attributes or factory invocation.
    return getattr(module, interface["app_attribute"])


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


def _kernel_text(text):
    if (
        type(text) is not str
        or len(text) > 65_536
        or not text.isascii()
        or any((ord(char) < 32 and char not in "\t\n") or ord(char) == 127 for char in text)
    ):
        raise ValueError("guest-kernel-controls")
    return text


def _network_names(text):
    lines = _kernel_text(text).splitlines()
    if (
        not 3 <= len(lines) <= 12
        or not lines[0].startswith("Inter-|")
        or not lines[1].lstrip().startswith("face |")
    ):
        raise ValueError("guest-kernel-controls")
    names = []
    for line in lines[2:]:
        name, separator, counters = line.partition(":")
        name = name.strip()
        # Counters are syntax only; zero/nonzero counters establish no safety.
        if (
            not separator
            or name not in {"lo", *_FALLBACK_INTERFACES}
            or name in names
            or re.fullmatch(r"[ \t]*[0-9]{1,20}(?:[ \t]+[0-9]{1,20}){0,15}[ \t]*", counters) is None
        ):
            raise ValueError("guest-kernel-controls")
        names.append(name)
    if "lo" not in names:
        raise ValueError("guest-kernel-controls")
    return names


def _network_snapshot(names, snapshot):
    if type(snapshot) is not dict or set(snapshot) != set(names):
        raise ValueError("guest-kernel-controls")
    indexes = set()
    for name in names:
        entry = snapshot[name]
        if type(entry) is not dict or set(entry) != set(_NETWORK_ATTRIBUTES):
            raise ValueError("guest-kernel-controls")
        if (
            any(type(entry[key]) is not int for key in ("flags", "type", "ifindex", "iflink"))
            or type(entry["operstate"]) is not str
            or not 1 <= entry["ifindex"] <= 2**31 - 1
            or entry["ifindex"] in indexes
        ):
            raise ValueError("guest-kernel-controls")
        indexes.add(entry["ifindex"])
        if name == "lo":
            expected_type, expected_flags = 772, 0x9
            expected_state, expected_link = "unknown", entry["ifindex"]
        else:
            expected_type, expected_flags = _FALLBACK_INTERFACES[name]
            expected_state, expected_link = "down", 0
        if (
            entry["type"] != expected_type
            or entry["flags"] != expected_flags
            or entry["operstate"] != expected_state
            or entry["iflink"] != expected_link
        ):
            raise ValueError("guest-kernel-controls")


def _check_network(observation):
    names = _network_names(observation["network"])
    if names == ["lo"] and "network_interfaces" not in observation:
        return
    detail = observation.get("network_interfaces")
    if type(detail) is not dict or set(detail) != {"before", "after", "names_after"}:
        raise ValueError("guest-kernel-controls")
    after_names = detail["names_after"]
    if (
        type(after_names) is not list
        or not 1 <= len(after_names) <= 10
        or any(type(name) is not str for name in after_names)
        or len(set(after_names)) != len(after_names)
        or set(after_names) != set(names)
    ):
        raise ValueError("guest-kernel-controls")
    # Validate native scalar types before equality (True must not equal 1).
    _network_snapshot(names, detail["before"])
    _network_snapshot(names, detail["after"])
    if detail["before"] != detail["after"]:
        raise ValueError("guest-kernel-controls")


def _read_network_snapshot(names, read):
    result = {}
    for name in names:
        # _network_names has already constrained names to this fixed set.
        entry = {}
        for key in _NETWORK_ATTRIBUTES:
            raw = read("/sys/class/net/" + name + "/" + key, 64)
            if key == "operstate":
                if re.fullmatch(r"(?:down|unknown)\n?", raw, re.ASCII) is None:
                    raise ValueError("guest-kernel-controls")
                entry[key] = raw.removesuffix("\n")
            elif key == "flags":
                if re.fullmatch(r"0x[0-9a-f]{1,8}\n?", raw, re.ASCII) is None:
                    raise ValueError("guest-kernel-controls")
                entry[key] = int(raw.removesuffix("\n")[2:], 16)
            else:
                if re.fullmatch(r"[0-9]{1,10}\n?", raw, re.ASCII) is None:
                    raise ValueError("guest-kernel-controls")
                entry[key] = int(raw.removesuffix("\n"))
        result[name] = entry
    return result


def check_kernel_controls(role, observation, manifest=None) -> None:
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
    if type(observation) is not dict or set(observation) not in (
        fields,
        fields | {"network_interfaces"},
    ):
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
        _kernel_text(observation[key])
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
    _check_network(observation)
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
    expected_inputs = _expected_input_paths(role, manifest)
    encoded_inputs = [_mount_path(path) for path in expected_inputs]
    if sorted(name for name in mounts if name == "/input" or name.startswith("/input/")) != sorted(
        encoded_inputs
    ):
        raise ValueError("guest-kernel-controls")
    if (
        type(observation["input_readonly"]) is not list
        or len(observation["input_readonly"]) != len(expected_inputs)
        or any(value is not True for value in observation["input_readonly"])
    ):
        raise ValueError("guest-kernel-controls")
    for target in encoded_inputs:
        if "ro" not in mounts[target][0] or "rw" in mounts[target][0]:
            raise ValueError("guest-kernel-controls")


def require_kernel_controls(role, manifest=None) -> None:
    """Read only fixed Linux kernel/filesystem paths, before any target import.

    No process, network, writes, retries or target contents are used. An absent
    property is unsupported. Blocking kernel operations still rely on the host
    phase deadline/cleanup, rather than a universal guest-side wall-time bound.
    """
    import os
    import stat

    if type(role) is not str or role not in _SCRIPTS:
        raise ValueError("guest-kernel-controls")

    def read(path, limit=65_536):
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        failure = None
        try:
            data = bytearray()
            while True:
                chunk = os.read(fd, min(4096, limit + 1 - len(data)))
                data.extend(chunk)
                if len(data) > limit:
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
    inputs = _expected_input_paths(role, manifest)
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
    names = _network_names(observation["network"])
    if names != ["lo"]:
        before = _read_network_snapshot(names, read)
        after = _read_network_snapshot(names, read)
        observation["network_interfaces"] = {
            "before": before,
            "after": after,
            "names_after": _network_names(read("/proc/net/dev")),
        }
    check_kernel_controls(role, observation, manifest)
