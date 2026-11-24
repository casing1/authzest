"""Owned inert HTTP file sessions; never import source or run a target/provider."""

from tests.helpers.repository_http_verification_data import POLICY, SOURCE, case_data, inputs

from authzest.analyzer.repository_origin import capture_repository_origin
from authzest.codex.repository_http_copy_plan import prepare_repository_http_copy_plan
from authzest.codex.repository_http_proposal import build_repository_http_request
from authzest.runner.repository_http_cases import build_repository_http_cases
from authzest.runner.repository_http_file_session import RepositoryHttpFileSession


class Clock:
    def __init__(self, value=10.0):
        self.value = value

    def __call__(self):
        return self.value


def perform(session, step):
    plan = session.prepare(step)
    return session.perform(session.decide(plan, plan.to_dict()["confirmation"]))


def make_http_file_session(tmp_path, *, clock=None, prefix="case"):
    root = (tmp_path / (prefix + "-origin")).resolve()
    parent = (tmp_path / (prefix + "-private")).resolve()
    root.mkdir()
    parent.mkdir(mode=0o700)
    (root / "app.py").write_bytes(SOURCE.encode("utf-8"))
    (root / "policy.md").write_bytes(POLICY.encode("utf-8"))
    origin = capture_repository_origin(root, "app.py", "policy.md")
    request = build_repository_http_request(origin.snapshot, "offline-model")
    response = inputs()[1]
    response["request_id"] = request.request_id
    response["proposal"]["before_sha256"] = request.to_dict()["selection"]["files"][0]["sha256"]
    cases = build_repository_http_cases(case_data(request))
    copy_plan = prepare_repository_http_copy_plan(request, response, cases)
    clock = clock if clock is not None else Clock()
    try:
        session = RepositoryHttpFileSession(
            origin, request, response, cases, copy_plan, _clock=clock, _parent=parent
        )
    except BaseException:
        origin.close()
        raise
    return session, origin, clock, request, response, cases, copy_plan
