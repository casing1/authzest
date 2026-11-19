"""Independent policy expectations for the installed synthetic owner-read fixture."""

import asyncio

import httpx

from authzest.owner_read_demo import availability
from authzest.owner_read_demo.app import create_app, current_principal
from authzest.owner_read_demo.checks import compare_owner_read_observations, owner_read_controls


def test_only_the_owner_archived_read_differs_from_policy(monkeypatch):
    visited_states = []
    baseline = availability.available_to_owner

    def observe(state):
        visited_states.append(state)
        return baseline(state)

    monkeypatch.setattr(availability, "available_to_owner", observe)
    app = create_app()
    actors = {"owner": lambda: "owner", "other": lambda: "other"}
    observations = []

    async def request(record_id):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get(f"/records/{record_id}")

    for case in owner_read_controls():
        actor, record_id = case["principal"], case["record_id"]
        app.dependency_overrides.clear()
        if actor is not None:
            app.dependency_overrides[current_principal] = actors[actor]
        visited_states.clear()
        response = asyncio.run(request(record_id))
        if actor == "owner" and record_id != "missing-note":
            assert visited_states == [record_id.removesuffix("-note")]
        else:
            assert visited_states == []
        observations.append(
            {
                "case_id": case["case_id"],
                "status_code": response.status_code,
                "body": response.json(),
            }
        )

    result = compare_owner_read_observations(observations)
    assert result["status"] == "compared"
    assert result["matches_before_profile"] is True
    assert result["matches_intended_policy"] is False
    assert result["intended_matches"] == 6
    assert [r["case_id"] for r in result["checks"] if not r["intended_match"]] == ["owner-archived"]
