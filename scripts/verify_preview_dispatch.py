"""Check an explicitly selected main commit before nonpublishing native preview checks."""

from __future__ import annotations

import os
import re
import subprocess

SHA_PATTERN = re.compile(r"[0-9a-f]{40}")


def verify_requested_run(event_name: str, ref: str, expected_sha: str, run_sha: str) -> None:
    if event_name != "workflow_dispatch":
        raise ValueError("Native preview checks require workflow_dispatch.")
    if ref != "refs/heads/main":
        raise ValueError("Native preview checks require the main branch, not a tag or other ref.")
    for name, value in (("expected_sha", expected_sha), ("run SHA", run_sha)):
        if SHA_PATTERN.fullmatch(value) is None:
            raise ValueError(
                f"Native preview {name} must be exactly 40 lowercase hexadecimal digits."
            )
    if expected_sha != run_sha:
        raise ValueError("Native preview expected_sha does not match this workflow run's SHA.")


def verify_dispatch(
    event_name: str, ref: str, expected_sha: str, run_sha: str, checkout_sha: str
) -> None:
    verify_requested_run(event_name, ref, expected_sha, run_sha)
    if SHA_PATTERN.fullmatch(checkout_sha) is None:
        raise ValueError(
            "Native preview checkout SHA must be exactly 40 lowercase hexadecimal digits."
        )
    if checkout_sha != expected_sha:
        raise ValueError("Native preview checkout HEAD does not match the requested workflow SHA.")


def read_checkout_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD"],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        encoding="ascii",
        errors="strict",
        timeout=10,
        check=True,
    )
    if result.stderr:
        raise ValueError("Native preview could not read a clean checkout HEAD response.")
    return result.stdout.removesuffix("\n")


def main() -> None:
    event_name = os.environ.get("GITHUB_EVENT_NAME", "")
    ref = os.environ.get("GITHUB_REF", "")
    expected_sha = os.environ.get("AUTHZEST_PREVIEW_EXPECTED_SHA", "")
    run_sha = os.environ.get("GITHUB_SHA", "")
    try:
        # Reject a wrong event/ref or stale selection before starting even the read-only Git query.
        verify_requested_run(event_name, ref, expected_sha, run_sha)
        verify_dispatch(event_name, ref, expected_sha, run_sha, read_checkout_sha())
    except (OSError, UnicodeError, ValueError, subprocess.SubprocessError) as exc:
        raise SystemExit(f"Native preview dispatch refused: {exc}") from exc
    print(f"Native preview dispatch verified for main commit {expected_sha}.")
    print(
        "Nonpublishing scan/preview checks only; this is not release or policy-execution approval."
    )


if __name__ == "__main__":
    main()
