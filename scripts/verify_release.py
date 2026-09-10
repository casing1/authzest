from __future__ import annotations

import argparse
import re
import tomllib
from datetime import date
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


def _changelog_lines(text: str) -> list[str]:
    """Inspect changelog prose, not headings copied into comments or code examples."""
    text = re.sub(r"<!--.*?(?:-->|$)", "", text, flags=re.DOTALL)
    lines: list[str] = []
    fence: str | None = None
    for line in text.splitlines():
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        if fence is not None:
            if (
                marker is not None
                and marker[1][0] == fence[0]
                and len(marker[1]) >= len(fence)
                and not marker[2].strip()
            ):
                fence = None
            continue
        if marker is not None:
            fence = marker[1]
        elif not line.startswith(("    ", "\t")):
            lines.append(line)
    return lines


def read_changelog_release_date(changelog: Path, tag: str) -> date:
    """Require one dated release section with prose or entries; never interpret its text."""
    label = tag.removeprefix("v")
    lines = _changelog_lines(changelog.read_text(encoding="utf-8"))
    heading = re.compile(rf"^ {{0,3}}##[ \t]+\[{re.escape(label)}\](.*)$")
    matches = [
        (index, match[1]) for index, line in enumerate(lines) if (match := heading.match(line))
    ]
    if len(matches) != 1:
        raise ValueError(f"{changelog} must contain exactly one release heading for [{label}]")
    start, suffix = matches[0]
    dated = re.fullmatch(r"[ \t]+-[ \t]+(\d{4}-\d{2}-\d{2})[ \t]*", suffix)
    if dated is None:
        raise ValueError(f"{changelog}: [{label}] must use a YYYY-MM-DD release date")
    try:
        release_date = date.fromisoformat(dated[1])
    except ValueError as exc:
        raise ValueError(f"{changelog}: [{label}] has an invalid release date: {dated[1]}") from exc
    entries = []
    for line in lines[start + 1 :]:
        if re.match(r"^ {0,3}#{1,2}(?:[ \t]+|$)", line):
            break
        if re.match(r"^ {0,3}#{1,6}(?:[ \t]+|$)", line) or re.match(r"^ {0,3}\[[^\]]+\]:", line):
            continue
        if line.strip(" -*+_=#>\t"):
            entries.append(line)
    if not entries:
        raise ValueError(f"{changelog}: [{label}] release section must not be empty")
    return release_date


def verify_release_changelogs(tag: str, changelog: Path, changelog_ko: Path) -> date:
    english_date = read_changelog_release_date(changelog, tag)
    korean_date = read_changelog_release_date(changelog_ko, tag)
    if english_date != korean_date:
        raise ValueError(
            f"Release [{tag.removeprefix('v')}] dates differ between {changelog} "
            f"({english_date}) and {changelog_ko} ({korean_date})"
        )
    return english_date


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify an AuthZest tag and bilingual release notes."
    )
    parser.add_argument("tag", help="Git tag to compare with pyproject.toml")
    parser.add_argument(
        "--pyproject",
        type=Path,
        default=Path("pyproject.toml"),
        help="Path to pyproject.toml",
    )
    parser.add_argument(
        "--changelog", type=Path, default=Path("CHANGELOG.md"), help="Path to the English changelog"
    )
    parser.add_argument(
        "--changelog-ko",
        type=Path,
        default=Path("docs/i18n/ko/CHANGELOG.md"),
        help="Path to the Korean changelog",
    )
    arguments = parser.parse_args()

    try:
        version = read_project_version(arguments.pyproject)
        verify_release_tag(arguments.tag, version)
        release_date = verify_release_changelogs(
            arguments.tag, arguments.changelog, arguments.changelog_ko
        )
    except (OSError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    print(
        f"Release tag {arguments.tag} matches project version {version} "
        f"and both dated changelogs ({release_date})."
    )


if __name__ == "__main__":
    main()
