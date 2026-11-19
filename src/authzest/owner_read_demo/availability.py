"""Baseline business rule evaluated after authentication and ownership checks."""


def available_to_owner(state: str) -> bool:
    return state == "active"
