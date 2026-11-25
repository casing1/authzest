"""Prepare the reviewed HTTP A/B runtime: wheels, images and a private profile.

This is an explicit operator step with effects, run from a source checkout:

1. ``wheels``  – download the exact pinned A wheels from files.pythonhosted.org
   into a new private wheelhouse and verify every byte (network).
2. ``build``   – prepare minimal private A/B contexts and run ``docker build``
   with the maintained Dockerfiles, without provenance/SBOM attestations.
3. ``profile`` – copy the Docker CLI into a private directory, create an empty
   private Docker config and write the private runtime profile for repo-fix.

Nothing here runs a target application, a model or a guest container.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import subprocess
import sys
import urllib.request
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlparse

from authzest.codex.contracts import canonical
from authzest.runner._generated_repair_preflight import engine_identity_sha256
from authzest.runner._repository_http_runtime_profile import (
    EMPTY_CONFIG_SHA256,
    expected_assets,
    expected_recipe_pins,
    validate_runtime_profile,
)
from scripts import repository_http_image_context as contexts
from scripts import repository_http_image_inputs as inputs

PLATFORM = "linux/arm64"
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE = Path.home() / ".authzest" / "runtime"
MAX_WHEEL_BYTES = 16 * 1024 * 1024


class SetupError(RuntimeError):
    """A setup step failed; created files are retained for inspection."""


def _private_directory(path: Path) -> Path:
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = os.lstat(path)
    if (
        not stat.S_ISDIR(info.st_mode)
        or info.st_uid != os.geteuid()
        or stat.S_IMODE(info.st_mode) != 0o700
    ):
        raise SetupError(f"{path} must be a private 0700 directory owned by you")
    return path


def _write_new(path: Path, data: bytes, mode: int) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    try:
        os.fchmod(fd, mode)
        view = memoryview(data)
        while view:
            view = view[os.write(fd, view) :]
        os.fsync(fd)
    finally:
        os.close(fd)


def wheel_plan(root: Path = ROOT, role: str = "A") -> list[dict]:
    """The exact pinned wheel set for one role; no network access."""
    _, base, _ = inputs.selected_inputs(root, role, PLATFORM)
    entry = base["roles"][role]["platforms"][PLATFORM]
    return [base["packages"][name]["wheels"][PLATFORM] for name in entry["packages"]]


def download_wheels(output: Path, *, root: Path = ROOT, opener=urllib.request.urlopen) -> dict:
    """Download each pinned A wheel once into a NEW private directory and verify it."""
    if output.exists():
        raise SetupError("Wheelhouse output must not exist yet")
    output.mkdir(mode=0o700, parents=False)
    for wheel in wheel_plan(root, "A"):
        url = urlparse(wheel["url"])
        if url.scheme != "https" or url.hostname != "files.pythonhosted.org":
            raise SetupError("Pinned wheel URL is not on files.pythonhosted.org over HTTPS")
        with opener(wheel["url"], timeout=60) as response:
            raw = response.read(MAX_WHEEL_BYTES + 1)
        if len(raw) != wheel["size"] or sha256(raw).hexdigest() != wheel["sha256"]:
            raise SetupError("Downloaded wheel differs from its pinned size/sha256")
        _write_new(output / wheel["filename"], raw, 0o600)
    return inputs.verify_wheelhouse(root, output, "A", PLATFORM)


def _run(argv: list[str], *, runner=subprocess.run) -> str:
    completed = runner(argv, check=False, capture_output=True, text=True, timeout=900)
    if completed.returncode != 0:
        raise SetupError(f"Command failed ({completed.returncode}): {' '.join(argv[:3])} ...")
    return completed.stdout


def build_images(
    wheelhouse: Path,
    work: Path,
    *,
    root: Path = ROOT,
    docker: str = "docker",
    runner=subprocess.run,
) -> dict:
    """Build A and B from fresh minimal contexts; return the reported image IDs."""
    _private_directory(work)
    # B has no wheels; its empty input root must not overlap the output parent.
    empty = work.parent / (work.name + "-empty-wheelhouse")
    empty.mkdir(mode=0o700, exist_ok=True)
    images = {}
    for role, wheels in (("A", wheelhouse), ("B", empty)):
        inputs.verify_wheelhouse(root, wheels, role, PLATFORM)
        prepared = contexts.prepare_image_context(root, wheels, work, role, PLATFORM)
        contexts.check_prepared_context(prepared.context_path, prepared)
        recipe = expected_recipe_pins(PLATFORM, role)["recipe_sha256"]
        tag = f"authzest-repository-http-{role.lower()}:{recipe[:12]}"
        _run(
            [
                docker,
                "build",
                "--platform=" + PLATFORM,
                "--pull=false",
                "--provenance=false",
                "--sbom=false",
                "--tag=" + tag,
                str(prepared.context_path),
            ],
            runner=runner,
        )
        image_id = _run(
            [docker, "image", "inspect", "--format={{.Id}}", tag], runner=runner
        ).strip()
        if not image_id.startswith("sha256:") or len(image_id) != 71:
            raise SetupError("Built image ID is not a sha256 digest")
        images[role] = {"tag": tag, "image_id": image_id}
    return images


def write_profile(
    images: dict,
    *,
    state: Path = DEFAULT_STATE,
    docker: str | None = None,
    runner=subprocess.run,
) -> Path:
    """Pin a private CLI copy, empty config, endpoint and engine identity."""
    _private_directory(state)
    source = Path(os.path.realpath(docker or shutil.which("docker") or ""))
    if not source.is_file():
        raise SetupError("Docker CLI was not found")
    bin_dir = _private_directory(state / "bin")
    client = bin_dir / "docker"
    if client.exists():
        raise SetupError(f"{client} already exists; move it aside to re-run setup")
    _write_new(client, source.read_bytes(), 0o755)
    config = _private_directory(state / "docker-config")
    if not (config / "config.json").exists():
        _write_new(config / "config.json", b"{}\n", 0o600)
    endpoint = _run(
        [str(client), "context", "inspect", "--format={{.Endpoints.docker.Host}}"], runner=runner
    ).strip()
    if not endpoint.startswith("unix://"):
        raise SetupError("Only a local unix Docker endpoint is supported")
    versions = _run(
        [
            str(client),
            "--config=" + str(config),
            "--host=" + endpoint,
            "version",
            "--format={{.Client.APIVersion}} {{.Server.APIVersion}}",
        ],
        runner=runner,
    ).split()
    api = min(versions, key=lambda value: tuple(int(part) for part in value.split(".")))
    engine_id = _run(
        [str(client), "--config=" + str(config), "--host=" + endpoint, "info", "--format={{.ID}}"],
        runner=runner,
    ).strip()
    profile = {
        "schema_version": "2.0",
        "kind": "repository-http-runtime-profile",
        "platform": PLATFORM,
        "engine": {
            "executable": str(client),
            "executable_sha256": sha256(client.read_bytes()).hexdigest(),
            "endpoint": endpoint,
            "config_dir": str(config),
            "config_json_sha256": EMPTY_CONFIG_SHA256,
            "server_identity_sha256": engine_identity_sha256(engine_id),
            "api_version": api,
        },
        "images": {
            role: {
                "image_id": images[role]["image_id"],
                **expected_recipe_pins(PLATFORM, role),
                "assets": expected_assets(role),
            }
            for role in ("A", "B")
        },
    }
    raw = canonical(profile)
    validate_runtime_profile(raw)
    path = state / "runtime.json"
    if path.exists():
        raise SetupError(f"{path} already exists; move it aside to re-run setup")
    _write_new(path, (raw + "\n").encode(), 0o600)
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    wheels = commands.add_parser("wheels", help="Download and verify the pinned A wheels.")
    wheels.add_argument("--output", type=Path, required=True)
    build = commands.add_parser("build", help="Build the A/B images from fresh contexts.")
    build.add_argument("--wheelhouse", type=Path, required=True)
    build.add_argument("--work", type=Path, default=DEFAULT_STATE / "build")
    build.add_argument("--images-json", type=Path, default=DEFAULT_STATE / "images.json")
    profile = commands.add_parser("profile", help="Write the private runtime profile.")
    profile.add_argument("--images-json", type=Path, default=DEFAULT_STATE / "images.json")
    profile.add_argument("--state", type=Path, default=DEFAULT_STATE)
    args = parser.parse_args(argv)
    try:
        if args.command == "wheels":
            print(json.dumps(download_wheels(args.output.absolute()), indent=2, sort_keys=True))
        elif args.command == "build":
            images = build_images(args.wheelhouse.absolute(), args.work.absolute())
            _private_directory(args.images_json.parent)
            _write_new(args.images_json, json.dumps(images, indent=2).encode() + b"\n", 0o600)
            print(json.dumps(images, indent=2))
        else:
            images = json.loads(args.images_json.read_text())
            print(write_profile(images, state=args.state.absolute()))
    except (SetupError, inputs.ImageInputsError, contexts.ImageContextError, OSError) as exc:
        print("HTTP runtime setup failed: " + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
