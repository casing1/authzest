<p align="center">
  <strong>English</strong> ·
  <a href="../i18n/ko/guides/OWNER_FILE_WORKFLOW.md">한국어</a>
</p>

# Opt-in owned-file CLI workflow

[Documentation index](../README.md) · [Recommendation and sharing](../reference/OWNER_POLICY_REPAIR_RECOMMENDATION.md) ·
[File-session API and prior observations](../reference/OWNER_POLICY_FILE_REPAIR.md) ·
[Development plan](../development/DEVELOPMENT_PLAN.md) ·
[Installed-flow acceptance runbook](OWNER_FILE_ACCEPTANCE.md)

## Availability and scope

This unreleased #82 source implementation connects `codex-owner-repair --file-workflow` to the
existing file-session API. [PR #120](https://github.com/casing1/authzest/pull/120) completed its
required final-head reviews and source delivery at `a0ae879`. Without the flag, the command remains
recommendation-only: no copy, policy execution, application or restoration. Published alpha.3 and package version `0.1.0a3` are
unchanged. The optional web dashboard does not display or control this workflow.

The active file path requires **POSIX non-frozen Python source mode** and the supported
descriptor-relative filesystem primitives. It rejects unsupported platforms before provider access
or copy creation. Windows/frozen builds can still render the portable offline sharing preview.
There is no repository path, destination, source, worker, receipt-import or resume option.

Only the registered synthetic ownership-omission pair and eight reviewed cases are supported.
The model selects a registered template; the host derives its exact diff. This is not arbitrary
AI-generated code repair, HTTP authorization verification, an OS sandbox or a security guarantee.
Existing Codex ChatGPT login and the pinned adapter are unchanged; no API key is introduced.

Initial verification used temporary files, fake adapters and scripted worker responses, **not policy
observations**. On 2026-10-30 KST, one noneditable Python 3.12.7 wheel installation matched the source
and passed 23 offline checks: the existing 13 plus 10 additional checks. Two separately approved real
recommendation attempts followed. The first declined an expired copy choice and exited `0`; the second
created one copy, prepared the before plan, then declined the unapproved worker step and exited `0`
as `before-check-declined`. Neither attempt ran a policy worker, applied a repair or restored a file.
The second raw stdout capture was incomplete; separate checks of the full before plan, final workflow
object, durable record and actual file do not establish a complete single-JSON stdout parse.

This is bounded installed recommendation/preparation evidence, not full end-to-end acceptance or
pipx/upgrade/native distribution evidence. The prior source-API observation is also a separate result.
See the [installed-flow acceptance runbook](OWNER_FILE_ACCEPTANCE.md) for the observation boundaries,
evidence capture and next separately approved gates. Full installed-flow acceptance remains open under
#82/#81/#35. Documentation examples and completed approvals do not authorize a new live attempt.

## Preview without side effects

Use a source installation containing this change. `YOUR_EXACT_MODEL_ID` is a placeholder for an
exact model available to your existing Codex account, not an automatic model selection.
These commands are offline and require neither authentication nor a provider/worker process:

```bash
authzest codex-owner-repair --model YOUR_EXACT_MODEL_ID --file-workflow --preview-only
authzest codex-owner-repair --model YOUR_EXACT_MODEL_ID --candidate after --file-workflow --preview-only --json
```

Preview-only deliberately uses the unchanged **sharing preview**. It shows the complete fixed
sources, criteria, assumptions, expectations, prompt, schema, model/settings and a fresh sharing
challenge. It creates no copy or file-stage plan and fabricates no file approval identifiers.
A preview-only challenge cannot approve a later invocation. `--file-workflow` is a selector,
**not consent**; neither this flag nor sharing approval grants file effects.

## Interactive sequence — separate choices

The following command is active, not an offline smoke test. Do not run it until you intend to
review sharing and each local effect; a provider request may consume account usage. The existing
one-attempt/120-second application limit does not separately cap Codex-internal retries or usage.

```bash
authzest codex-owner-repair --model YOUR_EXACT_MODEL_ID --candidate before --timeout-seconds 120 --file-workflow
```

Review every complete JSON preview, not just the human summary. Enter the exact phrase printed
by the **current** invocation. Enter declines; literal `cancel` cancels that choice. An unmatched
phrase is a decline, not a retry. EOF or interruption stops interaction rather than answering a
later restore prompt. There are no unattended approval flags or automatic rollback.

| Gate    | Exact phrase                         | Separately authorized effect                                                                                   |
| ------- | ------------------------------------ | -------------------------------------------------------------------------------------------------------------- |
| Sharing | `share <sharing_id>`                 | One existing adapter recommendation attempt; no policy execution or copy.                                      |
| Copy    | `copy <session_id> <application_id>` | One new private temporary copy of the registered before policy and retained evidence files.                    |
| Before  | `approve before-check <plan_id>`     | Check captured before-file bytes in the fixed worker. Expected case mismatches are not infrastructure failure. |
| Diff    | `approve diff <plan_id>`             | Accept the exact host-derived diff; no file replacement.                                                       |
| Apply   | `approve apply <plan_id>`            | Replace only the session-owned `policy.py` with registered after bytes.                                        |
| After   | `approve after-check <plan_id>`      | Check captured applied-file bytes, not an embedded after control.                                              |
| Restore | `approve restore <plan_id>`          | Restore registered before bytes only while the tracked file and evidence remain confirmed.                     |

The current recommendation and complete request bindings are revalidated before copy creation.
`no-change` and `unknown` finish normally without a copy. `registered-change` is valid only for
`before`; an `after` response cannot select a repair. Old provider captures, JSON decisions or
saved checkpoints cannot be imported as current authority.

The copy decision and each prepared stage expire within **300 seconds**, with a single attempt.
Reading or displaying a plan does not renew it. File identity, bytes, decision validity and
prerequisites are rechecked at the effect boundary. A new CLI invocation starts a new sharing
decision; it does not resume a retained copy or reuse consumed approvals.

Declining before/diff/apply stops forward progress. If a confirmed applied copy remains after an
after-check refusal or failure, the CLI can offer a **new, separately approved restore plan**.
User edits, missing/unconfirmed evidence or uncertain writes block unsafe continuation/restoration.
Interruption does not trigger automatic restore. Review the final checkpoint and retained files
before any manual follow-up; never assume an unsuccessful command made no change.

## Human output, JSON and retained state

Human output separates provider identity/usage, execution, expected-versus-observed comparisons,
application, restoration, file binding and evidence. Its eight-case table keeps missing observations
unknown. Data values are ASCII-quoted/escaped; model prose and displayed paths are not instructions.
Full authoritative JSON remains visible before each effect choice.

Add `--json` for **one final JSON document on stdout**; interactive previews, prompts and progress
go to stderr. With `--preview-only --json`, stdout contains just the complete sharing preview.
The active result kind is `codex-owner-file-workflow`; `file_workflow.session_result` holds the
current unauthenticated file checkpoint when available. Outer provider identity/usage/latency describe
the recommendation request; a nested pure-data preview's zero calls must not replace those metrics.

Execution completion is not comparison success. A completed before check can contain the two
expected mismatches. After restoration, a historical passing after comparison describes the earlier
applied bytes, **not the now-restored before file**; restoration does not rerun either check.
Failures retain partial effects and distinct recovery states instead of claiming blanket `not-run`.
An unavailable current checkpoint for a created session means unknown state, not proof of
non-execution. Normal `no-change`/`unknown` or pre-copy refusal instead reports that no copy was created.

Copies and records remain on disk after completion, refusal, failure or cancellation. Closing releases
the descriptor; it does not delete the workspace or rewrite `record.json`. Consequently, the final
in-memory `closed` value can differ from the last durable record. Neither form is an authenticated
receipt or resumable session; authorization remains `unknown`. Local paths, session/plan identifiers
and raw records may be private: inspect and redact them before sharing issue reports.
