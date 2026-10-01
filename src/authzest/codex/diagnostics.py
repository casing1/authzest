"""Closed, local failure metadata with no provider text or private identities."""

from dataclasses import dataclass

VALIDATION_CODES = frozenset(
    {
        "validation-json",
        "validation-budget",
        "validation-shape",
        "validation-text",
        "validation-duplicate",
        "validation-question-coverage",
        "validation-status",
        "validation-evidence",
        "validation-abstention",
        "validation-case-id",
        "validation-case-value",
        "validation-identity",
        "validation-usage",
    }
)

FAILURE_STAGES = frozenset(
    {
        "adapter-setup",
        "request-validation",
        "startup",
        "configuration",
        "account-check",
        "model-check",
        "thread-start",
        "turn-start",
        "turn-stream",
        "response-validation",
        "result-validation",
        "cleanup",
        "unknown",
    }
)
FAILURE_CODES = (
    frozenset(
        {
            "unexpected-error",
            "timeout",
            "cancelled",
            "transport-error",
            "protocol-rejected",
            "configuration-rejected",
            "version-unsupported",
            "authentication-required",
            "model-unavailable",
            "request-rejected",
            "turn-failed",
            "response-invalid",
            "request-invalid",
            "cleanup-failed",
        }
    )
    | VALIDATION_CODES
)
TURN_START_STATES = frozenset({"not-attempted", "attempted", "acknowledged", "unknown"})


def _allowed(value: object, choices: frozenset[str]) -> bool:
    # Check type before hashing/comparing: string subclasses and arbitrary objects
    # must never run their own equality/hash/string hooks in this redaction path.
    return type(value) is str and value in choices


@dataclass(frozen=True)
class FailureDiagnostic:
    """A local phase/progress observation, not proof of billing or server execution."""

    stage: str
    code: str
    turn_start: str

    def __post_init__(self) -> None:
        if not (
            _allowed(self.stage, FAILURE_STAGES)
            and _allowed(self.code, FAILURE_CODES)
            and _allowed(self.turn_start, TURN_START_STATES)
        ):
            raise ValueError("Invalid bounded failure diagnostic")


def sanitize_failure(
    value: object, *, stage: str = "unknown", code: str = "unexpected-error"
) -> dict[str, str]:
    """Return only validated enums; never accept mappings or trust a constructor."""
    fallback = {
        "stage": stage if _allowed(stage, FAILURE_STAGES) else "unknown",
        "code": code if _allowed(code, FAILURE_CODES) else "unexpected-error",
        "turn_start": "unknown",
    }
    if type(value) is not FailureDiagnostic:
        return fallback
    try:
        fields = (value.stage, value.code, value.turn_start)
    except AttributeError:
        return fallback
    if not all(
        _allowed(field, choices)
        for field, choices in zip(
            fields, (FAILURE_STAGES, FAILURE_CODES, TURN_START_STATES), strict=True
        )
    ):
        return fallback
    return dict(zip(("stage", "code", "turn_start"), fields, strict=True))
