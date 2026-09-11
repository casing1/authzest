<p align="center">
  <strong>English</strong> ·
  <a href="../i18n/ko/reference/PROPOSAL_CONTRACT.md">한국어</a>
</p>

# Offline proposal and decision contract

[Documentation index](../README.md) · [AI input/review contract](AI_CONTRACT.md)

## Implemented scope

#46 implements the first offline slice of #35, after #33. Proposal and decision schemas are `1.0`,
independent of report schema `1.2` and package version `0.1.0a2`. These source-checkout modules are not
part of the alpha.2 binaries. There is no new product CLI/API command or changed scan behavior.

The library packages explicit caller-authored replacement text and validates a proposal/decision.
It does not call Codex, synthesize code, write a draft workspace, apply a patch, execute tests, or
recover files. #35 remains open for the complete, separately approved integration stages.

The separate [#48 fixture-copy service](../guides/FIXTURE_APPLICATION.md) now demonstrates actual
approved application/restoration in a fresh POSIX copy only. This contract module remains pure; neither
it nor that bounded copy demo provides arbitrary-checkout writes, live AI or verification execution.
The separate [#50 Codex fixture command](../guides/CODEX_FIXTURE.md) supplies a narrowly validated model
draft to these host-bound contracts; live validation is pending. It does not change these pure functions
into a provider client or verification executor, and is not a general repository patch workflow.

## Proposal contents and preview

`prepare_proposal` takes a #33 request, its validated review, selected existing-file replacements,
rationale, explicit uncertainties, side effects, check identifiers, and expected outcomes.
`validate_proposal` revalidates the input/review and rejects mismatched schema/request/review identity,
missing source citations, malformed/extra fields, duplicate targets, and unchanged replacements.

- Each change records a relative path, original UTF-8 SHA-256, proposed exact text, and evidence IDs.
  A source citation for that file is mandatory. Existing IDs alone do not prove semantic support.
- This slice allows at most eight changed, already-selected Python files with nonblank text of at most
  32,768 characters each. Paths use ASCII letters/digits, underscores, dots, hyphens, and separators.
  Absolute/traversing/ambiguous paths, hidden components, reserved folders, and case-colliding selected
  paths are rejected. New files, deletion, renames, permissions, binary edits and non-Python targets are
  deliberately unsupported. JSON limits from the AI contract still apply.
- `proposal_id` binds all proposal content, including the request, validated review, original hashes,
  replacements, rationale, uncertainty, side effects, and verification plan. Changing any of these needs
  a new decision, even when the diff happens to look the same.
- `proposal_preview` derives unified diffs from the bound snapshots and replacement text; a separate
  provider-supplied diff field is rejected. UTF-8 content hashes do not normalize line endings. Diffs
  use LF-delimited lines, preserve CRLF data and show missing final-newline markers. The returned data
  includes exact before/after hashes, rationale and plan. Clients must safely display untrusted text.

Checks are non-executable identifiers: `fixture-static-inventory` and `fixture-regression-tests`.
They describe future verification intent, not existing executors or a command allowlist that grants
execution. The contract accepts no shell command, executable, argument, environment or install-hook fields.
Expectations and prose remain untrusted data. A future implementation must resolve checks through a
reviewed fixed implementation and obtain separate execution approval.

## Decisions and current-state checks

`record_decision` records the caller's explicit `approve`, `decline`, or `cancel` choice for the exact
proposal ID and purpose `patch-application`. It does not authenticate a human or infer consent from a
model's text. Callers supply finite timestamps from the same clock; expiry defaults to 300 seconds and
must be positive and no longer than one hour.

`assess_decision` revalidates the artifacts and compares the decision with the current proposal, time,
all selected source texts (not just edited files), and a source revision when the request supplied one.
Additional unselected content is ignored and never changed.

| Reason                   | Eligible | Meaning                                          |
| ------------------------ | -------- | ------------------------------------------------ |
| `pending`                | false    | No explicit decision                             |
| `declined` / `cancelled` | false    | Explicit refusal/cancellation                    |
| `stale-proposal`         | false    | Decision refers to a different proposal          |
| `clock-before-decision`  | false    | Current time predates the decision               |
| `expired`                | false    | Current time reaches or exceeds expiry           |
| `stale-source`           | false    | Selected text/revision is changed or unavailable |
| `approved`               | true     | Supplied state satisfies this offline check      |

Invalid schemas/inputs raise `ContractError` instead of producing eligibility. Every assessment still
has `applied: false` and `verification_status: not-run`. Eligibility is not a verified fix and does not
grant source sharing or verification execution.

This is an in-memory contract, **not a signed, one-use, replay-proof authorization system**. Calling the
checker twice with identical input returns the same result. The future application service must use the
latest non-revoked decision, consume it, read actual regular files without following links, recheck roots
and content, handle filesystem races atomically, preserve user edits and reject conflicts. Supplied
snapshots and lexical path validation do not establish symlink safety or current disk/Git state. Do not
connect this checker directly to an unrestricted patch or shell executor.

## Owned offline demonstration

After editable development setup, from the repository root:

```bash
python scripts/demo_proposal.py
python scripts/demo_proposal.py --decision approve
python scripts/demo_proposal.py --decision cancel
python scripts/demo_proposal.py --decision approve --scenario stale-source
python scripts/demo_proposal.py --decision approve --scenario expired
python -m pytest tests/test_proposal_contract.py tests/test_proposal_approval.py
```

The demo defaults to decline. It reads only `tests/fixtures/proposal_demo/main.py`, inventories it without
importing it, and packages a fixed caller-authored `debug=True` → `debug=False` configuration draft.
This is not an AI-discovered vulnerability, authorization test, or runtime security guarantee. It uses
a scripted review, simulated decisions and relative example times; the approved scenario also leaves
the fixture unchanged and tests unrun. JSON escapes control/non-ASCII characters for safe terminal display.

Tests cover exact/multifile diffs, newline handling, source/review/plan changes, unsafe targets, refusal,
cancellation, expiry, missing source, malformed records and explicit no-network/no-write behavior.
The fixture-specific application and provider slices have separate scope guides; the complete provider,
verification failure and recovery acceptance gate remains later #35 work.
