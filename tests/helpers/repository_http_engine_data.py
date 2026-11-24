"""Owned inert HTTP Engine declarations and memory streams; no actual daemon."""

import stat
from copy import deepcopy

from authzest.codex.contracts import canonical
from authzest.runner._generated_repair_engine_http import EngineResponse
from authzest.runner._generated_repair_preflight import engine_identity_sha256
from authzest.runner._repository_http_runtime_profile import (
    EMPTY_CONFIG_SHA256,
    expected_assets,
    expected_recipe_pins,
    validate_runtime_profile,
)

PIN = {
    "socket_identity": [1, 2, stat.S_IFSOCK | 0o660, 0, 0, 1, 0, 7, 8],
    "parent_chain_sha256": "a" * 64,
}


def profile_data():
    return {
        "schema_version": "2.0",
        "kind": "repository-http-runtime-profile",
        "platform": "linux/arm64",
        "engine": {
            "executable": "/reviewed/bin/docker",
            "executable_sha256": "1" * 64,
            "endpoint": "unix:///reviewed/run/docker.sock",
            "config_dir": "/reviewed/config",
            "config_json_sha256": EMPTY_CONFIG_SHA256,
            "server_identity_sha256": engine_identity_sha256("synthetic-http-engine"),
            "api_version": "1.47",
        },
        "images": {
            role: {
                "image_id": "sha256:" + ("3" if role == "A" else "4") * 64,
                **expected_recipe_pins("linux/arm64", role),
                "assets": expected_assets(role),
            }
            for role in ("A", "B")
        },
    }


def profile():
    return validate_runtime_profile(canonical(profile_data()))


def frame(operation, payload):
    raw = canonical(payload).encode()
    return EngineResponse(operation, raw, len(raw) + 80, deepcopy(PIN))


def metadata_context():
    checked = profile()
    data = checked.to_dict()
    frames = [
        frame(
            "version",
            {
                "Version": "29.0.0",
                "ApiVersion": "1.51",
                "MinAPIVersion": "1.41",
                "Os": "linux",
                "Arch": "arm64",
                "Ignored": "never-copy-this-synthetic-extra-field",
            },
        ),
        frame(
            "info",
            {
                "ID": "synthetic-http-engine",
                "ServerVersion": "29.0.0",
                "OSType": "linux",
                "Architecture": "aarch64",
                "CgroupVersion": "2",
                "CgroupDriver": "systemd",
                "DefaultRuntime": "runc",
                "SecurityOptions": ["name=seccomp,profile=builtin"],
                "MemoryLimit": True,
                "SwapLimit": False,
                "PidsLimit": True,
                "Ignored": "never-copy-this-synthetic-extra-field",
            },
        ),
    ]
    for role in ("A", "B"):
        frames.append(
            frame(
                "image-" + role,
                {
                    "Id": data["images"][role]["image_id"],
                    "Os": "linux",
                    "Architecture": "arm64",
                    "Variant": "v8",
                    "Config": {
                        "Env": ["PYTHONDONTWRITEBYTECODE=1"],
                        "Entrypoint": ["/usr/local/bin/python"],
                        "Cmd": None,
                        "User": "65532:65532",
                        "Volumes": None,
                        "Healthcheck": {"Test": ["NONE"]},
                    },
                    "Ignored": "never-copy-this-synthetic-extra-field",
                },
            )
        )
    return checked, frames


class MemorySocket:
    def __init__(self, wire=b""):
        self.wire = wire
        self.sent, self.connected, self.timeouts, self.read_sizes = [], [], [], []
        self.closed = 0

    def settimeout(self, value):
        self.timeouts.append(value)

    def connect(self, path):
        self.connected.append(path)

    def sendall(self, value):
        self.sent.append(value)

    def recv(self, size):
        self.read_sizes.append(size)
        result, self.wire = self.wire[:size], self.wire[size:]
        return result

    def close(self):
        self.closed += 1


def response(body=b'{"synthetic":true}', framing="length"):
    header = b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
    if framing == "length":
        return header + b"Content-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body
    if framing == "chunked":
        chunks = b"".join(
            f"{len(chunk):x}\r\n".encode() + chunk + b"\r\n"
            for chunk in (body[:3], body[3:])
            if chunk
        )
        return header + b"Transfer-Encoding: chunked\r\n\r\n" + chunks + b"0\r\n\r\n"
    return header + b"\r\n" + body
