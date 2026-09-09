# FastAPI route discovery

[Documentation](README.md) · English · [한국어](i18n/PARSER_SCOPE.ko.md)

This guide describes the current source on `main`. Owner recognition, prefix composition, and
repository-local imports are [`Unreleased`](../CHANGELOG.md#unreleased) changes and are not included in
the published [v0.1.0-alpha.1 preview](https://github.com/casing1/authzest/releases/tag/v0.1.0-alpha.1).
Use a current source checkout to try these features; the package version has not yet been bumped from
`0.1.0a1`.

AuthZest parses Python source with the standard-library AST parser. It does not import the scanned
application, instantiate its objects, or execute its code. The supported syntax is tested on Python 3.12.

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
The normal scan excludes `.git`, `.mypy_cache`, `.pytest_cache`, `.ruff_cache`, `.venv`, `__pycache__`,
`dist`, `node_modules`, and `venv`. These files cannot become candidates merely because another source
file imports them. The index also supports namespace packages represented by the indexed source tree;
an `__init__.py` is not required for every directory.

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
- Dependency collection, authentication or authorization decisions, and security findings.

Unsupported or unresolved declarations are omitted from the route inventory. They are not labelled
protected, unprotected, or vulnerable. The report schema is unchanged and does not yet expose an explicit
unresolved-declaration list, so an empty result must not be interpreted as proof that no endpoints exist
or that access control is safe. Malformed or unreadable source continues to appear in `parse_errors`.

Regression cases live in [`test_parser.py`](../tests/test_parser.py),
[`test_router_prefixes.py`](../tests/test_router_prefixes.py), and
[`test_cross_file_routes.py`](../tests/test_cross_file_routes.py), with CLI, API, and repository-runner
fixtures covering the shared report contract. No FastAPI version compatibility claim beyond this
source-syntax subset is made. For the release process, see [Releasing AuthZest](RELEASING.md).
