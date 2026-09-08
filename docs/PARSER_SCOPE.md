# FastAPI route discovery

AuthZest parses Python source with the standard-library AST parser. It does not import the scanned
application, instantiate its objects, or execute its code. The supported syntax is tested on Python 3.12.

## Supported declarations

Routes must belong to an object constructed directly from an absolute FastAPI import in the same file:

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

Supported decorators are lowercase `get`, `post`, `put`, `patch`, `delete`, `options`, and `head`, with a
literal string as their first positional argument. Both synchronous and asynchronous functions and
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

## Deferred patterns and interpretation

- Router prefixes and `include_router` composition: paths currently remain exactly as declared.
- Cross-file imports, relative imports, and resolution of which installed module an import loads.
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

Regression cases live in `tests/test_parser.py`, with CLI, API, and repository-runner fixtures covering the
shared report contract. No FastAPI version compatibility claim beyond this source-syntax subset is made.
