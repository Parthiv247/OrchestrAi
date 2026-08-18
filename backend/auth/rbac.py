from enum import Enum
from typing import List
from functools import wraps
from fastapi import HTTPException, status, Depends
from .jwt_handler import get_current_user

FORBIDDEN_SQL_KEYWORDS = {"DROP", "DELETE", "TRUNCATE", "ALTER", "CREATE", "GRANT", "REVOKE"}


class Role(str, Enum):
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"


ROLE_HIERARCHY = {
    Role.ADMIN: 3,
    Role.ANALYST: 2,
    Role.VIEWER: 1,
}


def require_role(roles: List[Role]):
    """Dependency that enforces role-based access."""
    async def role_checker(current_user: dict = Depends(get_current_user)):
        user_role = current_user.get("role")
        if user_role not in [r.value for r in roles]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {[r.value for r in roles]}",
            )
        return current_user
    return role_checker


def validate_sql_permissions(sql: str, role: str) -> tuple[bool, str]:
    """Analysts and Viewers cannot run destructive SQL."""
    if role == Role.ADMIN.value:
        return True, ""
    upper_sql = sql.upper()
    for keyword in FORBIDDEN_SQL_KEYWORDS:
        if keyword in upper_sql:
            return False, f"Role '{role}' is not permitted to execute {keyword} statements"
    return True, ""
