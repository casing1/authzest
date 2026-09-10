<p align="center">
  <strong>English</strong> ·
  <a href="i18n/EXAMPLES.ko.md">한국어</a>
</p>

# Source-only inventory examples

[Documentation index](README.md) · [Installation](../README.md)

The maintained examples contain only fixed public sample data.
They demonstrate source discovery without starting a server, importing the application, contacting an
endpoint, or calling Codex. Use the current source checkout, not the older published alpha binary.

## Route registration example

The [registration example](../examples/fastapi_inventory/) covers cross-file and repeated router mounts.
After installing the CLI as described in the project README, run from the repository root:

```bash
authzest scan examples/fastapi_inventory
authzest scan examples/fastapi_inventory --json
```

Expected inventory: **4 Python files, 3 routes, no parse errors, Codex disabled**.

| Method | Path              | Original declaration     |
| ------ | ----------------- | ------------------------ |
| GET    | /health           | app/main.py:11           |
| GET    | /v1/catalog/items | app/routers/catalog.py:9 |
| GET    | /v2/catalog/items | app/routers/catalog.py:9 |

The imported router has its own prefix and is registered twice. Both mounted routes retain the same
original handler location. These are source locations, not deployment URLs or proof that the app was run.
The exact JSON regression expectation is [stored separately](../tests/fixtures/fastapi_inventory.json);
In [the test](../tests/test_examples.py), the machine-specific scan root is excluded and route path
separators are normalized to POSIX style before comparison.
The current schema is 1.1; all three routes have `dependencies: []` because this fixture has no supported
route-local dependency declarations. This is not an authentication or authorization classification.

With the development environment active, verify the example using:

```bash
python -m pytest tests/test_examples.py
```

## Route-local dependency example

The [dependency example](../examples/fastapi_dependencies/) demonstrates three supported declaration sites.
From the repository root with the current source CLI installed:

```bash
authzest scan examples/fastapi_dependencies
authzest scan examples/fastapi_dependencies --json --strict
```

Expect **1 Python file, 2 GET routes, bounded analysis, no diagnostics, Codex disabled**, and exit code 0.
`/health` has an empty dependency list. `/items` records these declarations in source order:

| Kind       | Target            | Declaration level      | Parameter | Scopes           |
| ---------- | ----------------- | ---------------------- | --------- | ---------------- |
| `Depends`  | `trace_request`   | `decorator`            | null      | null             |
| `Depends`  | `pagination`      | `parameter-annotation` | `page`    | null             |
| `Security` | `example_context` | `parameter-default`    | `context` | `["items:read"]` |

All three targets have `resolution: "reference"`, meaning simple-name syntax, not proof of callable behavior.
The sample functions return fixed data or ordinary dependency-injection values. They do not enforce
authentication or authorization; even the `Security` declaration and scope string are not protection guarantees.
The [transport regressions](../tests/test_dependency_transports.py) check source positions, shared
core/CLI/API output, and separate dynamic-scopes cases that return a partial report and strict exit code 1.
The [report contract](REPORT_CONTRACT.md) defines each dependency field and null/empty distinctions.

These are inventory regressions, not a labelled access-control evaluation set. They do not measure
vulnerability detection or establish that an application is safe. Known unsupported declarations can be
omitted; see the [parser scope](PARSER_SCOPE.md). The [model strategy](MODEL_STRATEGY.md) describes the
separate policy fixtures and comparisons needed before making AI or security-effectiveness claims.
