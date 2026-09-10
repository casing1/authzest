<p align="center">
  <strong>English</strong> ·
  <a href="i18n/MODEL_STRATEGY.ko.md">한국어</a>
</p>

# Model strategy and evaluation

[Documentation index](README.md) · [Development plan](DEVELOPMENT_PLAN.md)

## Decision

Keep the installable CLI and the existing core/adapter boundary. Do not rewrite the product around a
particular GPT release. AuthZest's proposed value is repeatable source evidence, explicit policy
expectations, reviewable explanations, and measured limitations. Whether this helps more than giving
the same task directly to a model is a hypothesis to test, not an established advantage.

The current product inventories a bounded subset of FastAPI routes. It does not yet collect dependency
evidence, determine authorization correctness, or run an AI adapter. The [source-only example](EXAMPLES.md)
is a parser regression/demo, not a security benchmark.

## Stable contracts, replaceable models

| Layer                   | Responsibility                                                                                 | Must not imply                                                  |
| ----------------------- | ---------------------------------------------------------------------------------------------- | --------------------------------------------------------------- |
| Parser and analyzer     | Deterministic declarations, original locations, supported registration context                 | Complete understanding of arbitrary Python                      |
| Policy and report       | Separate observed facts, user-specified expectations, unresolved evidence, and eventual checks | A dependency declaration proves authentication or authorization |
| Optional adapter        | Explain a deliberately selected evidence payload; validate response shape and references       | A model's unsupported assertion becomes a confirmed finding     |
| CLI and optional API/UI | Present the same core report and honest failure/partial states                                 | Successful execution or zero routes is a security pass          |

Do not expand the parser into a general Python interpreter. Add syntax support only when a documented
use case and maintained fixtures justify it. Repeated mounts need distinct registration identity and
application/include-site provenance; a URL path or a handler location alone cannot identify their context.
Record known unresolved cases without claiming every unsupported construct can be discovered.

The next prerequisite is [#32: report and registration contract](https://github.com/casing1/authzest/issues/32),
then [#28: route-local declarations](https://github.com/casing1/authzest/issues/28) and
[#29: inherited declarations](https://github.com/casing1/authzest/issues/29).
Keep versioning, diagnostics, deterministic ordering, compatibility, and CLI exit behavior explicit.
Current parse errors can still accompany exit code 0; this document does not implement the future contract.

## AI boundary before a live integration

Start with [#33: evidence-linked explanations and offline evaluation](https://github.com/casing1/authzest/issues/33).
Define a minimal evidence payload and mock adapter tests before choosing one live integration.
No provider call, credentials, subscription, or paid model is required by the default scan or CI.

For a later opt-in adapter, require explicit data-sharing approval and inspect the permitted input scope.
Repository text is untrusted data, not instructions granting the model tools or access. Minimize source
content, handle secrets, and define timeout, cancellation, malformed output, unavailable-provider, and
unsupported-reference behavior. A local report must survive adapter failure.

Validate each explanation against the supplied evidence identifiers and keep inferred policy separate
from human-declared policy. Public endpoints and ordinary dependency injection are legitimate cases;
missing recognizable authorization evidence is not by itself a vulnerability.

Make provider/model selection configurable when an adapter exists. Record the exact returned model
identifier, prompt/adapter/report versions, source revision or content identity, permitted input manifest,
and actual usage and latency when available. Do not silently substitute a newer model or invent missing
usage data. Keep sensitive source and credentials out of telemetry. CLI and App Server are integration
options behind the interface, not parallel implementations required for this term project.

## Test the product hypothesis

Before tuning prompts, freeze a small, human-reviewed set of owned local fixtures and expected policy
labels. Include ordinary DI, intentionally public routes, relevant access-control declarations, repeated
mounts, incomplete inputs, and unsupported patterns. Keep the expected answers out of model input and
reserve held-out cases for evaluation rather than prompt development.

Compare three modes on the same task and permitted source/policy scope:

1. Static evidence without AI.
2. A model given the permitted source and policy directly, without AuthZest's extracted evidence.
3. The same model given that scope plus AuthZest's evidence.

Keep the model and task instructions comparable between the two AI modes, document any unavoidable
input differences, and record actual token usage rather than claiming equal cost. Run repeated trials
for the nondeterministic modes. A static-only mode may abstain from explanation tasks; report task
coverage separately from correctness instead of scoring an abstention as a correct answer.

Measure route/declaration correctness and coverage, valid source citations, unsupported claims, policy
agreement, unresolved outcomes, repeated-run variation, latency, actual usage, and human review effort.
Report denominators, fixture limitations, and representative errors alongside any aggregate score.
More routes or fewer unknowns alone do not establish better security analysis. Keep inventory fixtures
separate from the later labelled policy evaluation set.

A small comparison can begin after the evidence contract and initial dependency fixtures; a complete
deterministic finding engine is not a prerequisite. If the evidence-assisted mode does not help, narrow
the claim or revise the workflow rather than adding more agent autonomy.

## Evidence for this design

Official documentation reviewed on 2026-09-10: model capabilities and recommendations change, so model
selection belongs at a replaceable boundary. This is our architectural inference, not a demonstrated
AuthZest performance result. [OpenAI model guide](https://developers.openai.com/api/docs/guides/latest-model).

Task-specific datasets, expert labels, explicit metrics, comparisons, and repeat evaluation inform the
evaluation process above. [OpenAI evaluation guidance](https://developers.openai.com/api/docs/guides/evaluation-best-practices).

App Server documents an interface and managed authentication flow that can be evaluated later; reading
those docs does not enable the adapter or grant permission to send repository data.
[Codex App Server documentation](https://learn.chatgpt.com/docs/app-server).
