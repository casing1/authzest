"""Read-only HTTP client/config/endpoint file comparison, never a dispatch.

The synchronous caller supplies its original phase/setup deadline check. Files
are repeatedly inspected and hashed, not executed. No socket is acquired. The
trusted operator excludes hostile same-user writers; named checks are not CAS
or daemon authentication and filesystem calls have no independent wall bound.
"""

from __future__ import annotations

import inspect
import os
import stat
import sys
import threading
from hashlib import sha256
from pathlib import Path

from authzest.codex.contracts import canonical, decode
from authzest.runner._generated_repair_engine_http import _endpoint_identity
from authzest.runner._repository_http_runtime_profile import (
    RepositoryHttpRuntimeProfile,
    validate_runtime_profile,
)


class RepositoryHttpClientPinError(RuntimeError):
    """Redacted current-file comparison failure, never a readiness result."""


def _fail(reason):
    raise RepositoryHttpClientPinError(reason)


def _redacted_failure(exc):
    if not isinstance(exc, Exception) or isinstance(exc, RepositoryHttpClientPinError):
        raise exc
    error = RepositoryHttpClientPinError("http-client-files-unavailable")
    if hasattr(exc, "descriptor_cleanup_confirmed"):
        error.descriptor_cleanup_confirmed = exc.descriptor_cleanup_confirmed
    raise error from exc


def _identity(info):
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_uid,
        info.st_gid,
        info.st_nlink,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


def _directory(path, *, private=False):
    info = os.lstat(path)
    if (
        not stat.S_ISDIR(info.st_mode)
        or info.st_uid not in {0, os.geteuid()}
        or info.st_mode & 0o022
        and not info.st_mode & stat.S_ISVTX
        or private
        and (info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700)
    ):
        _fail("http-client-or-config-parent-unavailable")
    return _identity(info) if private else _identity(info)[:5]


def _file(path, *, maximum, private):
    info = os.lstat(path)
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_uid not in {0, os.geteuid()}
        or info.st_mode & 0o7022
        or info.st_nlink != 1
        or not 0 < info.st_size <= maximum
        or private
        and (info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o600)
    ):
        _fail("http-client-or-config-file-unavailable")
    return _identity(info)


def _digest(path, *, maximum, private, tick):
    tick()
    observed = _file(path, maximum=maximum, private=private)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    first, result, cleanup = None, None, True
    try:
        if _identity(os.fstat(fd)) != observed:
            _fail("http-client-or-config-file-changed")
        total, digest = 0, sha256()
        while True:
            tick()
            chunk = os.read(fd, min(262_144, maximum - total + 1))
            if type(chunk) is not bytes:
                _fail("http-client-or-config-read-unconfirmed")
            total += len(chunk)
            if total > maximum:
                _fail("http-client-or-config-size-limit")
            digest.update(chunk)
            if not chunk:
                break
        if (
            total != observed[6]
            or _identity(os.fstat(fd)) != observed
            or _file(path, maximum=maximum, private=private) != observed
        ):
            _fail("http-client-or-config-file-changed")
        tick()
        result = digest.hexdigest(), observed
    except BaseException as exc:
        first = exc
    try:
        os.close(fd)
    except BaseException as exc:
        cleanup = False
        if first is None or isinstance(first, Exception) and not isinstance(exc, Exception):
            first = exc
    if first is not None:
        if not isinstance(first, Exception):
            first.http_client_descriptor_cleanup_confirmed = cleanup
            raise first
        error = RepositoryHttpClientPinError(
            str(first)
            if isinstance(first, RepositoryHttpClientPinError)
            else "http-client-read-failed"
        )
        error.descriptor_cleanup_confirmed = cleanup
        raise error from first
    return result


class RepositoryHttpClientPin:
    """One current-process binding; snapshots cannot reconstruct this live checker.

    This checks the declared executable bytes and empty private configuration,
    plus no-follow endpoint and parent names. It neither contacts the daemon nor
    checks images/kernel controls. The caller must also recheck its held profile
    file/session/stage and require actual direct phase results before applying.
    """

    def __init__(self, profile: RepositoryHttpRuntimeProfile, tick):
        if (
            type(self) is not RepositoryHttpClientPin
            or type(profile) is not RepositoryHttpRuntimeProfile
        ):
            _fail("http-client-profile-type-invalid")
        if (
            not callable(tick)
            or inspect.iscoroutinefunction(tick)
            or inspect.isgeneratorfunction(tick)
            or inspect.isasyncgenfunction(tick)
        ):
            _fail("http-client-deadline-check-invalid")
        self._profile = profile
        self._profile_json = validate_runtime_profile(profile.payload_json).payload_json
        self._tick_hook = tick
        self._pid, self._thread = os.getpid(), threading.get_ident()
        self._busy, self._failed, self._identity_json = True, False, None
        try:
            self._compare(initial=True)
        except BaseException as exc:
            self._failed = True
            _redacted_failure(exc)
        finally:
            self._busy = False

    def __copy__(self):
        raise TypeError("Live HTTP client pins cannot be copied")

    def __deepcopy__(self, memo):
        raise TypeError("Live HTTP client pins cannot be copied")

    def __reduce__(self):
        raise TypeError("Live HTTP client pins cannot be serialized")

    def _owner(self):
        if (
            type(self) is not RepositoryHttpClientPin
            or self._pid != os.getpid()
            or self._thread != threading.get_ident()
        ):
            _fail("http-client-owner-unavailable")

    def _tick(self):
        self._owner()
        if self._failed:
            _fail("http-client-pin-unavailable")
        answer = self._tick_hook()
        if answer is not None:
            if inspect.iscoroutine(answer):
                answer.close()
            _fail("http-client-deadline-check-unconfirmed")
        self._owner()
        if self._failed:
            _fail("http-client-pin-unavailable")

    def _compare(self, *, initial=False):
        self._tick()
        if (
            os.name != "posix"
            or getattr(sys, "frozen", False)
            or not hasattr(os, "O_NOFOLLOW")
            or not hasattr(os, "O_NONBLOCK")
        ):
            _fail("http-client-platform-unsupported")
        if type(self._profile) is not RepositoryHttpRuntimeProfile:
            _fail("http-client-profile-type-invalid")
        checked = validate_runtime_profile(self._profile.payload_json)
        if checked.payload_json != self._profile_json:
            _fail("http-client-profile-changed")
        engine = checked.to_dict()["engine"]
        parents = {}
        for path in (engine["config_dir"], engine["executable"]):
            for parent in reversed(Path(path).parents):
                self._tick()
                parents[str(parent)] = list(_directory(parent))
        directory = _directory(engine["config_dir"], private=True)
        if os.listdir(engine["config_dir"]) != ["config.json"]:
            _fail("http-client-private-empty-config-required")
        if not os.access(engine["executable"], os.X_OK):
            _fail("http-client-not-executable")
        client_digest, client_identity = _digest(
            engine["executable"], maximum=134_217_728, private=False, tick=self._tick
        )
        config_path = str(Path(engine["config_dir"]) / "config.json")
        config_digest, config_identity = _digest(
            config_path, maximum=3, private=True, tick=self._tick
        )
        if (
            client_digest != engine["executable_sha256"]
            or config_digest != engine["config_json_sha256"]
        ):
            _fail("http-client-or-empty-config-digest-mismatch")
        self._tick()
        endpoint = _endpoint_identity(engine["endpoint"][7:])
        self._tick()
        if (
            _file(engine["executable"], maximum=134_217_728, private=False) != client_identity
            or _file(config_path, maximum=3, private=True) != config_identity
            or _directory(engine["config_dir"], private=True) != directory
            or os.listdir(engine["config_dir"]) != ["config.json"]
            or any(list(_directory(path)) != value for path, value in parents.items())
        ):
            _fail("http-client-config-or-parent-changed")
        value = canonical(
            {
                "client": list(client_identity),
                "config": list(config_identity),
                "directory": list(directory),
                "parents": parents,
                "endpoint": endpoint,
            }
        )
        if not initial and value != self._identity_json:
            _fail("http-client-config-or-endpoint-changed")
        self._tick()
        # The synchronous hook is trusted coordination, but it can replace a
        # frozen profile reference or suppress a reflective mutation. Recheck
        # the complete current declaration after the final callback so the
        # committed file observations cannot be exported under a new profile.
        if type(self._profile) is not RepositoryHttpRuntimeProfile:
            _fail("http-client-profile-type-invalid")
        if (
            validate_runtime_profile(self._profile.payload_json).payload_json
            != checked.payload_json
        ):
            _fail("http-client-profile-changed")
        self._identity_json = value

    def check(self) -> None:
        self._owner()
        if self._busy or self._failed:
            self._failed = True
            _fail("http-client-pin-unavailable")
        self._busy = True
        try:
            self._compare()
        except BaseException as exc:
            self._failed = True
            _redacted_failure(exc)
        finally:
            self._busy = False

    @property
    def identity(self) -> dict:
        self.check()
        return decode(self._identity_json)

    def review_dict(self) -> dict:
        self.check()
        return {
            "schema_version": "2.0",
            "kind": "repository-http-client-file-review",
            "status": "client-config-endpoint-files-match",
            "profile_id": self._profile.profile_id,
            "file_observations": decode(self._identity_json),
            "engine_contact_attempted": False,
            "runtime_invoked": False,
            "execution_authorized": False,
            "resource_enforcement_established": False,
            "isolation_established": False,
            "authorization_status": "unknown",
            "verified_fix": False,
        }
