# FastAPI route discovery

[Documentation](README.md) · English · [한국어](i18n/PARSER_SCOPE.ko.md)

This guide describes the current source on `main`. Owner recognition, prefix composition,
repository-local imports, versioned registration evidence, and route-local dependency declarations are [`Unreleased`](../CHANGELOG.md#unreleased)
changes and are not included in
the published [v0.1.0-alpha.1 preview](https://github.com/casing1/authzest/releases/tag/v0.1.0-alpha.1).
Use a current source checkout to try these features; the package version has not yet been bumped from
`0.1.0a1`.

AuthZest parses Python source with the standard-library AST parser. It does not import the scanned
application, instantiate its objects, or execute its code. The supported syntax is tested on Python 3.12.
Both single-file and repository parsing read source bytes and let Python interpret UTF-8, a UTF-8 byte
order mark (BOM), and PEP 263 source-encoding declarations such as `# coding: latin-1`. Invalid byte
sequences, unknown encodings, and conflicting BOM/encoding declarations are reported as parse errors.
Repository scans continue with other readable, valid source files.

## Supported declarations

Routes must belong to an object constructed directly from a recognized FastAPI import. Single-file
discovery recognizes local declarations; repository scans also connect supported imports between indexed
source files:

```python
from fastapi import FastAPI, APIRouter as Router

app = FastAPI()
router = Router()


@app.get("/health")
def health():
    return {"status": "ok"}


@router.post("/users")
async def create_user():
    pass
```

`import fastapi`, `import fastapi as fa`, and annotated assignments such as
`router: Router = Router()` are also supported. An annotation alone does not create an object.

Supported decorators are lowercase `get`, `post`, `put`, `patch`, `delete`, `options`, and `head`, with
exactly one positional argument containing a literal string. A `path=` keyword or expanded `**kwargs`
prevents that declaration from being resolved. Both synchronous and asynchronous functions and
multiple supported decorators on one function are collected. Each route retains its method, function
name, file, and one-based function-definition line number.

Straight-line function-local construction is supported, including this common application-factory shape:

```python
from fastapi import FastAPI


def create_app():
    app = FastAPI()

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app
```

Discovery describes source declarations; it does not prove that a factory is called or that a router is
mounted in a running application. Only stable enclosing bindings are inherited by function bodies.
Parameters, local declarations, reassignment, deletion, and potentially conflicting conditional writes
invalidate ownership. An unrelated `@cache.get(...)` is therefore not classified by its method name alone.

## Same-file router prefixes and registration

Literal `APIRouter(prefix=...)` and `include_router(..., prefix=...)` values are composed for supported
straight-line declarations in the same scope:

```python
from fastapi import APIRouter, FastAPI

app = FastAPI()
users = APIRouter(prefix="/users")


@users.get("/me")
def current_user():
    pass


app.include_router(users, prefix="/api")
app.include_router(router=users, prefix="/internal")
```

This reports `/api/users/me` and `/internal/users/me`, both pointing to the original `current_user`
definition. The unregistered `/users/me` entry is not duplicated. Repeated registrations are preserved,
even if their resulting paths match. Nested same-file router inclusions are supported when the child
declarations and inclusions precede the parent inclusion.

Prefixes are concatenated exactly, without slash normalization. An omitted prefix means an empty string;
a nonempty prefix must start with `/` and must not end with `/`. Only literal strings are resolved. Dynamic
values, invalid prefixes, and expanded `**kwargs` are not guessed. `FastAPI(prefix=...)` is not treated as
an APIRouter prefix.

A standalone router that is never included remains in the source inventory with its constructor prefix.
Once a known router is referenced by an inclusion, its raw declaration entries are suppressed. A resolvable
registration still appears even if another registration is unresolved; a router with only unresolved
registrations contributes no guessed path. These entries remain source evidence, not a guarantee of
deployment or reachability.

Only routes and nested inclusions already declared before an inclusion are composed. Late additions are
omitted from that registration. This is a conservative supported subset, not a simulation of every FastAPI
version's runtime behavior. Arbitrary mutations after inclusion and cross-scope composition remain deferred.
Function-local declarations are analyzed in isolation; parsing a function does not apply its side effects
to enclosing routers.

For framework usage examples, see [FastAPI's router composition guide](https://fastapi.tiangolo.com/tutorial/bigger-applications/).

## Repository-local imports

Repository scans build a module index from the selected source tree and its conventional `src/` directory.
Only indexed Python files participate. Resolution does not use the interpreter's import machinery,
installed packages, `sys.path`, or network access, and symlinked files or directories are excluded.
Within the selected root, the normal scan excludes source files beneath descendant directories named
`.git`, `.mypy_cache`, `.pytest_cache`, `.ruff_cache`, `.venv`, `__pycache__`, `dist`, `node_modules`, or
`venv`. The explicit scan root and its ancestors are not tested against that name list: choosing a root
named `dist`, or a project below a parent named `dist`, still scans its eligible source files. A nested
`dist` directory inside that root remains excluded. Excluded files cannot become candidates merely
because another source file imports them. The index also supports namespace packages represented by the
indexed source tree; an `__init__.py` is not required for every directory.

For example, a router in `app/routers/users.py`:

```python
from fastapi import APIRouter

router = APIRouter(prefix="/users")


@router.get("/me")
def current_user():
    pass
```

can be registered from `app/main.py`:

```python
from fastapi import FastAPI
from .routers.users import router as users_router

app = FastAPI()
app.include_router(users_router, prefix="/api")
```

The result is `/api/users/me`, with its file and line pointing to `current_user` in `app/routers/users.py`.
The raw `/users/me` declaration is not emitted again merely because the router file is also scanned.

Supported imports are module-level, static absolute or package-relative imports. They include direct
router imports, import aliases, module references such as `from app.routers import users` followed by
`users.router`, and import-based reexports through `__init__.py`. Nested registrations and repeated mounts
share router identities across the module cache. Separate registrations remain separate results.

An explicit dotted import such as `import app.routers.users` can be followed by
`app.routers.users.router`. A package initializer can reexport a child with `from . import users` or
reexport the router directly with `from .users import router`. Importing only `app` does not imply that
every submodule exists as an attribute: the child must be explicitly imported or statically reexported.
If a package explicitly assigns an unknown value to `users`, `from app import users` does not guess that
it means the sibling `users.py` module.

Source files and completed module analysis are cached within each scan. A later scan reads fresh source,
and report ordering does not depend on file creation order. If the root and `src/` offer conflicting
candidates for the same module name, or a file conflicts with a same-named package, the import remains
unresolved. Modules in an import cycle do not expose partial router exports.

Missing modules, conflicting module names, cyclic imports, wildcard imports, and dynamic imports are not
resolved by guessing. A local module named `fastapi` is not silently treated as the installed framework.
Imports cannot expand the scan beyond its indexed file set. Unsupported imports may leave standalone
declarations in the inventory, but do not establish an application registration or a security verdict.

Cross-file composition currently connects completed module-level declarations. Registering additional
decorators onto an imported router, using imported owners as mutable parent routers, and resolving router
imports inside deferred function bodies remain outside this subset. Existing function-local analysis
continues in isolation. The standalone `parse_file` entry point remains a single-file operation.

The supported syntax follows [Python's import forms](https://docs.python.org/3.12/reference/import.html#package-relative-imports),
but AuthZest does not simulate all runtime import behavior.

## Route-local dependency declarations

For a supported route, the parser records direct `Depends` and `Security` calls in parameter defaults,
inline `Annotated` metadata, and the route decorator's literal `dependencies` list. These are declaration
facts, not authentication/authorization classifications. For example:

```python
from typing import Annotated
from fastapi import Depends, FastAPI, Security

app = FastAPI()


@app.get("/items", dependencies=[Depends(trace_request)])
def items(
    page: Annotated[dict, Depends(pagination)],
    context=Security(example_context, scopes=["items:read"]),
):
    pass
```

The snippet illustrates declaration syntax only: target names are not defined here and the parser does
not look up or execute those callables. A simple or dotted target name can be `reference` even when it
is missing at runtime. General-purpose DI is recorded in the same way as security-related names;
`Security`, a scope string, or a function called `get_current_user` is not proof of access control.
The maintained [dependency example](EXAMPLES.md) supplies ordinary sample functions and expected output.

Supported factory imports include `from fastapi import Depends as D, Security as S`, `import fastapi`,
and `import fastapi as fa`. Inline `Annotated` is recognized through `typing` or `typing_extensions`,
including direct-import and module aliases. Binding changes and shadowing are respected; a user-defined
object named `Depends` is not identified by spelling alone. Repository analysis also respects locally
shadowed framework/typing modules and supported import reexports. Target-callable import resolution is
not part of this feature.

Python 3.12 function type parameters shadow names in that function's annotations and body, but not its
parameter defaults or decorators. These contexts use separate bindings during source analysis; this is
not runtime evaluation of a type parameter or annotation.

Parameter evidence covers positional-only, ordinary, and keyword-only defaults, plus direct recognized
metadata on inline parameter annotations. Only metadata after the first `Annotated` type argument is a
dependency site. Multiple direct dependency declarations for one parameter are preserved as unresolved,
not assigned a guessed runtime precedence. Known dependency-bearing type aliases and nested annotations
are diagnosed but not expanded; string annotations are not evaluated.
Alias diagnostics are bounded to recognized `Annotated` values in simple/annotated assignments or
Python 3.12 type aliases, and simple rebinding of an already known alias. They do not discover every
alias or recursive type expression. A plain dependency call in the first type argument is not metadata;
a recognized nested dependency-bearing `Annotated` there is diagnosed without expansion.

Decorator `dependencies` accepts a literal list, an empty list, or `None`. Recognized direct entries are
collected; dynamic collections, expanded/unknown entries, and repeated arguments receive diagnostics.
Each stacked decorator receives the common parameter evidence and only its own decorator dependencies.
Records are ordered by original source line and UTF-8 byte column. Same-file and cross-file mounts retain
that original route-local evidence; app/router/include dependencies are not inherited yet.

The target may be one positional argument or `dependency=...`. Simple/dotted names are accepted syntax;
implicit or `None` targets, factory calls, lambdas, and other dynamic targets are unresolved. Expressions
are normalized with the AST, never executed. Expanded, duplicate, unknown, or extra positional arguments
are unresolved. `use_cache` and the `Depends` `scope` keyword are accepted without interpreting their
runtime behavior. `Security` scopes are known only for a literal list of strings, omitted scopes, or
explicit `None`; omission/`None` mean an empty list. Dynamic or invalid scopes remain null with a reason.
The route itself is retained when only dependency evidence is partial.

This bounded syntax is informed by FastAPI's [dependency reference](https://fastapi.tiangolo.com/reference/dependencies/),
[dependency tutorial](https://fastapi.tiangolo.com/tutorial/dependencies/), and
[decorator dependency guide](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-in-path-operation-decorators/).
AuthZest does not reproduce every framework or Python runtime behavior.

## Registration evidence and diagnostics

The shared report uses `schema_version: "1.1"`. This report-schema version is independent of the
Python package and release version. Existing route fields and `parse_errors` remain available;
`analysis_status`, `diagnostics`, and each route's `registration_id` and `registration` were added in
1.0; 1.1 adds each route's `dependencies` without changing the registration-ID hash.
The [report contract](REPORT_CONTRACT.md) defines their representation and compatibility rules.

Every route produced by the parser records its original decorator and owner-constructor locations.
Resolved mounts also record the application owner when known and each `include_router` site, including
the parent owner, child router, and literal include prefix. The include chain runs from the outermost
registration (application or router) toward the innermost router. A standalone router can have a nonempty
chain with no application owner. The existing route `file` and `line` still identify the original
handler definition, not the mount site. New location fields use repository-relative POSIX paths in
report JSON, one-based lines, and one-based UTF-8 byte columns; an unavailable position is `null`.

Registration IDs are deterministic for unchanged source evidence within the same relative layout.
Separate applications, stacked decorators, and repeated mounts remain distinct even when paths and
HTTP methods match, including multiple mount calls on one line. IDs identify source registrations,
not runtime objects, complete source-content hashes, or approval tokens. Moving a declaration or
changing its recorded registration evidence can change its ID.

Function-body inventory is marked `execution_scope: "deferred"`; module-level inventory uses
`"module"`. An inherited owner keeps its original constructor location. Neither marker proves that
execution reaches the declaration or that the resulting route is deployed.

Diagnostics contain a reason `code`, explanatory `message`, original `location`, and `severity`.
The bounded parser reports these known cases without expanding the supported discovery syntax:

- `source-read-error`, `source-parse-error`, and `source-decode-error` identify source-loading failures.
  Existing `parse_errors` text is retained alongside these error diagnostics.
- `unsupported-owner-construction` identifies a recognized constructor whose arguments or prefix
  cannot be resolved.
- `dynamic-route-path`, `unsupported-route-arguments`, `unsupported-route-expression`, and
  `unsupported-route-owner` describe unresolved declarations on recognized route owners.
- `dynamic-include-prefix`, `unsupported-include-arguments`, `unsupported-include-context`,
  `unresolved-include-owner`, and `include-cycle` describe known unsupported inclusion attempts.
- `conditional-registration` marks a known-owner route declaration in unsupported control flow.
- `unsupported-dependency-list` covers a nonliteral or repeated decorator dependency collection;
  `unsupported-dependency-entry` covers an entry that is not a recognized direct dependency call.
- `unsupported-dependency-expression`, `unsupported-dependency-annotation`, and
  `unsupported-dependency-metadata` cover known dependency calls in unsupported default/annotation shapes
  and known dependency-bearing aliases that are not expanded.
- `unsupported-dependency-arguments` covers expanded, duplicate, extra positional, or unknown call arguments.
  `unresolved-dependency-target` marks an implicit or non-name target; `dynamic-security-scopes` marks scopes
  that cannot be represented as a known string list. `ambiguous-dependency-declaration` marks multiple
  direct declarations for one parameter without guessing which one the framework would select.

For example, an import cycle can leave the child of a recognized app's `include_router` unresolved;
the diagnostic points to that include call rather than claiming the import succeeded. Arbitrary
unknown `.get(...)` receivers and unrelated imports do not produce framework diagnostics merely
because of their names. Diagnostics are not an exhaustive list of every unsupported Python pattern.
Dependency diagnostics are warnings and make the report partial even when the route path remains known.
Calls that produce an evidence entry also retain their reason codes in `unresolved_reasons`; a dynamic
collection or unsupported nested annotation can instead produce a diagnostic with no dependency entry.
Scope diagnostics do not assert an OAuth failure, and an empty dependency list is not a public-route label.

## Deferred patterns and interpretation

- Runtime import hooks, external package resolution, wildcard imports, and ambiguous or cyclic modules.
- Cross-scope router composition and additions or mutations after inclusion.
- Instance or constructor aliases assigned through other variables, factory-call result inference,
  subclasses, and owners stored in attributes or containers.
- Routes inside class bodies, conditions, loops, `try`, or `with` blocks. These blocks can still invalidate
  earlier bindings when they write to a relevant name.
- Function bodies using `global` or `nonlocal`, assignment expressions in route declarations, and runtime
  mutation through arbitrary calls or reflection.
- Keyword-only `path=`, computed paths, `api_route`, `add_api_route`, and WebSocket declarations.
- Application/router/include dependency inheritance, nested dependency graphs, target-callable resolution,
  runtime overrides, authentication or authorization decisions, and security findings.

Unsupported or unresolved route declarations are omitted from the route inventory; supported routes with
unresolved dependency evidence remain with diagnostics. They are not labelled
protected, unprotected, or vulnerable. A report with diagnostics or parse errors has
`analysis_status: "partial"`; otherwise its status is `"bounded"`, never a claim of complete analysis.
An empty result, an empty diagnostic list, or a successful exit must not be interpreted as proof that
no endpoints exist or that access control is safe.

The text CLI prints diagnostic details to stderr and identifies partial inventory; JSON retains the
legacy `parse_errors` array alongside structured diagnostics. Default scans still return exit code 0
when a report is produced, including a partial report. With `--strict`, a partial report is still
printed but returns exit code 1. Invalid repository input returns exit code 2. The local scan API
returns HTTP 200 for a produced partial report; callers inspect `analysis_status` and `diagnostics`.
See the [report contract](REPORT_CONTRACT.md) for the full output and exit-code policy.

Regression cases live in [`test_parser.py`](../tests/test_parser.py),
[`test_router_prefixes.py`](../tests/test_router_prefixes.py),
[`test_cross_file_routes.py`](../tests/test_cross_file_routes.py), and
[`test_source_encodings.py`](../tests/test_source_encodings.py), and
[`test_report_parser.py`](../tests/test_report_parser.py), with CLI, API, and repository-runner
fixtures covering the shared report contract. Route-local dependency transport cases live in
[`test_dependency_transports.py`](../tests/test_dependency_transports.py). No FastAPI version compatibility claim beyond this
source-syntax subset is made. For the release process, see [Releasing AuthZest](RELEASING.md).
