"""
API Authentication and Authorization dependencies.
Supports session cookies (HttpOnly, SameSite=Lax), Bearer tokens, MFA completion enforcement,
and legacy API key checks.
"""
from typing import Optional, Tuple
from fastapi import Cookie, Depends, Header, HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.config import settings
from app.database.db import get_db, get_db_session
from app.models.db_models import UserModel, UserSessionModel
from app.services.auth_service import validate_session
from app.utils.logger import get_logger

logger = get_logger(__name__)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)


def require_api_key(
    x_api_key: Optional[str] = Security(api_key_header),
    bearer_creds: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
) -> bool:
    """
    Enforces authentication on administrative endpoints.
    Checks X-API-Key header or Authorization: Bearer <token>.
    """
    if not settings.api_key:
        return True

    provided_token = x_api_key
    if not provided_token and bearer_creds:
        provided_token = bearer_creds.credentials

    if not provided_token or provided_token.strip() != settings.api_key.strip():
        logger.warning("Unauthorized access attempt on protected endpoint")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Invalid or missing API Key.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return True


def get_session_token_from_request(
    request: Request,
    bearer_creds: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
) -> Optional[str]:
    """Extract raw session token from HttpOnly cookie or Authorization Bearer header."""
    cookie_token = request.cookies.get(settings.session_cookie_name)
    if cookie_token:
        return cookie_token
    if bearer_creds and bearer_creds.credentials:
        return bearer_creds.credentials
    # Fallback check for session header
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header.split(" ", 1)[1].strip()
    return None


def get_current_user_and_session(
    request: Request,
    db: Session = Depends(get_db_session),
    bearer_creds: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
) -> Tuple[UserModel, UserSessionModel]:
    """
    Validate user session from cookie or bearer token.
    Enforces that MFA is completed if MFA is enabled.
    """
    token = get_session_token_from_request(request, bearer_creds)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Missing session cookie or token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = validate_session(db, token)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    session, user = result

    if not session.is_mfa_completed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="MFA_CHALLENGE_REQUIRED",
        )

    return user, session


def get_current_user(
    auth: Tuple[UserModel, UserSessionModel] = Depends(get_current_user_and_session)
) -> UserModel:
    """Dependency that returns the authenticated UserModel."""
    return auth[0]


def get_optional_current_user(
    request: Request,
    db: Session = Depends(get_db_session),
    bearer_creds: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
) -> Optional[UserModel]:
    """Optional user dependency: returns UserModel if authenticated, None otherwise."""
    token = get_session_token_from_request(request, bearer_creds)
    if not token:
        return None
    res = validate_session(db, token)
    if not res:
        return None
    session, user = res
    if not session.is_mfa_completed:
        return None
    return user


def get_current_user_allow_pending_mfa(
    request: Request,
    db: Session = Depends(get_db_session),
    bearer_creds: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
) -> Tuple[UserModel, UserSessionModel]:
    """Dependency for MFA challenge routes where session.is_mfa_completed may be False."""
    token = get_session_token_from_request(request, bearer_creds)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )

    result = validate_session(db, token)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session.",
        )

    return result[1], result[0]


def require_admin(user: UserModel = Depends(get_current_user)) -> UserModel:
    """Require administrator privileges."""
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative privileges required.",
        )
    return user


def verify_resource_ownership(resource_user_id: Optional[str], current_user: UserModel) -> None:
    """Prevent IDOR by ensuring resource belongs to current user."""
    if resource_user_id and resource_user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resource not found.",
        )


