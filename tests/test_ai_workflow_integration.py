"""Real guarded API/core/copy flow with a scripted adapter and fake guest evidence."""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from pathlib import Path

import httpx
import pytest

from authzest.api._owner_read_controller import OwnerReadUIController
from authzest.api.app import create_app
from helpers.fake_owner_read_ui import core_workflow


@pytest.mark.skipif(os.name != "posix", reason="Private core copy workflow is POSIX source-only")
@pytest.mark.parametrize("choice", ["approve", "decline-after", "cancel-after"])
def test_guarded_api_drives_existing_core_and_preserves_exact_copy_outcome(
    choice, monkeypatch, tmp_path
):
    controller = OwnerReadUIController(
        Path("/inert/runtime.json"), workflow=core_workflow(monkeypatch, tmp_path)
    )
    origin, token = "http://127.0.0.1:8769", "t" * 43
    application = create_app(ai_controller=controller, ai_origin=origin, ai_token=token)

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=application),
            base_url=origin,
            headers={"X-AuthZest-Token": token, "Origin": origin},
        ) as client:
            response = await client.post("/api/ai/runs", json={"model": "offline-http-core"})
            assert response.status_code == 202
            run_id = response.json()["run_id"]
            url = f"/api/ai/runs/{run_id}"
            stages, prompts = [], set()
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                response = await client.get(url)
                assert response.status_code == 200
                value = response.json()
                if value["state"] in ("finished", "failed"):
                    break
                prompt = value["pending"]
                if prompt is not None and prompt["prompt_id"] not in prompts:
                    prompts.add(prompt["prompt_id"])
                    stage = prompt["stage"]
                    stages.append(stage)
                    if stage == "after" and choice == "cancel-after":
                        response = await client.post(url + "/cancel", json={})
                    else:
                        phrase = re.match(r"Type '([^']+)'", prompt["prompt"]).group(1)
                        response = await client.post(
                            url + "/decisions",
                            json={
                                "prompt_id": prompt["prompt_id"],
                                "answer": ""
                                if stage == "after" and choice == "decline-after"
                                else phrase,
                            },
                        )
                        replay = await client.post(
                            url + "/decisions",
                            json={"prompt_id": prompt["prompt_id"], "answer": phrase},
                        )
                        assert replay.status_code == 409
                    assert response.status_code == 202
                await asyncio.sleep(0.005)
            else:
                pytest.fail("Guarded UI workflow did not finish within the test budget")
            assert value["state"] == "finished", value
            response = await client.get(url + "/result")
            assert response.status_code == 200
            assert "attachment" in response.headers["content-disposition"]
            return stages, value, response.content

    try:
        stages, snapshot, raw = asyncio.run(run())
        result = json.loads(raw)
        workflow = result["file_workflow"]
        assert result["application_turn_attempts"] == 1  # Scripted adapter call, not a model call.
        assert stages[:7] == ["runtime", "share", "copy", "before", "diff", "apply", "after"]
        source = Path(workflow["copy"]["path"]) / "availability.py"
        if choice == "cancel-after":
            assert stages[-1] == "after"
            assert workflow["recovery_required"] is True
            assert workflow["workspace_state"] == "applied-after"
            assert source.read_text() == result["proposal"]["source"]
            assert snapshot["view"]["summary"]["recovery_required"] is True
        else:
            assert stages[-1] == "restore"
            assert workflow["recovery_required"] is False
            assert workflow["workspace_state"] == "restored-before"
            assert source.read_text() == result["source_evidence"]["source"]["text"]
            assert snapshot["view"]["summary"]["recovery_required"] is False
        if choice == "approve":
            assert workflow["status"] == "completed"
            assert (
                snapshot["view"]["session"]["checks"]["after"]["comparison"]["intended_match_count"]
                == 7
            )
        else:
            assert workflow["after"] is None
            assert workflow["stages"]["after"]["guest_dispatch_started"] is False
        assert result["original_checkout_modified"] is False
    finally:
        assert controller.close(timeout_seconds=3)
