"""Maintainer-owned response expectations for the seven synthetic owner-read cases."""

from typing import NamedTuple


class _Response(NamedTuple):
    status: int
    fields: tuple[tuple[str, str], ...]

    def as_dict(self):
        return {"status_code": self.status, "body": dict(self.fields)}

    def matches(self, status, body):
        return self.status == status and dict(self.fields) == body


class _Case(NamedTuple):
    case_id: str
    principal: str | None
    record_id: str
    before: _Response
    intended: _Response


_ACTIVE = _Response(200, (("id", "active-note"), ("title", "Active note")))
_ARCHIVED = _Response(200, (("id", "archived-note"), ("title", "Archived note")))
_DENIED = _Response(403, (("detail", "Read denied"),))
_ANONYMOUS = _Response(401, (("detail", "Authentication required"),))
_MISSING = _Response(404, (("detail", "Record not found"),))

_CASES = (
    _Case("owner-active", "owner", "active-note", _ACTIVE, _ACTIVE),
    _Case("owner-archived", "owner", "archived-note", _DENIED, _ARCHIVED),
    _Case("other-active", "other", "active-note", _DENIED, _DENIED),
    _Case("other-archived", "other", "archived-note", _DENIED, _DENIED),
    _Case("anonymous-active", None, "active-note", _ANONYMOUS, _ANONYMOUS),
    _Case("owner-missing", "owner", "missing-note", _MISSING, _MISSING),
    _Case("owner-pending", "owner", "pending-note", _DENIED, _DENIED),
)


def owner_read_controls() -> list[dict]:
    """Return a detached JSON preview in the order the collector must record."""
    return [
        {
            "case_id": case.case_id,
            "principal": case.principal,
            "record_id": case.record_id,
            "before": case.before.as_dict(),
            "intended": case.intended.as_dict(),
        }
        for case in _CASES
    ]


def _valid_observation(row: object, case: _Case) -> bool:
    if (
        type(row) is not dict
        or len(row) != 3
        or any(type(key) is not str for key in row)
        or row.keys() != {"case_id", "status_code", "body"}
    ):
        return False
    status, body = row["status_code"], row["body"]
    return (
        type(row["case_id"]) is str
        and row["case_id"] == case.case_id
        and type(status) is int
        and 100 <= status <= 599
        and type(body) is dict
        and len(body) <= 8
        and all(
            type(key) is str and len(key) <= 64 and type(value) is str and len(value) <= 256
            for key, value in body.items()
        )
    )


def compare_owner_read_observations(observations: object) -> dict:
    """Compare fixed-order response data. The result never echoes supplied bodies."""
    invalid = {
        "status": "invalid-observations",
        "checks_total": len(_CASES),
        "intended_matches": None,
        "matches_before_profile": None,
        "matches_intended_policy": None,
        "checks": [],
    }
    if type(observations) is not list or len(observations) != len(_CASES):
        return invalid
    checks = []
    for case, row in zip(_CASES, observations, strict=True):
        if not _valid_observation(row, case):
            return invalid
        status, body = row["status_code"], row["body"]
        checks.append(
            {
                "case_id": case.case_id,
                "before_match": case.before.matches(status, body),
                "intended_match": case.intended.matches(status, body),
            }
        )
    intended_matches = sum(row["intended_match"] for row in checks)
    return {
        "status": "compared",
        "checks_total": len(_CASES),
        "intended_matches": intended_matches,
        "matches_before_profile": all(row["before_match"] for row in checks),
        "matches_intended_policy": intended_matches == len(_CASES),
        "checks": checks,
    }
