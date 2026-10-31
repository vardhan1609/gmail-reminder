"""Customer billing, entitlements, payments and admin management."""
from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.config import settings
from app.database.db import get_db_session
from app.middleware.auth import get_current_user, require_admin
from app.models.db_models import (
    GmailConnectionModel, NotificationIntegrationModel, PaymentOrderModel,
    SubscriptionModel, UserModel, UsageEventModel, utc_now,
)
from app.services.auth_service import log_audit_event
from app.services.billing import (
    PLAN_CATALOG, activate_paid_subscription, get_active_subscription,
    get_payment_adapter, plan_price_paise, subscription_payload,
)

router = APIRouter(prefix="/billing", tags=["Billing & Subscriptions"])


class CheckoutRequest(BaseModel):
    plan_code: str = Field(..., pattern="^(basic|premium)$")
    provider: Optional[str] = Field(None, pattern="^(razorpay|cashfree)$")


class AdminCustomerUpdate(BaseModel):
    is_active: Optional[bool] = None
    plan_code: Optional[str] = Field(None, pattern="^(basic|premium)$")


@router.get("/plans")
def list_plans():
    """Public plan catalog. Prices are configured in integer minor units in server env."""
    return {
        code: {
            **plan,
            "price_paise": plan_price_paise(code),
            "currency": settings.payment_currency,
            "billing_period": "monthly",
        }
        for code, plan in PLAN_CATALOG.items()
    }


@router.get("/me")
def get_my_subscription(
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    return subscription_payload(db, current_user.id)


@router.post("/checkout", status_code=status.HTTP_201_CREATED)
def create_checkout(
    req: CheckoutRequest,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    price = plan_price_paise(req.plan_code)
    if price <= 0:
        raise HTTPException(status_code=400, detail=f"{req.plan_code.title()} plan has no payment price configured.")
    provider = req.provider or settings.payment_provider
    provider = provider.lower()
    try:
        adapter = get_payment_adapter(provider)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    order = PaymentOrderModel(
        user_id=current_user.id,
        plan_code=req.plan_code,
        provider=provider,
        amount_paise=price,
        currency=settings.payment_currency.upper(),
        status="creating",
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    callback_url = f"{settings.frontend_base_url.rstrip('/')}/dashboard/billing?checkout=return"
    try:
        checkout = adapter.create_checkout(order=order, user=current_user, callback_url=callback_url)
        order.provider_order_id = checkout["provider_order_id"]
        order.checkout_url = checkout["checkout_url"]
        order.status = "created"
        db.commit()
    except Exception as exc:
        order.status = "failed"
        db.commit()
        # Never return gateway response bodies or credentials to the client.
        raise HTTPException(status_code=502, detail=f"Unable to create {provider.title()} checkout. Check gateway configuration and try again.") from exc
    return {
        "order_id": order.id,
        "provider": provider,
        "plan_code": order.plan_code,
        "amount_paise": order.amount_paise,
        "currency": order.currency,
        "checkout_url": order.checkout_url,
        "status": order.status,
    }


@router.post("/cancel")
def cancel_at_period_end(
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    sub = get_active_subscription(db, current_user.id)
    if sub.plan_code == "basic":
        raise HTTPException(status_code=400, detail="Basic plan does not need cancellation.")
    sub.cancel_at_period_end = True
    db.commit()
    return {"message": "Cancellation recorded. Premium access remains active until the current period ends."}


@router.post("/webhooks/{provider}")
async def payment_webhook(provider: str, request: Request, db: Session = Depends(get_db_session)):
    """Verify gateway signature before processing a payment event. Idempotent on paid orders."""
    try:
        adapter = get_payment_adapter(provider)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Unsupported payment provider.") from exc
    body = await request.body()
    headers = {k.lower(): v for k, v in request.headers.items()}
    if not adapter.verify_webhook(body, headers):
        raise HTTPException(status_code=401, detail="Invalid payment webhook signature.")
    try:
        payload = json.loads(body.decode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid webhook payload.") from exc

    external_id = None
    payment_id = None
    paid = False
    reported_amount_paise = None
    reported_currency = None
    if provider == "razorpay":
        event = payload.get("event")
        entity = payload.get("payload", {})
        if event == "payment_link.paid":
            external_id = (entity.get("payment_link", {}).get("entity", {}) or {}).get("id")
            payment_id = (entity.get("payment", {}).get("entity", {}) or {}).get("id")
            link_entity = (entity.get("payment_link", {}).get("entity", {}) or {})
            reported_amount_paise = link_entity.get("amount")
            reported_currency = link_entity.get("currency")
            paid = True
    else:
        data = payload.get("data", {})
        external_id = data.get("link_id") or (data.get("link", {}) or {}).get("link_id")
        payment = data.get("payment", {}) or {}
        payment_id = payment.get("cf_payment_id")
        link_entity = data.get("link", {}) or {}
        raw_amount = link_entity.get("link_amount", data.get("link_amount"))
        if raw_amount is not None:
            from decimal import Decimal
            reported_amount_paise = int(Decimal(str(raw_amount)) * 100)
        reported_currency = link_entity.get("link_currency", data.get("link_currency"))
        paid = str(data.get("link_status", "")).upper() == "PAID" or str(payment.get("payment_status", "")).upper() == "SUCCESS"

    if not external_id:
        return {"received": True, "processed": False}
    order = db.query(PaymentOrderModel).filter(
        PaymentOrderModel.provider == provider,
        PaymentOrderModel.provider_order_id == str(external_id),
    ).first()
    if not order:
        return {"received": True, "processed": False}
    if paid:
        if reported_amount_paise is not None and int(reported_amount_paise) != order.amount_paise:
            order.status = "review"
            order.raw_webhook = body.decode("utf-8")[:20000]
            db.commit()
            return {"received": True, "processed": False}
        if reported_currency and str(reported_currency).upper() != order.currency.upper():
            order.status = "review"
            order.raw_webhook = body.decode("utf-8")[:20000]
            db.commit()
            return {"received": True, "processed": False}
        activate_paid_subscription(db, order, str(payment_id) if payment_id else None)
    else:
        order.raw_webhook = body.decode("utf-8")[:20000]
        db.commit()
    return {"received": True, "processed": bool(paid)}


@router.get("/admin/overview")
def admin_overview(
    admin: UserModel = Depends(require_admin),
    db: Session = Depends(get_db_session),
):
    active_subs = db.query(SubscriptionModel).filter(SubscriptionModel.status == "active").all()
    return {
        "customers": db.query(func.count(UserModel.id)).scalar() or 0,
        "active_subscriptions": len(active_subs),
        "basic_customers": sum(1 for s in active_subs if s.plan_code == "basic"),
        "premium_customers": sum(1 for s in active_subs if s.plan_code == "premium"),
        "paid_orders": db.query(func.count(PaymentOrderModel.id)).filter(PaymentOrderModel.status == "paid").scalar() or 0,
        "pending_orders": db.query(func.count(PaymentOrderModel.id)).filter(PaymentOrderModel.status.in_(["created", "creating"])).scalar() or 0,
    }


@router.get("/admin/customers")
def admin_customers(
    q: Optional[str] = None,
    limit: int = 50,
    skip: int = 0,
    admin: UserModel = Depends(require_admin),
    db: Session = Depends(get_db_session),
):
    limit = max(1, min(limit, 100))
    query = db.query(UserModel)
    if q:
        pattern = f"%{q.strip().lower()}%"
        query = query.filter(or_(func.lower(UserModel.email).like(pattern), func.lower(UserModel.full_name).like(pattern)))
    total = query.count()
    users = query.order_by(UserModel.created_at.desc()).offset(skip).limit(limit).all()
    customers = []
    for user in users:
        sub = db.query(SubscriptionModel).filter(
            SubscriptionModel.user_id == user.id,
            SubscriptionModel.status == "active",
        ).order_by(SubscriptionModel.created_at.desc()).first()
        gmail_count = db.query(func.count(GmailConnectionModel.id)).filter(GmailConnectionModel.user_id == user.id, GmailConnectionModel.active == True).scalar() or 0
        channels = [x.type for x in db.query(NotificationIntegrationModel).filter(NotificationIntegrationModel.user_id == user.id, NotificationIntegrationModel.is_active == True).all()]
        month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        usage = db.query(func.count(UsageEventModel.id)).filter(
            UsageEventModel.user_id == user.id,
            UsageEventModel.period_start == month_start,
            UsageEventModel.status.in_(["reserved", "sent"]),
        ).scalar() or 0
        customers.append({
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "is_active": user.is_active,
            "is_verified": user.is_verified,
            "is_admin": user.is_admin,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "plan_code": sub.plan_code if sub else "basic",
            "subscription_status": sub.status if sub else "default",
            "gmail_accounts": int(gmail_count),
            "channels": channels,
            "notifications_used": int(usage),
            "notifications_limit": PLAN_CATALOG[sub.plan_code if sub else "basic"]["monthly_notifications"],
        })
    return {"customers": customers, "total": total, "limit": limit, "skip": skip}


@router.get("/admin/orders")
def admin_orders(
    limit: int = 50,
    admin: UserModel = Depends(require_admin),
    db: Session = Depends(get_db_session),
):
    limit = max(1, min(limit, 100))
    rows = db.query(PaymentOrderModel).order_by(PaymentOrderModel.created_at.desc()).limit(limit).all()
    return {"orders": [{
        "id": row.id,
        "user_id": row.user_id,
        "customer_email": db.query(UserModel.email).filter(UserModel.id == row.user_id).scalar(),
        "plan_code": row.plan_code,
        "provider": row.provider,
        "provider_order_id": row.provider_order_id,
        "provider_payment_id": row.provider_payment_id,
        "amount_paise": row.amount_paise,
        "currency": row.currency,
        "status": row.status,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "paid_at": row.paid_at.isoformat() if row.paid_at else None,
    } for row in rows]}

@router.patch("/admin/customers/{user_id}")
def admin_update_customer(
    user_id: str,
    req: AdminCustomerUpdate,
    admin: UserModel = Depends(require_admin),
    db: Session = Depends(get_db_session),
):
    user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Customer not found.")
    if user.id == admin.id and req.is_active is False:
        raise HTTPException(status_code=400, detail="You cannot deactivate your own admin account.")
    if req.is_active is not None:
        user.is_active = req.is_active
    if req.plan_code:
        now = utc_now()
        for old in db.query(SubscriptionModel).filter(SubscriptionModel.user_id == user.id, SubscriptionModel.status == "active").all():
            old.status = "replaced"
        db.add(SubscriptionModel(
            user_id=user.id,
            plan_code=req.plan_code,
            status="active",
            current_period_start=now,
            current_period_end=datetime(2099, 1, 1, tzinfo=timezone.utc) if req.plan_code == "basic" else now + timedelta(days=30),
        ))
    db.commit()
    log_audit_event(db, event_type="admin_customer_updated", user_id=admin.id, details={"target_user_id": user.id, "is_active": req.is_active, "plan_code": req.plan_code})
    return {"message": "Customer updated.", "customer_id": user.id}
