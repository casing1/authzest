from __future__ import annotations

import argparse
import re
import tomllib
from pathlib import Path

VERSION_PATTERN = re.compile(
    r"^(?P<base>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:(?P<kind>a|b|rc)(?P<number>0|[1-9]\d*))?$"
)
PRE_RELEASE_NAMES = {"a": "alpha", "b": "beta", "rc": "rc"}


def read_project_version(pyproject: Path) -> str:
    with pyproject.open("rb") as project_file:
        project = tomllib.load(project_file)
    version = project.get("project", {}).get("version")
    if not isinstance(version, str):
        raise ValueError("pyproject.toml must define project.version as a string")
    return version


def expected_tag(version: str) -> str:
    match = VERSION_PATTERN.fullmatch(version)
    if match is None:
        raise ValueError(f"Unsupported release version: {version}")

    tag = f"v{match.group('base')}.{match.group('minor')}.{match.group('patch')}"
    kind = match.group("kind")
    if kind is not None:
        tag += f"-{PRE_RELEASE_NAMES[kind]}.{match.group('number')}"
    return tag


def verify_release_tag(tag: str, version: str) -> None:
    expected = expected_tag(version)
    if tag != expected:
        message = (
            f"Release tag {tag!r} does not match project version {version!r}; use {expected!r}"
        )
        raise ValueError(message)


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify an AuthZest release tag.")
    parser.add_argument("tag", help="Git tag to compare with pyproject.toml")
    parser.add_argument(
        "--pyproject",
        type=Path,
        default=Path("pyproject.toml"),
        help="Path to pyproject.toml",
    )
    arguments = parser.parse_args()

    version = read_project_version(arguments.pyproject)
    try:
        verify_release_tag(arguments.tag, version)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    print(f"Release tag {arguments.tag} matches project version {version}.")


if __name__ == "__main__":
    main()
