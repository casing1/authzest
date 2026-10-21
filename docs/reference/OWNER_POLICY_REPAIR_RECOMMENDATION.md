<p align="center">
  <strong>English</strong> ·
  <a href="../i18n/ko/reference/OWNER_POLICY_REPAIR_RECOMMENDATION.md">한국어</a>
</p>

# Offline registered repair-recommendation contract

[Documentation index](../README.md) · [Development plan](../development/DEVELOPMENT_PLAN.md) ·
[Registered pair API](OWNER_POLICY_REPAIR_PAIR.md) ·
[Unchanged S1 recommendation API](OWNER_POLICY_RECOMMENDATION.md) ·
[Issue #81](https://github.com/casing1/authzest/issues/81)

## Availability and boundary — 2026-10-21 KST

This is **new unreleased source work in progress** in
`authzest.codex.owner_policy_repair_recommendation`, tracked under #81. It is a separate pure
offline contract for selecting the registered test-only repair pair, not a new CLI command,
provider adapter, live Codex answer, AI-generated source/diff or complete #81/#35 workflow.
This document does not claim new CI/review/delivery results or runtime observations.

The fixed pair API was delivered through [PR #101](https://github.com/casing1/authzest/pull/101)
at merge `cbe6b37` on 2026-10-21 KST. This extension uses those exact registered sources, criteria,
assumptions, eight reviewed expectations and recorded-review bindings. It pins the review by its
hash rather than embedding its full record or URL. It does not change their
authorship or convert the recorded label decision into authenticated approval, execution consent
or observed behavior. Published alpha.3, report schema `1.2`, S1 schema `1.0` / registry `empty-v1`
and the #80 correct-policy worker remain unchanged. The negative candidate is not added to that
worker's allowlist.

There is no filesystem/network/provider/process access, target import/evaluation, file application
or restoration. `policy.py` remains a logical display label, not an input path. The API accepts no
arbitrary source, repository, callback, model choice, replacement pair, cases, labels or approval.
The prompt is inert text; generating it does not send anything to Codex.

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

Complete canonical/raw UTF-8 artifacts and the rendered prompt are bounded to 262,144 bytes;
JSON depth is at most 32 and visited nodes at most 8,192. These limits include complete composed
preview metadata and any nested registered-pair preview. General explanation text is bounded to
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
print(json.dumps({
    "prepared_prompt": owner_policy_repair_recommendation_prompt(request),
    "preview": preview.to_dict(),
}, ensure_ascii=True, indent=2))
```

## Verification and remaining gates

Offline verification must cover both candidates and all statuses; exact request/prompt/evidence/case
bindings; stale/forged/detached data; closed field and complete-artifact budget boundaries; and guards
against side effects or policy import/evaluation. These are requirements, not results claimed here.

The next live integration requires its own exact sharing preview, minimized transport review and
fresh bounded sharing/provider-use approval. A pinned prompt alone is not a transport or consent
boundary. Before/after observations then need a separately reviewed fixed worker recipe and fresh
exact-plan decisions; #80 must continue rejecting the negative source. Exact-diff approval,
new-copy application, verification and recovery require later independent current-state decisions.
No live call, execution, patch, merge, tag or release follows from these data objects. Wider #81/#82
and prerelease gates remain open.
