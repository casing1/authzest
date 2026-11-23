# External test interfaces and supplied comparisons (S3)

[Documentation](../README.md) · English · [한국어](../i18n/ko/reference/REPOSITORY_VERIFICATION.md)

[#206](https://github.com/casing1/authzest/issues/206) adds pure Python contracts for the
[external file-workflow design](../development/REPOSITORY_FILE_WORKFLOW.md). It does not start a
model, import/collect/execute source or tests, launch a guest, read files or authorize writes.
The current `repo-suggest`, adapter and [S2 file session](REPOSITORY_FILE_SESSION.md) retain their
existing v1.0 boundaries. The new request type is not accepted by those APIs or the current GUI.

## Explicit model-visible test interface

`build_repository_test_request(base, entry_source=..., import_root='.', app_attribute='app')`
produces a distinct frozen `RepositoryTestRequest` with schema `1.1`. Its base is a validated current
`RepositoryProposalRequest` (`1.0`); old payloads, prompts and identities remain unchanged. The new
config truthfully identifies prompt version `external-repository-test-proposal-v1.1`.
`validate_repository_test_request` reconstructs the complete selection, static evidence, interface,
prompt, schema and identity. Response validation and host-derived preview use the new version/ID
and retain the existing bounded inert-source/test rules.

The declared `test_interface` binds:

- An already selected Python `entry_source`, import root `.` or `src`, derived module and a plain
  ASCII Python app-attribute identifier, default `app`.
- A trusted `client` fixture, lifespan `off` and authentication overrides `none`.
- Interface schema `1.0` and its own canonical identity, included in the new prompt/request identity.

Module components must be ASCII identifiers and non-keywords. Selected package initializers are
required; no discovery, factory calls, synthesized `__init__.py`, project dependency installation,
conftest/plugins or setup callbacks are declared. With `src`, all selected Python files must be below
that root. Reject physical aliases and logical file/package or module/submodule conflicts such as
`pkg.py` alongside `pkg/__init__.py`. A valid declaration does not establish an app object, usable
imports, installed dependencies or a working fixture; these remain unverified until a later runtime.

The model receives the selected source, policy, evidence and explicit interface. It does **not** receive
the independent case set, case IDs, expected values or human-review declarations. Provider access,
sharing decisions and transport compatibility remain separate gates. The
[official App Server documentation](https://learn.chatgpt.com/docs/app-server#turns) describes per-turn
`outputSchema`; that documentation does not establish new-request compatibility with this project's
pinned `0.153.0` adapter. No RPC/pin change or actual model call occurs here.

## Host-only independent case declarations

`build_repository_cases(data)` returns a frozen `RepositoryCaseSet`;
`validate_repository_cases` reconstructs it exactly. Its basis must identify the selected source,
policy, complete selection and test interface. Authorship, assumptions, applicability and reasons are
**supplied data**, not authenticated review, policy truth or acceptance of concrete labels.

The closed schema requires 4–8 unique cases, exactly one designated regression and a nonblank reason
whose declared before response differs from desired after. Coverage names are owner, non-owner,
anonymous, normal-use and public. Each references existing cases or supplies a not-applicable reason;
normal-use must always reference a control. Explicit public coverage is supported without inferring
public intent from AST or a missing dependency. These are contract-test declarations, not a frozen
independent benchmark or newly maintainer-approved policy oracle.

Each case has one literal GET path and separate exact before/after response values. Bounds and
initial unsupported forms are explicit:

- Case document: at most 64 KiB; supplied phase frame: at most 64 KiB.
- Paths: at most 512 ASCII characters, a single leading slash, literal letters/digits and `/_.-`;
  reject `//`, dot segments, queries, fragments, percent encoding, backslashes and absolute URLs.
- Headers: only lowercase `x-user`, `x-user-id`, `x-role`; at most three values of at most 64 ASCII
  characters with the `test-` synthetic-token prefix. Host, Authorization, Cookie, proxy/framing headers,
  real credentials, request bodies, scripts, callbacks and redirects are unsupported. A prefix is a
  naming declaration, not secret detection or proof of synthetic identity.
- Expected status: 2xx or 4xx. Body: typed JSON or explicit empty; 204/205 require empty bodies.
  JSON is at most 4 KiB, depth 8, 128 value nodes, string values 1,024 UTF-8 bytes and keys 128 bytes.
  Integers are within ±(2^53−1); floats must be finite. Boolean, integer and float types stay distinct;
  object-key order is irrelevant. Duplicate JSON keys and unknown fields are rejected.

## Binding and observer projection

`build_repository_verification_plan(request, response, cases)` validates current `1.1` inputs and
binds the full request/response identities, selected before and proposed after hashes, generated-test
hash, interface and host-only cases. Valid non-change statuses return no plan. Case basis must match
the current input exactly. `validate_repository_verification_plan` reconstructs the complete plan
against all current inputs; rehashing edited metadata does not make it match.

`prepare_repository_observer_schedule(..., phase=...)` projects only plan ID, phase and GET request
records. No expected answers, source/test text, policy, regression reasons or authorship are included.
The plan remains private host data. Data flow is:

```text
v1.0 base request → opt-in v1.1 test-interface request (model view)
current request + proposal + independent cases → verification plan (host only)
plan + phase → request-only observer schedule
supplied frame + current plan/inputs → candidate and comparison (unverified)
```

Hashes bind declarations. They do not measure actual staged files, authenticate an observer or prove
that the named source/test ran. No v1.1 downgrade, imported result or comparison unlocks S2 writes.

## Supplied frames and honest comparison

`decode_repository_phase_candidate` checks a bounded `repository-supplied-phase` frame for the current
plan and before/after phase. Its echoed source/test/interface binding must match. Every planned case
must occur exactly once in schedule order, with either a typed response or one closed error code.
Typed observations can record 3xx/5xx, but comparisons mark those as errors; 304 also requires an
empty body. This codec does not parse raw HTTP/TCP headers, fragments or framing. Later transport
and observer code must establish those separate properties.

Pytest data has bounded exact integer counts, exit code and a supplied `failure_kind` of `assertion`,
`other` or `none`. Cleanup has exactly T/A/B states. Before candidate criteria require:

- Every response matches the declared before value, including the designated mismatch against desired
  after behavior.
- Nonzero collected tests, exactly one supplied assertion failure, all remaining tests passed, exit 1,
  no errors/skips/xfails/xpasses, and supplied confirmed cleanup for all three guests.

After candidate criteria require every declared after control, nonzero all-pass pytest counts,
exit 0, failure kind `none`, no errors/skips/xfails/xpasses and all supplied cleanup confirmed.
General exceptions, missing/invalid observations, setup/transport errors, timeout, server error or
unknown cleanup cannot meet these criteria. Pytest remains untrusted auxiliary data even when consistent.

`compare_repository_phase` validates the current plan/inputs **before** handling malformed frame data.
Valid frames retain each match/mismatch/error. An invalid frame retains every planned case as invalid,
with closed diagnostic codes and no raw-error echo. It never scores only an available subset.
`validate_repository_phase_candidate` reconstructs the supplied candidate and refuses promoted flags.

Even a fully matching result always has `evidence_basis: supplied-unverified`, execution `not-run`,
authorization `unknown`, `verified_fix: false`, `live_evidence: false` and `writes_authorized: false`.
`supplied_criteria_met` is a comparison of declarations only. A caller can fabricate matching responses,
pytest labels and cleanup; this does not reproduce a defect or establish a verified repair.

## Remaining product work

Separate T/A/B launchers, sealed selected-byte staging, raw HTTP observation, reviewed runtime images,
limits and directly returned live phase results remain unimplemented for external projects. Then bind
the CLI operator to those live results and S2 decisions, verify a bounded installed external flow,
implement separately reviewed original-project final correction and connect the shared GUI engine.
#152/#150 stay open. No account use, actual external-project run, risk acceptance, tag or release is
authorized or established by these pure contracts.
