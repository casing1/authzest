"""Maintainer-authored sample for a legitimate owner's archived-note read."""


def test_owner_can_read_archived_note(owner_client):
    response = owner_client.get("/records/archived-note")
    assert response.status_code == 200
