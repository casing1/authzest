<p align="center">
  <strong>English</strong> ·
  <a href="../i18n/ko/reference/OWNER_POLICY_REPAIR_RECOMMENDATION.md">한국어</a>
</p>

# Registered repair recommendation and sharing

[Documentation index](../README.md) · [Development plan](../development/DEVELOPMENT_PLAN.md) ·
[Registered pair API](OWNER_POLICY_REPAIR_PAIR.md) ·
[Unchanged S1 recommendation API](OWNER_POLICY_RECOMMENDATION.md) ·
[Issue #81](https://github.com/casing1/authzest/issues/81)

## Availability and boundary — 2026-10-28 KST

This **unreleased source feature** is tracked under #81. The pure offline selection contract in
`authzest.codex.owner_policy_repair_recommendation` was delivered through
[PR #102](https://github.com/casing1/authzest/pull/102) at merge `8409bc7` on 2026-10-24 KST.
The source implementation delivered through [PR #103](https://github.com/casing1/authzest/pull/103)
at merge `cc644a1` on 2026-10-25 KST adds the separate `codex-owner-repair` command: a complete
sharing preview, an explicit one-attempt sharing decision and an existing Codex App Server
transport connection. One fresh, separately approved live attempt at that commit succeeded on
2026-10-28 KST; see the bounded acceptance record below. It does not complete #81/#35 or establish
policy observations, application or recovery. Published alpha.3 does not include this command.

The fixed pair API was delivered through [PR #101](https://github.com/casing1/authzest/pull/101)
at merge `cbe6b37` on 2026-10-21 KST. This extension uses those exact registered sources, criteria,
assumptions, eight reviewed expectations and recorded-review bindings. It pins the review by its
hash rather than embedding its full record or URL. It does not change their
authorship or convert the recorded label decision into authenticated approval, execution consent
or observed behavior. Published alpha.3, report schema `1.2`, S1 schema `1.0` / registry `empty-v1`
and the #80 correct-policy worker remain unchanged. The negative candidate is not added to that
worker's allowlist.

The pure contract still has no filesystem/network/provider/process access, target import/evaluation,
file application or restoration. `policy.py` remains a logical display label, not an input path.
It accepts no arbitrary source, repository, callback, replacement pair, cases or labels. Rendering
the prompt or CLI sharing preview sends nothing to Codex. Only the separately approved interactive
transport path starts Codex; it does not execute either policy candidate or apply the selected diff.

## Bounded live acceptance — 2026-10-28 KST

The [acceptance record](https://github.com/casing1/authzest/issues/81#issuecomment-6458726176)
documents one freshly approved `before` attempt at `cc644a1`, using the existing ChatGPT login,
Codex `0.153.0` and explicit model `gpt-6-astra`. The approved input was the public fixed synthetic
before/after policy pair, criteria, assumptions, eight reviewed expected labels, prompt and output
schema. The limit was one application turn with a 120-second timeout, no AuthZest retry or model
fallback; Codex-internal retries and actual usage were not separately capped. The exact fresh
sharing phrase was entered under the user's authorization after comparing the complete preview.

- The workflow returned `recommendation-ready` with `registered-change` in `30690.214375` ms.
- Reported usage was 7,750 input and 697 output tokens, with one warning and zero retry notifications.
  These are reported transport observations, not a signed provider receipt or a guarantee that no
  unreported internal retry occurred.
- The model selected the existing registered repair template; it did not generate arbitrary
  replacement code. The host derived the diff, and offline revalidation of the result, evidence
  references and composed diff passed.
- Neither policy was executed; application/restoration remained `not-run`, before/after observations
  stayed null, comparison stayed `not-evaluated` and authorization stayed `unknown`. The original
  checkout was unchanged.

That one-run sharing approval is consumed. This is one bounded integration acceptance, not an
independent benchmark, general model-quality result or proof that the repair changes observed
behavior. The maintainer subsequently [approved the dedicated check design and offline implementation](https://github.com/casing1/authzest/pull/110#issuecomment-6459020000).
PR #110 adds a separate [registered-candidate check Python API](OWNER_POLICY_REPAIR_CHECK.md)
with offline/mocked-process verification only. Neither new candidate has been executed; before and
after still require separate fresh exact-plan decisions for actual observation. Embedded after is
a control, not applied-file verification. The #80 worker remains unchanged and continues rejecting
the negative candidate. #81/#35/#82 remain open.

## CLI: preview first, then opt in

Use a source installation containing this work. Supply the exact model identifier available to your
existing Codex ChatGPT account; no model is selected or substituted automatically. Replace
`YOUR_EXACT_MODEL_ID` below before requesting a live response. Both preview commands are offline:

```bash
authzest codex-owner-repair --model YOUR_EXACT_MODEL_ID --preview-only
authzest codex-owner-repair --model YOUR_EXACT_MODEL_ID --candidate after --timeout-seconds 120 --preview-only --json
```

The preview contains the complete fixed request, both source snapshots, policy criteria, trusted
assumptions, eight reviewed case expectations, exact rendered prompt and requested output schema.
It also shows the selected model, host settings/limits and a fresh sharing challenge. These are the
contents to review, not just a summary or hashes. No repository path is accepted or read as source.
`--preview-only` does not inspect authentication or start a provider process.
This is the complete AuthZest-controlled payload; Codex also adds harness context, and the account's
data-handling rules apply. It is not a byte-for-byte preview of all provider-side context.

To request one response, run without `--preview-only`:

```bash
authzest codex-owner-repair --model YOUR_EXACT_MODEL_ID --candidate before --timeout-seconds 120
```

Review the new complete preview and enter exactly `share <sharing_id>` using the ID printed by that
invocation. A preview-only ID or copied prior decision is not authority for a later invocation.
Declining or cancelling before sharing sends no request. There is no noninteractive approval flag.
`before` is the default candidate; `after` retains the correct-policy no-change/unknown path.

The live path requires POSIX and uses the existing version-pinned Codex `0.153.0` App Server transport
and existing ChatGPT login. Preview-only does not require POSIX or that Codex installation.
It does not create an API key. AuthZest makes one application-level attempt, with no
retry or model fallback. Codex/provider internal communication retries and actual usage/billing are
not separately capped by that limit or the timeout. The sharing decision authorizes this request
only, not policy execution, patch application, verification or restoration.

Default output is human-readable. `--json` keeps the final result on stdout and interactive preview,
prompts and progress on stderr; `--preview-only --json` emits the complete offline preview on stdout.
Treat explanatory strings as untrusted display data, not instructions. The adapter validates the
response against the exact request before composing the host-derived diff. `registered-change`
is valid only for `before`; `no-change` and `unknown` remain valid results. Validation failure or
transport failure is not evidence that either policy is safe or that a repair succeeded.

The pure result preview keeps its caller-supplied-data provenance and zero provider-call count:
it describes that pure composition step. Separate adapter metadata reports the host's transport
attempt; it is not a signed provider attestation and does not turn model explanations or reviewed
expectations into observed policy behavior. The existing `codex-owner-review`, S1 contract and
#80 worker remain unchanged.

In the CLI preview/result, `request_id` identifies the transport request, including its selected
model and output schema; `recommendation_request_id` identifies the unchanged model-independent
selection request. A successful workflow keeps the transport envelope in `recommendation` and the
pure composed result in `recommendation_preview`. `application_turn_attempts` counts host adapter
attempts, not successful provider turns or billable calls.

## Python entry points

| Entry point                                                            | Result                                                                  |
| ---------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| `build_owner_policy_repair_recommendation_request(candidate="before")` | Build a fixed request for exactly `before` or `after`                   |
| `validate_owner_policy_repair_recommendation_request(raw)`             | Rebuild and validate the complete exact current request                 |
| `owner_policy_repair_recommendation_prompt(request)`                   | Revalidate the request and compose the pinned prompt plus its JSON data |
| `validate_owner_policy_repair_recommendation(raw, request)`            | Validate a closed result against that exact request                     |
| `prepare_owner_policy_repair_recommendation_preview(result, request)`  | Revalidate both artifacts and compose an output-only preview            |

The validators receive serialized JSON text, not a file path or executable input. IDs and wrappers
are not approval capabilities: consumers revalidate the complete current context, not only a copied
hash or directly constructed dataclass. Detached snapshots cannot register new content. Version,
candidate, prompt or registered-content changes invalidate stale bindings.

## Request, evidence and result semantics

This separate schema `1.0` pins the prompt, candidate and complete registered pair context with its
hashes. Candidate `before` selects the deliberately incorrect, explicitly warned test-only source;
`after` selects the unchanged correct maintained source. Both candidates keep the same complete
registered pair available as evidence. No caller-selected source normalization or editing occurs.
Content identities bind exact data; they attest neither who authored it nor permission to share it.

The closed request contains exactly these fields:

| Field                     | Binding                                                                                                  |
| ------------------------- | -------------------------------------------------------------------------------------------------------- |
| `schema_version` / `kind` | `1.0` / `owner-policy-repair-recommendation-request`                                                     |
| `candidate`               | Exactly `before` or `after`; default `before`                                                            |
| `prompt`                  | Exactly `version` = `owner-repair-selection-v1` and fixed `text`                                         |
| `registry`                | Exactly registered `version`, `pair_id`, `content_sha256`, `review_record_sha256`                        |
| `content`                 | Full exact registered pair content, including both sources, criteria, assumptions and cases/expectations |
| `evidence_ids`            | Exactly `before`, `after`, `criteria`, `cases`, each binding that full content section                   |

The derived `request_id` is not a self-referential request field. The rendering function returns
the exact pinned instruction text, `\nREQUEST_JSON:\n`, canonical request JSON,
`\nREQUEST_ID:\n`, its derived ID and a final LF. Prompt version pins both instructions and this
rendering recipe; it does not identify a selected model or a provider response.

Results use these data statuses:

| Status              | Permitted binding                                       | Meaning within this contract                                      |
| ------------------- | ------------------------------------------------------- | ----------------------------------------------------------------- |
| `registered-change` | `before` request only; exact current registered pair ID | Select the one host-registered change, not replacement source     |
| `no-change`         | Pair ID is JSON null                                    | No change selected; not a security verdict                        |
| `unknown`           | Pair ID is JSON null                                    | Insufficient support retained explicitly; not an observed failure |

Every result references the exact four registered evidence IDs and one to eight distinct existing
case IDs. New or duplicate evidence/case references are refused. Rationale, assumptions,
uncertainties, expected effects and limitations are bounded untrusted explanatory data. `unknown`
requires a nonempty uncertainty list. The validator cannot establish explanation truth or prevent
false claims inside strings. Valid references
or a `registered-change` status do not prove that the explanation is correct or that the selected
change fixes anything.

Raw results cannot supply source, diff, commands, executable tests, cases/labels, observation or
approval fields. Extra fields are rejected even when empty. Provider/model provenance and execution
claims are not accepted from result JSON. Instructions or code-like text within explanation strings
remain untrusted data and must not be evaluated or treated as permission.

The raw result has exactly `schema_version`, `request_id`, `status`, `rationale`, `evidence_ids`,
`case_ids`, `assumptions`, `uncertainties`, `expected_effects`, `limitations` and `change_pair_id`.
Assumptions, expected effects and limitations each require at least one nonblank item; `unknown`
also requires at least one uncertainty. Other statuses may have an empty uncertainty array.
All explanation arrays have at most 32 items. Neither casing/coercion nor omitted keys are accepted.

## Output-only preview and next gates

Only a valid `before` / `registered-change` result composes the existing host-derived exact pair
diff in `pair_preview`, the full existing registered-pair preview dictionary. `no-change` and
`unknown` set `pair_preview` to JSON null. The composed preview also embeds the revalidated
`request` / `recommendation`, their IDs and kind `owner-policy-repair-recommendation-preview`.
There are no caller-supplied or additional `changes` / `diffs` fields. The host, not the supplied
response, owns all source/diff bytes and operational facts. Provider calls are `0`; execution,
application and restoration remain `not-run`; before/after observations remain null, comparison
`not-evaluated` and authorization `unknown`.

Preview provenance remains unauthenticated caller-supplied data. A caller can have scripted the
entire result; this API has no transport receipt or live-model evidence. The preview is data, not
a renderer, sharing-consent record, execution plan or patch service. Any later renderer must escape
untrusted text. Printing a prompt, diff or copied JSON grants no authority.

## Bounds and explicitly scripted example

Canonical/raw UTF-8 contract requests/results, the complete pure composed preview and the rendered
prompt are bounded to 262,144 bytes; JSON depth is at most 32 and visited nodes at most 8,192.
These limits include pure composed-preview metadata and any nested registered-pair preview.
The outer CLI sharing/workflow output repeats payloads and is not capped at 262,144 bytes as a whole.
General explanation text is bounded to
4,096 characters and IDs to 128. Shared decoding rejects duplicate keys, non-finite numbers,
invalid Unicode and forbidden text controls without silently normalizing source. Shape-valid
alternative prompt, sources, labels, review hashes or evidence still fail exact registered equality.
General text allows TAB/LF/CR and does not remove every bidi/zero-width character; safe presentation
is still a separate responsibility.

Use a source environment containing this new work, not the alpha.3 executable. This example
constructs an explicitly **SCRIPTED** `unknown` response. It asks no provider, evaluates neither
policy candidate, applies nothing and grants no sharing/execution consent. The complete prepared
prompt and output preview are printed as ASCII-escaped display data.

```python
import json

from authzest.codex.owner_policy_repair_recommendation import (
    build_owner_policy_repair_recommendation_request,
    owner_policy_repair_recommendation_prompt,
    prepare_owner_policy_repair_recommendation_preview,
    validate_owner_policy_repair_recommendation,
    validate_owner_policy_repair_recommendation_request,
)

request = build_owner_policy_repair_recommendation_request(candidate="before")
request = validate_owner_policy_repair_recommendation_request(
    json.dumps(request.to_dict(), ensure_ascii=True)
)
payload = request.to_dict()

# SCRIPTED caller-owned data, not a model answer or policy verdict.
SCRIPTED_RESULT = {
    "schema_version": "1.0",
    "request_id": request.request_id,
    "status": "unknown",
    "rationale": "Scripted example: no semantic review was performed.",
    "evidence_ids": list(payload["evidence_ids"].values()),
    "case_ids": [payload["content"]["cases"][0]["case_id"]],
    "assumptions": ["This is caller-supplied demonstration data."],
    "uncertainties": ["No model answer or before/after observations were obtained."],
    "expected_effects": ["No change selected, policy execution or patch requested."],
    "limitations": ["Reference validation does not establish semantic correctness."],
    "change_pair_id": None,
}
result = validate_owner_policy_repair_recommendation(
    json.dumps(SCRIPTED_RESULT, ensure_ascii=True), request
)
preview = prepare_owner_policy_repair_recommendation_preview(result, request)
print(
    json.dumps(
        {
            "prepared_prompt": owner_policy_repair_recommendation_prompt(request),
            "preview": preview.to_dict(),
        },
        ensure_ascii=True,
        indent=2,
    )
)
```

## Verification and remaining gates

Offline verification must cover both candidates and all statuses; exact request/prompt/evidence/case
bindings; stale/forged/detached data; closed field and complete-artifact budget boundaries; and guards
against side effects or policy import/evaluation. These are requirements, not results claimed here.

The sharing/adapter checks additionally cover scripted transport responses, refusal/cancellation,
exact sharing bindings and failure cases; offline tests are not live-model acceptance. The separate
2026-10-28 acceptance above consumed its one-run sharing approval; any further provider check needs
a fresh bounded decision. The [dedicated fixed-check API](OWNER_POLICY_REPAIR_CHECK.md) implements
the reviewed recipe in PR #110 with offline/static/mock verification only. Actual before/after
observations still need fresh, separate finalized-plan decisions and bounded acceptance; no actual
new worker run is approved or reported. #80 continues rejecting the negative source. Exact-head
delivery, exact-diff approval, new-copy application, file-bound verification and recovery remain
separate gates; an embedded after control cannot verify an applied file.
No execution, patch, merge, tag or release follows from these data objects or a valid provider result.
Wider #81/#82 and prerelease gates remain open.
