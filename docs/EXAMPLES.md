<p align="center">
  <strong>English</strong> ·
  <a href="i18n/EXAMPLES.ko.md">한국어</a>
</p>

# Source-only inventory example

[Documentation index](README.md) · [Installation](../README.md)

The maintained [FastAPI example](../examples/fastapi_inventory/) contains only fixed public sample data.
It demonstrates source discovery without starting a server, importing the application, contacting an
endpoint, or calling Codex. Use the current source checkout, not the older published alpha binary.

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

With the development environment active, verify the example using:

```bash
python -m pytest tests/test_examples.py
```

This is an inventory regression, not a labelled access-control evaluation set. It does not measure
vulnerability detection or establish that an application is safe. Known unsupported declarations can be
omitted; see the [parser scope](PARSER_SCOPE.md). The [model strategy](MODEL_STRATEGY.md) describes the
separate policy fixtures and comparisons needed before making AI or security-effectiveness claims.
