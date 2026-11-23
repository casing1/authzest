"""Scripted core workflow for UI tests and local developer verification.

Only test/developer callers inject this factory. Production code does not import
it. It uses inert temporary files, a fake adapter and supplied fake guest results.
"""

from __future__ import annotations


def core_workflow(monkeypatch, tmp_path):
    from authzest.runner import _owner_read_copy_files, _owner_read_workflow
    from authzest.runner.owner_read_suggestion import run_suggestion
    from test_owner_read_file_session import SOURCE, TEST, evidence

    class Runtime:
        def __init__(self, _):
            pass

        def to_dict(self):
            return {"image_trust": "scripted-test-only"}

        def review_dict(self):
            return self.to_dict()

        def check(self):
            return None

        def close(self):
            return None

    class Dispatcher:
        def __init__(self, _):
            pass

        def preflight(self, *, guard):
            guard()
            return {"status": "ready", "cleanup_confirmed": True}

        def __call__(self, capture, *, guard):
            guard()
            return evidence(capture)

        def observations(self):
            return []

    class Adapter:
        async def suggest_owner_read(self, request):
            return {
                "request_id": request.request_id,
                "status": "proposed-change",
                "rationale": "Scripted test response.",
                "source": SOURCE,
                "test": TEST,
            }

    async def workflow(model, **options):
        return await run_suggestion(model, adapter_factory=lambda **_: Adapter(), **options)

    monkeypatch.setattr(_owner_read_workflow, "OwnerReadRuntime", Runtime)
    monkeypatch.setattr(_owner_read_workflow, "OwnerReadDockerDispatcher", Dispatcher)
    monkeypatch.setattr(_owner_read_copy_files, "_TEMP_PARENT", tmp_path)
    return workflow
