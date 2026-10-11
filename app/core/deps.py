"""FastAPI dependencies: auth, RBAC, pagination."""
import jwt
from fastapi import Depends, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.security import decode_access_token
from app.db.models import Role, User
from app.db.session import get_db

APPROVER_ROLES = {Role.admin}
STAFF_ROLES = {Role.admin, Role.support_agent}


# HTTPBearer registers an `http: bearer` securityScheme in the OpenAPI spec,
# which makes the Swagger UI Authorize button functional.
_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise UnauthorizedError("Missing bearer token")
    token = credentials.credentials
    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError as e:
        raise UnauthorizedError("Invalid or expired token") from e
    user = db.get(User, payload.get("sub", ""))
    if user is None or not user.is_active:
        raise UnauthorizedError("User not found or inactive")
    return user


def require_staff(user: User = Depends(get_current_user)) -> User:
    if user.role not in STAFF_ROLES:
        raise ForbiddenError("Staff role required")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != Role.admin:
        raise ForbiddenError("Admin role required")
    return user


def require_approver(user: User = Depends(get_current_user)) -> User:
    """Separate permission for approval decisions (admins only)."""
    if user.role not in APPROVER_ROLES:
        raise ForbiddenError("Approver role required")
    return user


class Pagination:
    def __init__(
        self,
        page: int = Query(default=1, ge=1),
        size: int = Query(default=20, ge=1, le=100),
    ):
        self.page = page
        self.size = size
        self.offset = (page - 1) * size
