<p align="center">
  <strong>English</strong> ·
  <a href="../i18n/ko/guides/OWNER_POLICY.md">한국어</a>
</p>

# Owned report policy example

[Documentation index](../README.md) · [Source-only examples](EXAMPLES.md) · [Integrated review demo](REVIEW_DEMO.md)

## Scope and availability

[#73](https://github.com/casing1/authzest/issues/73) adds one maintained owner-only report-read policy
and an independent regression matrix to the source checkout. It is a developer example, not a new
AuthZest command or runtime mode. Use a checkout containing this change with the
[development environment](../../README.md#development-setup) active. Published alpha.3 binaries do
not install this example or its tests; package `0.1.0a3` and scan report schema `1.2` are unchanged.
The issue records acceptance and policy-review status; this guide does not claim a new release.

The example separates three things: a pure policy function exercised by developer unit tests,
FastAPI declarations inventoried without target execution, and real authentication/HTTP integration
that is not implemented or tested here. Data is synthetic; there is no vulnerable variant, bypass
demonstration, external service, model call or generated-code execution.

## Policy and trust boundary

The [policy module](../../examples/fastapi_owner_policy/policy.py) defines
`Principal(subject, authenticated, scopes)`, `Report(report_id, owner_id)` and
`can_read_report(principal, report) -> bool`. Access is allowed only when every condition holds:

- The inputs are the exact expected `Principal` and `Report` types, with valid nonblank string IDs.
- `authenticated` is exactly `True`.
- `scopes` is a `frozenset` of nonblank strings containing the exact scope `reports:read`.
- The principal's subject equals the report's nonblank owner ID exactly.

All other inputs are denied, including missing identities/owners, missing scope and non-owner access.
Whitespace checking rejects blank IDs/scopes but does not normalize their values for comparison.
There is no admin, wildcard, substring or case-insensitive exception. A malformed scope collection
does not become valid merely because it also contains the required scope.

The function assumes a trusted caller supplies verified principal attributes and authoritative report
ownership. It does not authenticate a person, validate tokens, load ownership from a database or make
client-supplied identity/scopes trustworthy. Constructing a `Principal` in a test models that trusted
input; it is not an authentication implementation or permission to accept those fields from HTTP.

## Run the two kinds of checks

From the repository root:

```bash
authzest scan examples/fastapi_owner_policy --json
python -m pytest tests/test_owner_policy.py
```

The scan reads two Python files and inventories one `GET /reports/{report_id}` registration, with
bounded analysis, no diagnostics/parse errors and Codex disabled. It records one parameter-annotation
`Security` declaration targeting `require_authenticated_principal`, with `scopes=["reports:read"]`;
the local and effective dependency lists each contain that declaration. These are static source facts,
not proof that the policy function is called correctly or that HTTP access is enforced.

The developer tests deliberately import and call the reviewed, repository-owned **pure policy module**
against the [independent matrix](../../tests/fixtures/owner_policy/cases.json). Expected allow/deny values
are data, not calculated by the function under test. Cases cover the authentication/scope/owner conditions
and invalid or missing inputs. Separate inventory regressions keep the application and its framework
unimported while checking source evidence. The FastAPI application, endpoint and authentication provider
are not executed by these checks. Unit-test execution is not an AuthZest fixture-runner permission.

A passing matrix supports only the listed policy inputs and implementation. A successful scan means
the inventory was produced. Neither is a general authorization verdict, endpoint test, vulnerability
finding, model-quality evaluation or verified security repair.

## Source reference and deliberately missing integration

[main.py](../../examples/fastapi_owner_policy/main.py) is a source-only FastAPI reference. Its
authentication provider is deliberately unconfigured and fail-closed; it does not accept identity,
authentication flags or scopes directly from request fields. The source shows a fixed synthetic report
lookup and a policy decision before returning data, but it is not a runnable authentication tutorial.
Do not start its server or import it as part of this validation.

Real principal verification, HTTP endpoint behavior, database ownership, token expiry and integration
with Codex patch proposals remain separate work. The opt-in [read-only Codex owner review](CODEX_OWNER_REVIEW.md)
uses packaged snapshots and produces review/case drafts only; it does not execute this example.
The scanner does not infer the policy function's semantics.
This example does not expand the narrow syntax accepted by `proposal-check`, existing copy-application
flows or the fixed source/runtime fixture allowlists. Default scans remain source-only; there is no
provider/account use, source sharing or automatic patch application.

## Matrix provenance and compatibility

The maintainer approved the policy criteria on 2026-09-24: authenticated identity, exact `reports:read`
scope and matching ownership are all required; there is no admin exception and missing information
is denied. The policy matrix and all 28 exact expected values remain assistant-authored development
material, not human-authored or independently approved reference labels. The recorded status is
`criteria-approved-label-review-pending`, not blanket approval of those labels. Policy decisions and
maintainer review are tracked in [#73](https://github.com/casing1/authzest/issues/73) and
[#75](https://github.com/casing1/authzest/issues/75). Review expected values separately from implementation
changes rather than deriving both from the same logic. Policy approval does not approve source sharing,
account use, patch application or execution.

The frozen `tests/fixtures/ai_evaluation/v1` corpus, labels, held-out split and hash are unchanged.
Its source-only declared-scope examples still have unknown authorization; this new policy unit test
does not upgrade their verdicts or change the mock evaluation scores. Existing Codex and fixture flows,
published alpha.3 assets and the broader incomplete #35 acceptance remain unchanged.
