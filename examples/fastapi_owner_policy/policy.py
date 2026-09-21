"""Pure policy for a maintained synthetic example, not an authentication provider.

The caller must supply an already trusted principal and report ownership context.
These dataclasses and this function do not authenticate that context or make
request-supplied identity, scope, authentication, or ownership claims trustworthy.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Principal:
    """Synthetic trusted context; construction does not authenticate a subject."""

    subject: str | None
    authenticated: bool
    scopes: frozenset[str]


@dataclass(frozen=True, slots=True)
class Report:
    """Synthetic report metadata supplied by a trusted lookup, not an HTTP claim."""

    report_id: str
    owner_id: str | None


def _nonblank_string(value: object) -> bool:
    # Whitespace is inspected only for blankness; identifiers are never normalized.
    return type(value) is str and bool(value.strip())


def can_read_report(principal: Principal | None, report: Report | None) -> bool:
    """Require trusted authentication, exact ownership, and the literal read scope.

    Missing or malformed input denies access. There is no admin, wildcard, or
    normalization bypass, and this predicate performs no I/O or authentication.
    """
    if type(principal) is not Principal or type(report) is not Report:
        return False
    if getattr(principal, "authenticated", None) is not True:
        return False
    subject = getattr(principal, "subject", None)
    owner_id = getattr(report, "owner_id", None)
    report_id = getattr(report, "report_id", None)
    scopes = getattr(principal, "scopes", None)
    if not all(_nonblank_string(value) for value in (subject, owner_id, report_id)):
        return False
    if type(scopes) is not frozenset:
        return False
    if not all(_nonblank_string(scope) for scope in scopes):
        return False
    return subject == owner_id and "reports:read" in scopes
