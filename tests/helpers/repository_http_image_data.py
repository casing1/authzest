"""Owned synthetic image metadata and inert ZIPs, never a real image acceptance."""

from __future__ import annotations

import copy
import json
import shutil
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from scripts import generated_image_inputs as shared
from scripts import repository_http_image_inputs as inputs

from test_generated_image_inputs import manifest_data, wheel_bytes, write_inputs

REPOSITORY = Path(__file__).resolve().parents[2]


@dataclass
class HTTPImageFixture:
    repo: Path
    wheelhouse: Path
    parent: Path
    data: dict
    base: dict


def write_http_inputs(repo: Path, base: dict, monkeypatch) -> dict:
    """Rebuild synthetic HTTP declarations; patch test-local expected pins only."""
    digest = sha256((repo / inputs.BASE_REFERENCE).read_bytes()).hexdigest()
    monkeypatch.setattr(inputs, "BASE_REFERENCE_SHA256", digest)
    data = {
        "schema_version": "2.0",
        "kind": "repository-http-image-inputs",
        "status": "declared-not-built",
        "base_reference": inputs.BASE_REFERENCE,
        "base_reference_sha256": digest,
        "roles": {},
        "image_ids": None,
        "contents_verified": False,
        "runtime_ready": False,
    }
    pins = {}
    for role in inputs.ROLES:
        sources = copy.deepcopy(inputs._ASSET_PATHS[role])
        for relative in sources.values():
            target = repo / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(REPOSITORY / relative, target)
        item = {"asset_sources": sources, "assets": inputs.expected_assets(role), "platforms": {}}
        data["roles"][role] = item
        old = base["roles"][role]["platforms"]["linux/arm64"]
        recipe = {
            "schema_version": "2.0",
            "kind": "repository-http-image-recipe",
            "role": role,
            "platform": "linux/arm64",
            "base_manifest_sha256": base["base"]["platforms"]["linux/arm64"]["manifest_sha256"],
            "dependency_lock_path": shared.IMAGES + "/" + old["requirements_file"],
            "dependency_lock_sha256": old["requirements_sha256"],
            "dockerfile": "Dockerfile.linux-arm64-" + role,
            "dockerfile_sha256": "0" * 64,
            "assets": copy.deepcopy(item["assets"]),
            "recipe_sha256": "0" * 64,
        }
        item["platforms"]["linux/arm64"] = recipe
        raw = inputs._dockerfile(data, base, role, "linux/arm64")
        recipe["dockerfile_sha256"] = sha256(raw).hexdigest()
        recipe["recipe_sha256"] = inputs._recipe(recipe)
        target = repo / inputs.IMAGES / recipe["dockerfile"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        pins[role] = {key: recipe[key] for key in ("dependency_lock_sha256", "recipe_sha256")}

    def expected_recipe_pins(platform, role):
        inputs._role_platform(role, platform)
        return dict(pins[role])

    monkeypatch.setattr(inputs, "expected_recipe_pins", expected_recipe_pins)
    (repo / inputs.IMAGES / "manifest.json").write_text(json.dumps(data), encoding="utf-8")
    return data


def make_http_fixture(tmp_path, monkeypatch, role="A", *, base_data=None, wheel_payloads=None):
    """Write one owned synthetic source tree and an exact selected wheel set."""
    tmp_path = Path(tmp_path).resolve()
    tmp_path.mkdir(parents=True, exist_ok=True)
    repo, wheels, parent = (tmp_path / name for name in ("repo", "wheels", "output"))
    for path in (repo, wheels, parent):
        path.mkdir(mode=0o700)
    base = copy.deepcopy(manifest_data() if base_data is None else base_data)
    payloads = {}
    for name, package in base["packages"].items():
        wheel = package["wheels"]["linux/arm64"]
        raw = (
            (wheel_payloads or {}).get(name)
            if name in (wheel_payloads or {})
            else wheel_bytes(name, package["version"], tuple(wheel["requires_dist"]))
        )
        payloads[name] = raw
        for declaration in package["wheels"].values():
            declaration.update(size=len(raw), sha256=sha256(raw).hexdigest())
    base = write_inputs(repo, base)
    data = write_http_inputs(repo, base, monkeypatch)
    for name in base["roles"][role]["platforms"]["linux/arm64"]["packages"]:
        wheel = base["packages"][name]["wheels"]["linux/arm64"]
        (wheels / wheel["filename"]).write_bytes(payloads[name])
    return HTTPImageFixture(repo, wheels, parent, data, base)
