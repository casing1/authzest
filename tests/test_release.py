from pathlib import Path

import pytest
from scripts.package_release import write_checksum
from scripts.verify_release import expected_tag, read_project_version, verify_release_tag


def test_expected_tag_converts_pep440_prerelease_to_semver() -> None:
    assert expected_tag("0.1.0a1") == "v0.1.0-alpha.1"
    assert expected_tag("1.2.3b2") == "v1.2.3-beta.2"
    assert expected_tag("2.0.0rc3") == "v2.0.0-rc.3"
    assert expected_tag("2.0.0") == "v2.0.0"


def test_verify_release_tag_rejects_a_mismatched_version() -> None:
    with pytest.raises(ValueError, match="does not match"):
        verify_release_tag("v0.1.0", "0.1.0a1")


def test_read_project_version(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nversion = "0.1.0a1"\n', encoding="utf-8")

    assert read_project_version(pyproject) == "0.1.0a1"


def test_write_checksum_uses_a_portable_lf_manifest(tmp_path: Path) -> None:
    artifact = tmp_path / "authzest-windows-x64.exe"
    artifact.write_bytes(b"release artifact")

    checksum = write_checksum(artifact)

    manifest = checksum.read_bytes()
    assert manifest.endswith(b"  authzest-windows-x64.exe\n")
    assert b"\r\n" not in manifest
