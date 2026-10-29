"""
Emails API endpoints (v1).
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.database.db import get_db
from app.middleware.auth import require_api_key, get_optional_current_user
from app.models.db_models import UserModel
from app.schemas.emails import EmailResponse, EmailListResponse

router = APIRouter(prefix="/emails", tags=["Emails V1"])


@router.get("", response_model=EmailListResponse, dependencies=[Depends(require_api_key)])
def list_emails(
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    category: Optional[str] = Query(None),
    sender: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    current_user: Optional[UserModel] = Depends(get_optional_current_user),
    db=Depends(get_db),
):
    """List processed emails with pagination and optional filters."""
    filter_dict = {}
    if current_user and not current_user.is_admin:
        filter_dict["user_id"] = current_user.id
    if category:
        filter_dict["category"] = category
    if sender:
        filter_dict["sender"] = sender

    total = db.emails.count_documents(filter_dict)
    emails_cursor = db.emails.find(filter_dict).sort("created_at", -1).skip(skip).limit(limit)
    emails_list = list(emails_cursor)

    items = []
    for e in emails_list:
        items.append(
            EmailResponse(
                id=str(e.get("id") or e.get("_id")),
                account_id=e.get("account_id"),
                gmail_message_id=e.get("gmail_message_id") or e.get("gmail_id") or "",
                gmail_thread_id=e.get("gmail_thread_id"),
                sender=e.get("sender", "unknown"),
                recipients=e.get("recipients"),
                subject=e.get("subject", "(no subject)"),
                received_at=e.get("received_at"),
                category=e.get("category", "Other"),
                extracted_deadline=e.get("extracted_deadline") or e.get("deadline"),
                confidence_score=e.get("confidence_score", 0.0),
                ambiguous_date=e.get("ambiguous_date", False),
                plain_body=e.get("plain_body") or e.get("body"),
                labels=e.get("labels"),
                processing_status=e.get("processing_status", "completed"),
                created_at=e.get("created_at"),
                updated_at=e.get("updated_at"),
            )
        )

    return EmailListResponse(emails=items, total=total, limit=limit, skip=skip)


@router.get("/{id}", response_model=EmailResponse, dependencies=[Depends(require_api_key)])
def get_email(
    id: str,
    current_user: Optional[UserModel] = Depends(get_optional_current_user),
    db=Depends(get_db),
):
    """Retrieve details for a single email record."""
    email = db.emails.find_one({"id": id}) or db.emails.find_one({"_id": id})
    if not email:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email record not found")

    if current_user and not current_user.is_admin:
        email_user_id = email.get("user_id")
        if email_user_id and email_user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email record not found")

    return EmailResponse(
        id=str(email.get("id") or email.get("_id")),
        account_id=email.get("account_id"),
        gmail_message_id=email.get("gmail_message_id") or email.get("gmail_id") or "",
        gmail_thread_id=email.get("gmail_thread_id"),
        sender=email.get("sender", "unknown"),
        recipients=email.get("recipients"),
        subject=email.get("subject", "(no subject)"),
        received_at=email.get("received_at"),
        category=email.get("category", "Other"),
        extracted_deadline=email.get("extracted_deadline") or email.get("deadline"),
        confidence_score=email.get("confidence_score", 0.0),
        ambiguous_date=email.get("ambiguous_date", False),
        plain_body=email.get("plain_body") or email.get("body"),
        labels=email.get("labels"),
        processing_status=email.get("processing_status", "completed"),
        created_at=email.get("created_at"),
        updated_at=email.get("updated_at"),
    )

