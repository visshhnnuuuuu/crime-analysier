"""
Basic RBAC (Phase 11)
Role passed via X-User-Role header. Two roles:
  - "viewer": can view risk flags
  - "reviewer": can view AND action (review) risk flags
Nothing is auto-actioned regardless of role -- this only gates who
can call which endpoint.
"""

from fastapi import Header, HTTPException

ALLOWED_ROLES = {"viewer", "reviewer"}

def require_role(x_user_role: str = Header(default=None)):
    if x_user_role is None or x_user_role not in ALLOWED_ROLES:
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid X-User-Role header. Use 'viewer' or 'reviewer'.",
        )
    return x_user_role


def require_reviewer(x_user_role: str = Header(default=None)):
    if x_user_role != "reviewer":
        raise HTTPException(
            status_code=403,
            detail="This action requires the 'reviewer' role.",
        )
    return x_user_role
