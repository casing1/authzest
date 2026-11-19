"""Independent policy expectations for the installed synthetic owner-read fixture."""

import asyncio

import httpx

from authzest.owner_read_demo import availability
from authzest.owner_read_demo.app import create_app, current_principal


def test_only_the_owner_archived_read_differs_from_policy(monkeypatch):
    # The baseline is deliberately too strict. Pending records must stay unavailable.
    policy = (
        ("owner", "active-note", 200),
        ("owner", "archived-note", 200),
        ("other", "active-note", 403),
        ("other", "archived-note", 403),
        (None, "active-note", 401),
        ("owner", "missing-note", 404),
        ("owner", "pending-note", 403),
    )
    allowed_titles = {"active-note": "Active note", "archived-note": "Archived note"}
    errors = {401: "Authentication required", 403: "Read denied", 404: "Record not found"}

    visited_states = []
    baseline = availability.available_to_owner

    def observe(state):
        visited_states.append(state)
        return baseline(state)

    monkeypatch.setattr(availability, "available_to_owner", observe)
    app = create_app()
    actors = {"owner": lambda: "owner", "other": lambda: "other"}
    mismatches = []

    async def request(record_id):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get(f"/records/{record_id}")

    for actor, record_id, expected_status in policy:
        app.dependency_overrides.clear()
        if actor is not None:
            app.dependency_overrides[current_principal] = actors[actor]
        visited_states.clear()
        response = asyncio.run(request(record_id))
        if actor == "owner" and record_id != "missing-note":
            assert visited_states == [record_id.removesuffix("-note")]
        else:
            assert visited_states == []
        if response.status_code == 200:
            assert expected_status == 200
            assert response.json() == {"id": record_id, "title": allowed_titles[record_id]}
        else:
            assert response.json() == {"detail": errors[response.status_code]}
        if response.status_code != expected_status:
            mismatches.append((actor, record_id, expected_status, response.status_code))

    assert mismatches == [("owner", "archived-note", 200, 403)]
