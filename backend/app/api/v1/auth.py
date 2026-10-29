"""
Authentication and MFA API Endpoints.
Provides user registration, email verification, session login/logout,
password reset, TOTP MFA enrollment and verification, and session management.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.database.db import get_db_session
from app.middleware.auth import (
    get_current_user,
    get_current_user_allow_pending_mfa,
    get_current_user_and_session,
    get_session_token_from_request,
)
from app.models.db_models import (
    NotificationPreferencesModel,
    UserModel,
    UserSessionModel,
)
from app.services import auth_service, mfa_service
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication & MFA"])


# --- Schemas ---

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class VerifyEmailRequest(BaseModel):
    token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8, max_length=128)


class MFAConfirmRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=6)


class MFAChallengeRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=8)


class MFARecoveryRequest(BaseModel):
    recovery_code: str


class MFADisableRequest(BaseModel):
    password: str
    code: Optional[str] = None


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: Optional[str]
    is_verified: bool
    is_active: bool
    is_admin: bool
    mfa_enabled: bool
    created_at: Any

    class Config:
        from_attributes = True


class SessionResponse(BaseModel):
    id: str
    ip_address: Optional[str]
    user_agent: Optional[str]
    is_mfa_completed: bool
    is_current: bool
    expires_at: Any
    created_at: Any
    last_active_at: Any


# --- Endpoints ---

@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(req: RegisterRequest, db: Session = Depends(get_db_session)):
    """Register a new user account with Argon2id password hashing and email verification."""
    email_clean = req.email.lower().strip()

    # Password strength check
    is_valid, err_msg = auth_service.validate_password_strength(req.password)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)

    # Check duplicate
    existing = db.query(UserModel).filter(UserModel.email == email_clean).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists.",
        )

    pwd_hash = auth_service.hash_password(req.password)
    new_user = UserModel(
        email=email_clean,
        password_hash=pwd_hash,
        full_name=req.full_name.strip() if req.full_name else None,
        is_verified=False,
        is_active=True,
        is_admin=False,
        mfa_enabled=False,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Create default notification preferences
    prefs = NotificationPreferencesModel(
        user_id=new_user.id,
        notification_mode="immediate",
        digest_interval_minutes=60,
        privacy_mode=False,
        notification_cutoff_hours=24,
        reminder_offsets_min="1440,360,60",
        included_categories="All",
    )
    db.add(prefs)
    db.commit()

    # Create verification token
    verification_token = auth_service.create_email_verification_token(db, new_user.id)

    auth_service.log_audit_event(
        db, event_type="user_registered", user_id=new_user.id, details={"email": email_clean}
    )

    return {
        "message": "Registration successful. Please verify your email address to continue.",
        "user_id": new_user.id,
        "email": new_user.email,
        "verification_token": verification_token,
    }


@router.post("/login")
def login(
    req: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db_session),
):
    """
    Authenticate user, enforce rate limits, and set secure HttpOnly session cookie.
    If MFA is enabled, marks session as MFA-pending.
    """
    email_clean = req.email.lower().strip()
    client_ip = request.client.host if request.client else "unknown"
    rate_key = f"{client_ip}:{email_clean}"

    # Rate limiting check
    allowed, cooldown = auth_service.check_rate_limit(rate_key)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed login attempts. Please wait {cooldown} seconds.",
            headers={"Retry-After": str(cooldown)},
        )

    user = db.query(UserModel).filter(UserModel.email == email_clean).first()
    if not user or not auth_service.verify_password(req.password, user.password_hash):
        auth_service.record_failed_attempt(rate_key)
        auth_service.log_audit_event(
            db,
            event_type="login_failed",
            ip_address=client_ip,
            user_agent=request.headers.get("user-agent"),
            details={"email": email_clean},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled. Please contact support.",
        )

    # Authentication successful
    auth_service.clear_failed_attempts(rate_key)

    is_mfa_req = bool(user.mfa_enabled)
    session_obj, raw_token = auth_service.create_session(
        db,
        user=user,
        ip_address=client_ip,
        user_agent=request.headers.get("user-agent"),
        is_mfa_completed=not is_mfa_req,
    )

    # Set HttpOnly session cookie
    response.set_cookie(
        key=settings.session_cookie_name,
        value=raw_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=settings.session_expiry_days * 86400,
        path="/",
    )

    auth_service.log_audit_event(
        db,
        event_type="login_successful",
        user_id=user.id,
        ip_address=client_ip,
        user_agent=request.headers.get("user-agent"),
        details={"mfa_required": is_mfa_req},
    )

    return {
        "message": "Login successful.",
        "mfa_required": is_mfa_req,
        "token": raw_token,  # Also returned for clients/tests that use Authorization Bearer
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "is_verified": user.is_verified,
            "mfa_enabled": user.mfa_enabled,
            "is_admin": user.is_admin,
        },
    }


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db_session),
):
    """Log out current session and clear session cookie."""
    raw_token = get_session_token_from_request(request)
    if raw_token:
        res = auth_service.validate_session(db, raw_token)
        if res:
            session_obj, user = res
            auth_service.revoke_session(db, session_obj.id, user.id)
            auth_service.log_audit_event(
                db,
                event_type="logout",
                user_id=user.id,
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
            )

    response.delete_cookie(key=settings.session_cookie_name, path="/")
    return {"message": "Logged out successfully."}


@router.get("/me", response_model=UserResponse)
def get_me(current_user: UserModel = Depends(get_current_user)):
    """Get profile of currently authenticated user."""
    return current_user


@router.post("/verify-email")
def verify_email(req: VerifyEmailRequest, db: Session = Depends(get_db_session)):
    """Verify email address with a short-lived token."""
    user = auth_service.verify_email_token(db, req.token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token.",
        )
    auth_service.log_audit_event(db, event_type="email_verified", user_id=user.id)
    return {"message": "Email address successfully verified. You may now log in."}


@router.post("/forgot-password")
def forgot_password(
    req: ForgotPasswordRequest,
    request: Request,
    db: Session = Depends(get_db_session),
):
    """
    Initiate password recovery.
    Returns generic response to avoid email enumeration.
    """
    email_clean = req.email.lower().strip()
    user = db.query(UserModel).filter(UserModel.email == email_clean).first()
    reset_token = None
    if user and user.is_active:
        reset_token = auth_service.create_password_reset_token(db, user.id)
        auth_service.log_audit_event(
            db,
            event_type="password_reset_requested",
            user_id=user.id,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )

    # In dev or testing, we include reset_token in the payload
    resp = {
        "message": "If that email address is registered, password reset instructions have been sent."
    }
    if reset_token:
        resp["reset_token"] = reset_token
    return resp


@router.post("/reset-password")
def reset_password(
    req: ResetPasswordRequest,
    request: Request,
    db: Session = Depends(get_db_session),
):
    """Reset password using a single-use token and invalidate all active sessions."""
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    success, err_msg = auth_service.reset_password_with_token(
        db,
        raw_token=req.token,
        new_password=req.new_password,
        ip_address=client_ip,
        user_agent=user_agent,
    )
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)

    return {"message": "Password has been successfully reset. Please log in with your new password."}


# --- MFA Endpoints ---

@router.post("/mfa/enroll")
def mfa_enroll(
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Initiate TOTP MFA enrollment and return QR code data URL."""
    secret, uri, qr_code = mfa_service.initiate_mfa_enrollment(db, current_user)
    return {
        "secret": secret,
        "provisioning_uri": uri,
        "qr_code": qr_code,
    }


@router.post("/mfa/confirm")
def mfa_confirm(
    req: MFAConfirmRequest,
    request: Request,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Confirm MFA setup with a code from authenticator and receive recovery codes."""
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    success, err_msg, recovery_codes = mfa_service.confirm_mfa_enrollment(
        db,
        user=current_user,
        totp_code=req.code,
        ip_address=client_ip,
        user_agent=user_agent,
    )
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)

    return {
        "message": "Two-factor authentication successfully enabled.",
        "recovery_codes": recovery_codes,
    }


@router.post("/mfa/challenge")
def mfa_challenge(
    req: MFAChallengeRequest,
    auth: Tuple[UserModel, UserSessionModel] = Depends(get_current_user_allow_pending_mfa),
    db: Session = Depends(get_db_session),
):
    """Verify TOTP code during login challenge."""
    user, session_obj = auth
    if session_obj.is_mfa_completed:
        return {"message": "MFA is already verified for this session."}

    valid = mfa_service.verify_totp_code(db, user, req.code)
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid authenticator code. Please check your time synchronization.",
        )

    session_obj.is_mfa_completed = True
    db.commit()

    return {
        "message": "MFA challenge successfully verified.",
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "is_verified": user.is_verified,
            "mfa_enabled": user.mfa_enabled,
        },
    }


@router.post("/mfa/recovery")
def mfa_recovery(
    req: MFARecoveryRequest,
    request: Request,
    auth: Tuple[UserModel, UserSessionModel] = Depends(get_current_user_allow_pending_mfa),
    db: Session = Depends(get_db_session),
):
    """Authenticate using a single-use recovery code."""
    user, session_obj = auth
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    valid = mfa_service.verify_and_consume_recovery_code(
        db,
        user=user,
        recovery_code=req.recovery_code,
        ip_address=client_ip,
        user_agent=user_agent,
    )
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or already used recovery code.",
        )

    session_obj.is_mfa_completed = True
    db.commit()

    return {
        "message": "Recovery code accepted. MFA challenge completed.",
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "is_verified": user.is_verified,
            "mfa_enabled": user.mfa_enabled,
        },
    }


@router.post("/mfa/disable")
def mfa_disable(
    req: MFADisableRequest,
    request: Request,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Disable MFA after confirming user password."""
    if not auth_service.verify_password(req.password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid password. Cannot disable MFA.",
        )

    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    mfa_service.disable_mfa(
        db, user=current_user, ip_address=client_ip, user_agent=user_agent
    )
    return {"message": "Two-factor authentication disabled successfully."}


# --- Session Management Endpoints ---

@router.get("/sessions", response_model=List[SessionResponse])
def list_sessions(
    auth: Tuple[UserModel, UserSessionModel] = Depends(get_current_user_and_session),
    db: Session = Depends(get_db_session),
):
    """List all active sessions for the authenticated user."""
    user, current_session = auth
    sessions = (
        db.query(UserSessionModel)
        .filter(UserSessionModel.user_id == user.id)
        .order_by(UserSessionModel.last_active_at.desc())
        .all()
    )
    return [
        SessionResponse(
            id=s.id,
            ip_address=s.ip_address,
            user_agent=s.user_agent,
            is_mfa_completed=s.is_mfa_completed,
            is_current=(s.id == current_session.id),
            expires_at=s.expires_at,
            created_at=s.created_at,
            last_active_at=s.last_active_at,
        )
        for s in sessions
    ]


@router.delete("/sessions/{session_id}")
def revoke_session(
    session_id: str,
    auth: Tuple[UserModel, UserSessionModel] = Depends(get_current_user_and_session),
    db: Session = Depends(get_db_session),
):
    """Revoke a specific session."""
    user, _ = auth
    success = auth_service.revoke_session(db, session_id=session_id, user_id=user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or already revoked.",
        )
    return {"message": "Session revoked."}


@router.post("/sessions/revoke-all")
def revoke_all_sessions(
    auth: Tuple[UserModel, UserSessionModel] = Depends(get_current_user_and_session),
    db: Session = Depends(get_db_session),
):
    """Revoke all sessions except the current active session."""
    user, current_session = auth
    count = auth_service.revoke_all_user_sessions(
        db, user_id=user.id, except_session_id=current_session.id
    )
    return {"message": f"Revoked {count} other active session(s)."}
