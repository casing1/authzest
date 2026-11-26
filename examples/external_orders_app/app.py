"""Synthetic order-lookup service with a deliberate object-ownership defect.

Copy this folder outside the repository before running repo-fix on it.
Identities are synthetic test headers, not a real authentication system.
"""

from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException

app = FastAPI()

ORDERS = {
    "A-100": {"order_id": "A-100", "customer": "test-kim", "item": "keyboard", "total": 59},
    "A-101": {"order_id": "A-101", "customer": "test-lee", "item": "monitor", "total": 189},
}


def current_user(
    x_user_id: str | None = Header(default=None),
    x_role: str | None = Header(default=None),
) -> dict:
    if x_user_id is None:
        raise HTTPException(status_code=401, detail="Login required")
    return {"id": x_user_id, "role": x_role or "test-customer"}


@app.get("/status")
def status():
    return {"service": "orders", "ready": True}


@app.get("/orders/{order_id}")
def get_order(order_id: str, user: Annotated[dict, Depends(current_user)]):
    order = ORDERS.get(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return order
