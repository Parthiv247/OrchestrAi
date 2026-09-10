from fastapi import Depends, HTTPException, status

from ..auth.jwt_handler import get_current_user


async def get_tenant_id(current_user: dict = Depends(get_current_user)) -> str:
    """Extract tenant_id from authenticated user's JWT payload."""
    tenant_id = current_user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="tenant_id missing from token",
        )
    return tenant_id
