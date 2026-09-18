<p align="center">
  <strong>English</strong> ·
  <a href="../i18n/ko/reference/EXPECTATION_CONTRACT.md">한국어</a>
</p>

# Offline evidence-linked expectation contract

[Documentation index](../README.md) · [Proposal and decision contract](PROPOSAL_CONTRACT.md)

## Implemented scope

[#61](https://github.com/casing1/authzest/issues/61) adds a pure, caller-authored expectation manifest
under #35. It is an unreleased source-checkout addition after alpha.3, with its own schema `1.0`.
Package version `0.1.0a3`, report schema `1.2`, and the existing proposal/decision schemas are unchanged.
The implementation is [codex/expectations.py](../../src/authzest/codex/expectations.py).

The manifest connects an exact proposal to baseline source/registration evidence, cited policy and
intended outcomes for later review. It generates no tests, calls no provider, reads or writes no files,
and executes no source, process or network operation. The separate
[#63 CLI preview](../guides/PROPOSAL_PREVIEW.md) displays it from a validated offline bundle.
The later [#69 source-only check](../guides/PROPOSAL_CHECK.md) compares declaration targets with a
bounded subset of that bundle's source snapshots. No adapter, patch-application or execution service,
or approval decision consumes or binds this manifest.
The existing fixed configuration/health fixture workflow is unchanged; #35 and broader
defensive regression-test drafting remain unfinished.

## Bound data and validation

`prepare_expectation_manifest` takes a request, its validated review, an exact proposal and a list of
caller-authored expectations. `validate_expectation_manifest` revalidates those artifacts and accepts
only the exact schema fields, not a command or executable test language.

- The manifest binds `request_id`, `review_id`, `proposal_id` and `source_identity`. Its
  `manifest_id` is `expectation-` followed by the canonical payload's SHA-256. All material content,
  including expected values, policy references and limitations, contributes to that identity.
- Each expectation supplies `id`, `source_evidence_id`, `route_evidence_id`, `policy_evidence_ids`,
  `observation`, `expected` and nonempty `limitations`. The source and route must belong to the same
  request, have the correct evidence kinds and name the same file, which the proposal must change.
  Every policy reference must identify policy evidence in that request; citations do not establish
  that the policy supports the expectation or is approved by its owner.
- Preparation derives `path`, `baseline_registration_id`, `before_sha256` and `after_sha256` from
  those artifacts. Validation rejects inconsistent supplied bindings. Exact UTF-8 source and replacement
  hashes preserve line endings. The registration ID identifies the baseline registration, including
  source locations; it is not promised to remain stable after a patch.
- A manifest has 1–32 expectations with unique IDs matching `[a-z][a-z0-9-]{0,63}`. It rejects repeated
  `(baseline_registration_id, observation)` pairs. Each expectation needs 1–16 unique policy references
  and 1–16 nonblank limitations. The AI contract's bounded JSON parsing rules also apply.
- Missing, foreign or wrong-kind evidence, stale bindings, duplicate references, unsupported observations
  and unexpected fields raise `ContractError`. Shell, environment, install-hook, observed-result or
  approval fields are not accepted as extra manifest fields. Prose remains untrusted display data.

The immutable wrapper stores canonical JSON; `to_dict()` and previews return detached data. Consumers
must revalidate even a `ValidatedExpectationManifest` wrapper. This is content binding, not a signed
authorization record, proof of fixture ownership, semantic correctness or current disk/Git freshness.

## What an expectation means

| `observation`             | Exact `expected` shape                                                                | Intended meaning, not an observed result                                                                                       |
| ------------------------- | ------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| `policy-intent`           | `{"intent": "public"}`; also `restricted` or `unspecified`                            | Caller interpretation of cited policy; no automatic policy matching or enforcement claim                                       |
| `dependency-declarations` | `{"count": 1}`; integer 0–256, not boolean                                            | Intended effective dependency declaration count for the selected registration; ordinary DI is not access-control evidence      |
| `scope-declarations`      | `{"scopes": ["items:read"]}`; 0–32 unique, nonblank strings of at most 256 characters | Intended unique declared scopes across that registration's effective dependencies; declarations do not prove scope enforcement |

These are caller-authored targets. This pure contract module does not parse or compare source.
The separate [#69 checker](../guides/PROPOSAL_CHECK.md) re-parses supported baseline/proposed snapshots
and reports declaration comparisons, while `policy-intent` always remains `not-evaluated`.
Baseline evidence may be partial, and an expectation manifest may
cover only a subset of proposal changes. An empty scopes list or zero declaration count is not a finding
that an endpoint is public, safe or vulnerable. Public intent does not prove public runtime behavior;
restricted intent does not prove authorization.

`expectation_preview` always returns `status: draft`, `verification_status: not-run`, `observed: null`
and `authorization_verdict: unknown`. It labels policy intent as `caller-policy-interpretation` and
declaration expectations as `source-declaration-target`, retaining explicit limitations. Successful
validation means structural consistency only, not passed verification or a fixed security issue.

No existing proposal decision binds this separately versioned manifest. A changed expectation creates
a new manifest identity, but does not currently invalidate a proposal-only decision. A future execution
integration must bind the reviewed manifest to its own exact plan and separate approval, define a fixed
checker and result contract, and recheck actual state. Do not attach this artifact to an unrestricted executor.

## Python API and offline checks

This example assumes `request`, `review` and `proposal` already exist, and the caller has reviewed the
three evidence IDs from that request for a changed file and its baseline registration. `public` is an
illustrative caller-authored target, not a classification inferred by the API.

```python
from authzest.codex.expectations import (
    expectation_preview,
    prepare_expectation_manifest,
)

manifest = prepare_expectation_manifest(
    request,
    review,
    proposal,
    expectations=[
        {
            "id": "policy-intent-1",
            "source_evidence_id": source_evidence_id,
            "route_evidence_id": route_evidence_id,
            "policy_evidence_ids": [policy_evidence_id],
            "observation": "policy-intent",
            "expected": {"intent": "public"},
            "limitations": ["Caller-authored intent; enforcement is not established."],
        }
    ],
)
preview = expectation_preview(manifest, request, review, proposal)
```

After editable development setup, from the repository root:

```bash
python -m pytest tests/test_expectation_contract.py
```

The tests use caller-authored mock expectations for the existing public-intent, ordinary-DI and
declared-scope development cases. Frozen corpus bytes and held-out cases are unchanged. They test
structural/reference rejection, identity changes, detached serialization and no-I/O behavior, not
model quality, actual target observations or authorization correctness. No live Codex validation or
release is implied by this offline slice.
