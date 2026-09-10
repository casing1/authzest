from datetime import date
from pathlib import Path

import pytest
from scripts.package_release import write_checksum
from scripts.verify_release import (
    expected_tag,
    main,
    read_changelog_release_date,
    read_project_version,
    verify_release_changelogs,
    verify_release_tag,
)


def test_expected_tag_converts_pep440_prerelease_to_semver() -> None:
    assert expected_tag("0.1.0a1") == "v0.1.0-alpha.1"
    assert expected_tag("0.1.0a2") == "v0.1.0-alpha.2"
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


TAG = "v0.1.0-alpha.2"
HEADING = "## [0.1.0-alpha.2] - 2026-09-10"


def write_changelog(path: Path, body: str, heading: str = HEADING) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# Changelog\n\n## [Unreleased]\n\n"
        f"{heading}\n\n{body}\n\n"
        "## [0.1.0-alpha.1] - 2026-09-04\n\n- Previous release content.\n",
        encoding="utf-8",
    )
    return path


def test_matching_bilingual_release_sections_keep_valid_dates(tmp_path: Path) -> None:
    english = write_changelog(tmp_path / "CHANGELOG.md", "### Added\n\n- Source reports.")
    korean = write_changelog(
        tmp_path / "docs" / "i18n" / "ko" / "CHANGELOG.md", "### 추가\n\n- 소스 리포트."
    )

    assert verify_release_changelogs(TAG, english, korean) == date(2026, 9, 10)


@pytest.mark.parametrize("missing_language", ["english", "korean"])
def test_both_changelogs_must_have_the_requested_release_heading(
    tmp_path: Path, missing_language: str
) -> None:
    english = write_changelog(tmp_path / "CHANGELOG.md", "- Current release.")
    korean = write_changelog(tmp_path / "CHANGELOG.ko.md", "- 현재 릴리스.")
    missing = english if missing_language == "english" else korean
    missing.write_text("## [Unreleased]\n\n- These notes are not a release.\n", encoding="utf-8")

    with pytest.raises(ValueError, match="exactly one release heading"):
        verify_release_changelogs(TAG, english, korean)


def test_duplicate_release_headings_are_not_accepted(tmp_path: Path) -> None:
    path = write_changelog(tmp_path / "CHANGELOG.md", f"- One section.\n\n{HEADING}\n\n- Two.")

    with pytest.raises(ValueError, match="exactly one release heading"):
        read_changelog_release_date(path, TAG)


@pytest.mark.parametrize(
    "heading",
    [
        "## [0.1.0-alpha.2]",
        "## [0.1.0-alpha.2] - soon",
        "## [0.1.0-alpha.2] - 2026-9-10",
        "## [0.1.0-alpha.2] - 2026-02-30",
        "## [0.1.0-alpha.2] - 2026-13-01",
    ],
)
def test_release_dates_must_have_iso_shape_and_be_calendar_dates(
    tmp_path: Path, heading: str
) -> None:
    path = write_changelog(tmp_path / "CHANGELOG.md", "- A release entry.", heading)

    with pytest.raises(ValueError, match="release date"):
        read_changelog_release_date(path, TAG)


def test_bilingual_release_dates_must_match(tmp_path: Path) -> None:
    english = write_changelog(tmp_path / "CHANGELOG.md", "- Source reports.")
    korean = write_changelog(
        tmp_path / "CHANGELOG.ko.md", "- 소스 리포트.", HEADING.replace("09-10", "09-11")
    )

    with pytest.raises(ValueError, match="dates differ"):
        verify_release_changelogs(TAG, english, korean)


@pytest.mark.parametrize(
    "body",
    [
        "",
        "### Added\n\n### Fixed",
        "<!-- Release entries will go here. -->",
        "[0.1.0-alpha.2]: https://example.invalid/release\n\n---",
        "```md\n### Added\n- Only a code example.\n```",
    ],
)
def test_section_without_entries_cannot_borrow_content_from_an_older_release(
    tmp_path: Path, body: str
) -> None:
    path = write_changelog(tmp_path / "CHANGELOG.md", body)

    with pytest.raises(ValueError, match="must not be empty"):
        read_changelog_release_date(path, TAG)


@pytest.mark.parametrize("empty_language", ["english", "korean"])
def test_both_languages_need_nonempty_release_entries(tmp_path: Path, empty_language: str) -> None:
    english = write_changelog(
        tmp_path / "CHANGELOG.md", "" if empty_language == "english" else "- Source reports."
    )
    korean = write_changelog(
        tmp_path / "CHANGELOG.ko.md", "" if empty_language == "korean" else "- 소스 리포트."
    )

    with pytest.raises(ValueError, match="must not be empty"):
        verify_release_changelogs(TAG, english, korean)


@pytest.mark.parametrize("wrapper", ["```md\n{}\n```", "~~~md\n{}\n~~~", "<!--\n{}\n-->"])
def test_release_headings_in_examples_or_comments_do_not_count(
    tmp_path: Path, wrapper: str
) -> None:
    path = tmp_path / "CHANGELOG.md"
    path.write_text(wrapper.format(f"{HEADING}\n\n- Not an actual section."), encoding="utf-8")

    with pytest.raises(ValueError, match="exactly one release heading"):
        read_changelog_release_date(path, TAG)


def test_release_text_is_data_not_python_to_evaluate(tmp_path: Path) -> None:
    marker = tmp_path / "must-not-be-created"
    body = f"- __import__('pathlib').Path({str(marker)!r}).touch()"
    path = write_changelog(tmp_path / "CHANGELOG.md", body)

    assert read_changelog_release_date(path, TAG) == date(2026, 9, 10)
    assert not marker.exists()


def test_release_verifier_defaults_use_the_language_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "0.1.0a2"\n', encoding="utf-8")
    write_changelog(tmp_path / "CHANGELOG.md", "- Source reports.")
    write_changelog(tmp_path / "docs" / "i18n" / "ko" / "CHANGELOG.md", "- 소스 리포트.")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["verify_release.py", TAG])

    main()

    assert "matches project version 0.1.0a2" in capsys.readouterr().out


def test_release_verifier_checks_tag_before_trying_to_read_changelogs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "0.1.0a2"\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["verify_release.py", "v0.1.0-alpha.1"])

    with pytest.raises(SystemExit, match="does not match project version"):
        main()


def test_release_verifier_accepts_explicit_changelog_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    pyproject = tmp_path / "candidate.toml"
    pyproject.write_text('[project]\nversion = "0.1.0a2"\n', encoding="utf-8")
    english = write_changelog(tmp_path / "release-en.md", "- Source reports.")
    korean = write_changelog(tmp_path / "release-ko.md", "- 소스 리포트.")
    monkeypatch.setattr(
        "sys.argv",
        [
            "verify_release.py",
            TAG,
            "--pyproject",
            str(pyproject),
            "--changelog",
            str(english),
            "--changelog-ko",
            str(korean),
        ],
    )

    main()

    assert "both dated changelogs (2026-09-10)" in capsys.readouterr().out
