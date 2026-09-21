"""Source-only reference for the owned policy example; do not import or serve it.

Authentication is deliberately unconfigured and fails closed. The scanner may
observe declarations here; that is not proof of authentication or authorization.
"""

from typing import Annotated

from fastapi import FastAPI, HTTPException, Security

from .policy import Principal, Report, can_read_report

app = FastAPI()

_REPORTS = {"report-001": Report(report_id="report-001", owner_id="alice")}


def require_authenticated_principal() -> Principal:
    """Fail closed until a real trusted authentication provider is designed."""
    raise HTTPException(status_code=401, detail="Authentication provider is not configured")


@app.get("/reports/{report_id}")
def read_report(
    report_id: str,
    principal: Annotated[
        Principal, Security(require_authenticated_principal, scopes=["reports:read"])
    ],
) -> dict[str, str]:
    report = _REPORTS.get(report_id)
    if not can_read_report(principal, report):
        raise HTTPException(status_code=403, detail="Report access denied")
    return {"report_id": report.report_id, "content": "Synthetic report data only"}
