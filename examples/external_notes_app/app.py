"""Synthetic notes service with a deliberate object-ownership defect.

Copy this folder outside the repository before running repo-fix on it.
Identities are synthetic test headers, not a real authentication system.
"""

from fastapi import FastAPI, Header, HTTPException

app = FastAPI()

NOTES = {
    1: {"id": 1, "owner": "test-alice", "text": "Alice's synthetic note"},
    2: {"id": 2, "owner": "test-bob", "text": "Bob's synthetic note"},
}


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/notes/{note_id}")
def read_note(note_id: int, x_user: str | None = Header(default=None)):
    if x_user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    note = NOTES.get(note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="Not found")
    return note
