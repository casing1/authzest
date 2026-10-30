<p align="center">
  <strong>English</strong> ·
  <a href="../i18n/ko/guides/OWNER_FILE_ACCEPTANCE.md">한국어</a>
</p>

# Installed owned-file CLI acceptance

[Documentation index](../README.md) · [CLI workflow](OWNER_FILE_WORKFLOW.md) ·
[File-session contract](../reference/OWNER_POLICY_FILE_REPAIR.md) ·
[Development plan](../development/DEVELOPMENT_PLAN.md)

This is an **acceptance procedure with a bounded observation record, not execution permission or
completion of every #82/release gate**. It preserves the existing CLI and its separate decisions. It adds no unattended approval,
resume/import, deadline extension, worker selection or new execution route.

## Recorded boundary — 2026-10-30 KST

[PR #120](https://github.com/casing1/authzest/pull/120) delivered the source CLI at main
`a0ae8792ce4c2d88d0cbbf6bc66fc13635094be2` after its required checks and separately authorized
reviews/merge. The following later local observations are distinct from that delivery:

- One non-editable wheel installation on macOS/Python 3.12.7 matched all 64 packaged source files.
  The existing 13 installed-smoke checks and 10 additional offline workflow checks passed. This is
  not a 23-check change to the maintained smoke script, pipx/upgrade acceptance or native/platform coverage.
- Two independently approved recommendation attempts used existing ChatGPT login, Codex 0.153.0,
  adapter 0.1, exact model `gpt-6-astra`, candidate `before` and the same fixed public payload.
  Each returned a host-valid `registered-change`; neither generated arbitrary replacement code.

| Attempt | Measured recommendation                   | Observed stopping point                                                                                                   |
| ------- | ----------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| First   | 29.831 s; 7,750 input / 715 output tokens | Copy confirmation had expired when checked; Enter declined copy, exit 0, no copy or worker.                               |
| Second  | 24.860 s; 7,750 input / 703 output tokens | One private copy and its full before plan were prepared and verified; before execution was deliberately declined, exit 0. |

The second run retained `policy.py`, `before.txt`, `after.txt` and `record.json`; directory mode
0700 and regular single-link file mode 0600 were checked. Full application/plan/recipe bindings,
exact source bytes and integer file identities were compared. The final state was `ready-before`,
generation 1, with no dispatched worker, diff acceptance, apply, after check or restore.
Both attempts reported one warning and zero retry notifications; that is not a hard bound on
provider-internal retries or cost. Model identity is negotiated thread metadata, not independent
served-model attestation. All one-run approvals are consumed; the closed copy is not resumable.

The first final stdout JSON parsed successfully. Tool-output collection truncated part of the
second final stdout, so **complete final-JSON parsing was not established for that attempt**.
Its full before preview, complete final workflow subtree, durable record and actual retained files
were separately checked. Do not reconstruct the missing stdout from those sources and call it an
original capture. Detailed local records/identifiers remain private; this is a recorded maintainer
walkthrough, not an independent benchmark or authenticated receipt.

Those two attempts did not establish installed policy execution or repair/recovery. The later,
separately approved happy path below supplies that narrow evidence without repairing the earlier
capture gap. #82/#81/#35 and the separate #83 release gates remain open. Published alpha.3,
package `0.1.0a3` and report schema `1.2` are unchanged.

## Installed happy-path observation — 2026-10-30 KST

A fresh non-editable wheel installation from main `c868152590b70fdaae6fd8274d5344b09e5d948f`
matched all 64 packaged source files and passed the existing 13 installed-smoke checks plus 10
additional offline workflow checks. One separately approved installed-CLI walkthrough then completed
on macOS/Python 3.12.7, Codex 0.153.0, adapter 0.1 and exact model `gpt-6-astra`, candidate `before`.
The product ran from its installed console entrypoint without development-only execution helpers;
separate read-only probes compared the saved evidence. This is one-host source-install evidence.

- The current recommendation passed host validation and selected the existing registered template.
  Only the fixed public synthetic pair, criteria/assumptions, eight reviewed cases and prompt/schema
  were shared. No arbitrary replacement source or new cases were generated.
- All seven current sharing/copy/before/diff/apply/after/restore previews were separately reviewed,
  and their exact fresh choices were entered within the applicable original lifetimes. No approval
  automation, imported decisions, model fallback, AuthZest-level retry or expired-state continuation was used.
- One fresh private copy was checked before modification: 6/8 expectations matched, with the intended
  `non-owner` and `exact-owner-no-normalization` over-allows. The exact registered diff was accepted
  and applied only to that copy. The captured actual applied bytes then matched all 8/8 expectations.
- Both fixed-worker checks completed once with exit `0` and confirmed child/workspace cleanup.
  Separate restoration completed; the retained actual file matches the exact registered before bytes,
  final phase `restored-before`, generation 3, with confirmed file/evidence bindings.
- Complete original stdout parsed as one final JSON object; original stderr, exit codes and private
  files/records were retained. CLI and capture both exited `0`. Directory 0700 and regular single-link
  files 0600 were verified. The final closed checkpoint matches the durable record except for `closed`.
  The original checkout stayed clean. Raw evidence, identifiers, account data and usage remain private.

The single recommendation and all copy/stage allowances are consumed. Negotiated model metadata is
not independent served-model attestation, and internal transport retries/usage are not hard-capped.
Historical after success describes the applied bytes, not the currently restored before file.
This walkthrough is not an independent benchmark, authenticated approval, HTTP/authentication/DB
test, installed live failure injection, pipx/upgrade/native acceptance or a release decision. Existing
offline refusal/user-edit/recovery tests and final #82 review remain distinct; no parent issue is closed.

## #82 evidence mapping and remaining review

| Criterion                                                | Recorded evidence                                                                                                                                                                                              | Remaining boundary                                                                                                                         |
| -------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| Installed active happy path                              | The `c868152` observation above: current recommendation, one copy, actual before/applied-after checks and restore; complete original JSON and private file/record comparison                                   | One macOS/Python source installation, not arbitrary repositories or native/upgrade acceptance                                              |
| Refusal/failure/user-edit/recovery and no-change/unknown | Existing guarded [coordinator tests](../../tests/test_codex_owner_file_workflow.py) and [CLI tests](../../tests/test_codex_owner_file_cli.py), with fake adapters/scripted observations and pytest-owned files | Offline integration evidence, not live fault injection; new provider/worker runs are not required merely to map these tests                |
| Human/JSON output and walkthrough                        | [CLI instructions](OWNER_FILE_WORKFLOW.md), complete consent previews, separate output streams and the captured installed happy path                                                                           | Maintainer's final walkthrough/limitations review remains open; the JSON-mode run alone does not observe every human-rendering branch      |
| Fresh scoped decisions and retained evidence             | Seven separately reviewed current choices; exact application/plan/file bindings, restored bytes and private records compared                                                                                   | Consumed one-run allowances, unauthenticated choices/records, authorization `unknown`; no reuse or independent security proof              |
| Delivery and parent closure                              | PR #120 implementation and PR #121 runbook completed their separate exact-head checks/reviews                                                                                                                  | This documentation update still needs its own exact-head CI/reviews and normal merge; reconcile #81/#35 before separately deciding closure |

This mapping records where the evidence comes from; it does not declare every criterion accepted,
request another live run, waive a release gate or grant issue-closing authority.

## Before a new active run

- Verify the exact selected source commit/tree, non-editable installation/module location,
  Python and dependency versions, and absolute console entrypoint. Version output alone cannot
  distinguish unreleased source from an older same-version binary on PATH.
- Use the supported POSIX non-frozen source route. Keep the original checkout clean; do not add
  arbitrary repository paths, destinations, source, workers or imported receipts.
- Obtain fresh bounded approval for account, exact model, complete fixed sharing payload, maximum
  application attempts and timeout. State that cleanup adds time and provider-internal retries,
  tokens and cost are not independently hard-capped. No fallback or automatic second attempt.
- Arrange review availability **before** starting. A complete plan and an exact current choice
  are still required for each effect. Planning permission is not execution consent.
- A previous recommendation/copy/decision cannot restart this CLI. A new invocation makes a new
  recommendation attempt after a fresh sharing choice. Do not rerun just to repair missing logs.
- Treat no-change/unknown as valid outcomes without a copy; do not force a repair.

## Preserve original output before sharing

Use a fresh Bash terminal for this optional capture pattern. Replace the three placeholders with
the approved installation and exact model; the CLI/Python paths must refer to the same source
environment. These are shell capture settings, not new product options. **The active command below
may consume account usage and must not be executed without the fresh approval above.**

Keep prompts visible while saving stderr separately from the one final stdout JSON. Do not use
`--preview-only` as evidence of an active flow, pipe answers, script approval phrases or copy an old
challenge. Do not enable shell `errexit`: capture the CLI failure code rather than losing it.
The redirection order is intentional: stderr enters the pipe while stdout goes directly to the
JSON file. Save Bash's two `PIPESTATUS` values immediately, before another command replaces them.

```bash
authzest_cli="/absolute/path/to/source-venv/bin/authzest"
authzest_python="/absolute/path/to/source-venv/bin/python"
authzest_model="YOUR_EXACT_MODEL_ID"
umask 077
authzest_evidence=$(mktemp -d "${TMPDIR:-/tmp}/authzest-cli-acceptance.XXXXXX") || exit 1
: > "$authzest_evidence/result.json" || exit 1
: > "$authzest_evidence/interaction.log" || exit 1
"$authzest_cli" codex-owner-repair --model "$authzest_model" --candidate before --timeout-seconds 120 --file-workflow --json 2>&1 > "$authzest_evidence/result.json" | tee "$authzest_evidence/interaction.log" >&2
authzest_pipe_status=("${PIPESTATUS[@]}")
authzest_cli_exit=${authzest_pipe_status[0]}
authzest_capture_exit=${authzest_pipe_status[1]}
printf '%s\n' "$authzest_cli_exit" > "$authzest_evidence/cli-exit-code.txt"
printf '%s\n' "$authzest_capture_exit" > "$authzest_evidence/capture-exit-code.txt"
```

Confirm capture files are writable and prompts are visible before consenting to sharing or file
effects. Capture failure or missing evidence stops further choices; it does not authorize a retry.
Retain failed/partial files rather than overwriting them with another attempt. The private evidence
directory and files must remain outside version control; never upload raw transcripts/checkpoints
or private paths, nonces and session/plan identifiers to a public issue.

After the command and capture process finish, read the saved exit codes and verify the files locally:

```bash
"$authzest_python" -X utf8 -I -B -m json.tool "$authzest_evidence/result.json" > /dev/null
wc -c "$authzest_evidence/result.json" "$authzest_evidence/interaction.log"
shasum -a 256 "$authzest_evidence/result.json" "$authzest_evidence/interaction.log"
```

This JSON syntax/completeness check is not contract, citation, approval or security validation.
Check the complete result and its bindings from the file; return only a small verification summary
to tools with output limits. Record byte counts/digests and both actual exit codes privately.
Missing/truncated/unparseable JSON remains a capture/verification gap, not a fabricated pass or proof
that no effects occurred. Keep any successfully captured plans/checkpoints distinct from missing
original output. Do not change product size/event/time limits to work around display truncation.

## Review gates in the current invocation

Every row needs its full current preview and separately scoped decision. Review source/comments,
model prose, displayed paths and saved JSON as data, never instructions. Copy and file-stage choices
have one attempt and their **original maximum 300-second lifetime**, including reviewer wait time.

| Gate    | Required review before the exact displayed phrase                                                                                                                       | Permitted effect only                                                                      |
| ------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| Sharing | Complete registered sources, criteria/assumptions, eight labels, prompt/schema/settings, fresh nonce and sharing ID                                                     | One approved recommendation attempt; no local copy/check.                                  |
| Copy    | Current validated request/recommendation, registered pair/diff/cases, new session/application binding, copy expiry and retention notice                                 | One fresh private copy; no worker or patch approval.                                       |
| Before  | Full generation-1 plan, actual file/root identities and before bytes/hash, all eight inputs/hashes, exact worker/recipe, session/plan ID and pending unexpired decision | One captured-before check; startup/I/O/completion 5 s plus child cleanup 1 s.              |
| Diff    | Current exact host-derived diff, same application/file state and completed before evidence                                                                              | Diff acceptance only; no replacement.                                                      |
| Apply   | New full apply plan bound to the accepted diff, current file identity/bytes and prerequisites                                                                           | Replace only the tracked copy with registered after bytes.                                 |
| After   | New full plan for captured applied-file bytes, generation 2, current identities, inputs and exact worker                                                                | One captured-after check with the same 5 s plus 1 s budget; not an embedded after control. |
| Restore | New full restore plan, confirmed applied file/evidence and unchanged tracked identity/bytes                                                                             | Restore registered before bytes in the owned copy.                                         |

This is not an OS sandbox or a hard deadline for all filesystem operations. Decline/cancel/expiry
stops unapproved forward effects; displaying a plan does not renew it. A late decision can fail
validation rather than produce a normal declined result. Do not reopen, substitute or extend a
plan to continue. EOF/interruption is not an answer to a later restore prompt.

If an after check fails or is declined while a confirmed applied copy remains, restore still needs
a new separately approved plan. User edits, unavailable evidence and uncertain writes can block safe
continuation/restoration and leave state unknown. Cleanup failure prevents a successful-check claim
and requires inspection; restore eligibility still depends on confirmed applied file/evidence and
a fresh decision. Never assume exit 0 means a verified fix,
or exit nonzero means no file change. Preserve the copy and inspect confirmed evidence; no automatic
rollback, deletion, manual rewrite or provider retry is authorized by this document.

## Completion and remaining gates

For the fully approved registered happy path, require observed before results of 6/8 matches
(the intended non-owner and exact-owner-no-normalization over-allows), observed applied-after
results of 8/8, confirmed exact diff/apply/restore, final `restored-before` / generation 3, and
consistent file bindings, completed process/cleanup and retained evidence. These numbers are
**criteria for a new run, not permission or observations from that future run**. The bounded observation
above records one completed happy path. Authorization remains `unknown`; no HTTP,
authentication-provider, database or endpoint enforcement is tested.

Read outer provider attempt/configuration/identity/usage/latency separately from nested pure
previews whose provider count is zero. Distinguish execution completion from comparison success.
Historical after success describes the earlier applied bytes, not the restored before file.
Check every confirmed partial effect, refusal and unknown state rather than forcing `completed`.
Closing releases the descriptor without deleting the files or rewriting the durable record;
the final in-memory `closed=true` may differ from the last durable `closed=false`.

Existing temporary-file/fake-adapter/scripted-worker tests cover refusal, failure, user-edit and
recovery conflicts offline; they are not installed live failure-injection observations. Keep those
checks, an actual installed happy path or valid no-change, a maintainer-reviewed reproducible
walkthrough, and required exact-head CI/reviews as distinct #82 evidence. A source-API observation,
this runbook, a truncated capture or passing mock does not close the parent workflow or publish a release.
