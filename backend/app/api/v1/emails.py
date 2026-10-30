"""Authenticated, tenant-scoped email listing and detail endpoints."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session
from app.database.db import get_db_session
from app.middleware.auth import get_current_user
from app.models.db_models import EmailModel, UserModel
from app.schemas.emails import EmailResponse, EmailListResponse
router = APIRouter(prefix="/emails", tags=["Emails V1"])

@router.get("", response_model=EmailListResponse)
def list_emails(limit: int = Query(50, ge=1, le=100), skip: int = Query(0, ge=0),
                category: Optional[str] = Query(None),
                sender: Optional[str] = Query(None, description="Legacy partial sender filter"),
                search: Optional[str] = Query(None, description="Search sender and subject"),
                current_user: UserModel = Depends(get_current_user),
                db: Session = Depends(get_db_session)):
    """Return only the signed-in user's emails, newest first."""
    query = db.query(EmailModel).filter(EmailModel.user_id == current_user.id)
    if category:
        query = query.filter(EmailModel.category == category)
    term = (search or sender or "").strip()
    if term:
        pattern = f"%{term}%"
        query = query.filter(or_(EmailModel.sender.ilike(pattern), EmailModel.subject.ilike(pattern)))
    total = query.count()
    rows = query.order_by(EmailModel.received_at.desc(), EmailModel.created_at.desc()).offset(skip).limit(limit).all()
    return EmailListResponse(emails=[EmailResponse(**row.to_dict()) for row in rows], total=total, limit=limit, skip=skip)

@router.get("/{email_id}", response_model=EmailResponse)
def get_email(email_id: str, current_user: UserModel = Depends(get_current_user),
              db: Session = Depends(get_db_session)):
    """Retrieve an email only when it belongs to the signed-in user."""
    email = db.query(EmailModel).filter(EmailModel.id == email_id, EmailModel.user_id == current_user.id).first()
    if not email:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email record not found")
    return EmailResponse(**email.to_dict())
