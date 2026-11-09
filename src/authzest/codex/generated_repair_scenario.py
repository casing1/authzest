"""One maintained synthetic source/policy context, never imported or executed.

The demo actor header is caller-controlled test data, not authentication. The
policy below is assistant-authored and awaiting maintainer review; it is not an
independently approved reference set or observed endpoint behavior.
"""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from authzest.codex.contracts import ContractError
from authzest.parser.fastapi import FastAPIRouteParser

SCENARIO_ID = "owned-fastapi-document-ownership-v1"
SOURCE_PATH = "app.py"
TEST_PATH = "tests/test_generated_ownership.py"
SOURCE = '''"""Synthetic ownership demo. X-Demo-Actor is NOT authentication."""

from fastapi import Depends, FastAPI, Header, HTTPException

app = FastAPI()

DOCUMENTS = {
    "doc-alice": {"owner": "alice", "body": "Alice's synthetic document"},
    "doc-bob": {"owner": "bob", "body": "Bob's synthetic document"},
}


def current_actor(x_demo_actor: str | None = Header(default=None)) -> str:
    # Caller-selected fixture identity only: no credentials or real login.
    if x_demo_actor not in ("alice", "bob"):
        raise HTTPException(status_code=401, detail="Unknown demo actor")
    return x_demo_actor


@app.get("/documents/{document_id}")
def read_document(document_id: str, actor: str = Depends(current_actor)):
    document = DOCUMENTS.get(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    # Intentionally incomplete test-only ownership enforcement.
    return {"id": document_id, "owner": document["owner"], "body": document["body"]}
'''

POLICY = (
    "This is a maintained synthetic ownership-policy demo, not a production finding. "
    "X-Demo-Actor is caller-controlled fixture data, not authentication or a trusted identity.",
    "Under the fixed demo actor, alice and bob may read only their own existing document. "
    "An owner receives HTTP 200 with the existing id, owner and body values unchanged.",
    "A valid demo actor requesting another actor's existing document receives HTTP 403 "
    "without disclosing that document's id, owner or body in the response.",
    "A missing or unknown demo actor receives HTTP 401; a valid actor requesting a missing "
    "document receives HTTP 404. Preserve the existing route and principal-selection behavior.",
    "Propose a new defensive pytest regression test using in-memory FastAPI TestClient and "
    "model-authored repair source for app.py only. Do not add routes, credentials, services, "
    "network calls, filesystem access or alter fixture data. These are requested limits, "
    "not a guarantee that generated code obeys them.",
    "Source declarations and these proposed expectations are not runtime observations. "
    "Independent maintained controls and a separately reviewed execution boundary "
    "are still needed.",
)


def build_scenario_context() -> dict:
    """Return detached fixed bytes and in-memory declarations; paths are labels only."""
    root = Path("owned-fastapi-document-ownership")
    parsed = FastAPIRouteParser().parse_source(SOURCE, root / SOURCE_PATH)
    if parsed.error or parsed.diagnostics or len(parsed.routes) != 1:
        raise ContractError("Maintained generation scenario mismatch", code="validation-identity")
    declaration = parsed.routes[0].to_dict(root)
    if declaration["path"] != "/documents/{document_id}" or declaration["methods"] != ["GET"]:
        raise ContractError("Maintained generation route mismatch", code="validation-identity")
    return {
        "scenario_id": SCENARIO_ID,
        "source": {
            "path": SOURCE_PATH,
            "text": SOURCE,
            "sha256": sha256(SOURCE.encode("utf-8")).hexdigest(),
        },
        "test_path": TEST_PATH,
        "test_before": "absent-in-planned-copy",
        "policy": list(POLICY),
        "policy_authorship": "assistant",
        "policy_review": "pending-maintainer-review",
        "declarations": [declaration],
    }
