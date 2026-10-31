"""Plan entitlements, monthly metering and provider-neutral hosted checkout adapters."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

import httpx
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.database.session import SessionLocal
from app.models.db_models import (
    GmailConnectionModel, NotificationIntegrationModel, PaymentOrderModel,
    SubscriptionModel, UsageEventModel, UserModel, utc_now,
)

PLAN_CATALOG = {
    "basic": {
        "name": "Basic",
        "gmail_accounts": 1,
        "monthly_notifications": 100,
        "channels": ["telegram"],
        "google_calendar": True,
        "whatsapp": False,
    },
    "premium": {
        "name": "Premium",
        "gmail_accounts": 4,
        "monthly_notifications": 500,
        "channels": ["telegram", "whatsapp"],
        "google_calendar": True,
        "whatsapp": True,
    },
}


def plan_price_paise(plan_code: str) -> int:
    return int(settings.basic_plan_price_paise if plan_code == "basic" else settings.premium_plan_price_paise)


def get_active_subscription(db, user_id: str) -> SubscriptionModel:
    now = utc_now()
    sub = (
        db.query(SubscriptionModel)
        .filter(SubscriptionModel.user_id == user_id, SubscriptionModel.status == "active")
        .order_by(SubscriptionModel.created_at.desc())
        .first()
    )
    if sub and sub.current_period_end > now:
        return sub
    # Basic is the default entry tier until a paid plan is purchased.
    if sub:
        sub.status = "expired"
        db.commit()
    basic = SubscriptionModel(
        user_id=user_id,
        plan_code="basic",
        status="active",
        current_period_start=now,
        current_period_end=datetime(2099, 1, 1, tzinfo=timezone.utc),
    )
    db.add(basic)
    db.commit()
    db.refresh(basic)
    return basic


def subscription_payload(db, user_id: str) -> Dict[str, Any]:
    sub = get_active_subscription(db, user_id)
    plan = PLAN_CATALOG[sub.plan_code]
    start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    used = (
        db.query(func.count(UsageEventModel.id))
        .filter(
            UsageEventModel.user_id == user_id,
            UsageEventModel.period_start == start,
            UsageEventModel.status.in_(["reserved", "sent"]),
        )
        .scalar()
        or 0
    )
    return {
        "plan_code": sub.plan_code,
        "plan_name": plan["name"],
        "status": sub.status,
        "current_period_start": sub.current_period_start.isoformat(),
        "current_period_end": sub.current_period_end.isoformat(),
        "cancel_at_period_end": sub.cancel_at_period_end,
        "limits": plan,
        "usage": {"notifications_used": int(used), "notifications_limit": plan["monthly_notifications"]},
    }


def reserve_notification_usage(user_id: str, idempotency_key: str, channel: str) -> Tuple[bool, Optional[str]]:
    """Atomically reserve one monthly notification unit before delivery."""
    db = SessionLocal()
    try:
        sub = get_active_subscription(db, user_id)
        plan = PLAN_CATALOG[sub.plan_code]
        if channel in ("whatsapp", "whatsapp_meta") and not plan["whatsapp"]:
            return False, "WhatsApp is available on the Premium plan. Upgrade to continue."
        period_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        existing = db.query(UsageEventModel).filter(
            UsageEventModel.user_id == user_id,
            UsageEventModel.idempotency_key == idempotency_key,
        ).first()
        if existing and existing.status in ("reserved", "sent"):
            return True, None
        used = db.query(func.count(UsageEventModel.id)).filter(
            UsageEventModel.user_id == user_id,
            UsageEventModel.period_start == period_start,
            UsageEventModel.status.in_(["reserved", "sent"]),
        ).scalar() or 0
        if used >= plan["monthly_notifications"]:
            return False, f"Monthly notification limit reached ({plan['monthly_notifications']}). Upgrade your plan or wait until the next billing month."
        if existing:
            existing.status = "reserved"
            existing.period_start = period_start
            existing.channel = channel
        else:
            db.add(UsageEventModel(
                user_id=user_id,
                idempotency_key=idempotency_key,
                usage_type="notification",
                channel=channel,
                period_start=period_start,
                status="reserved",
            ))
        db.commit()
        return True, None
    except IntegrityError:
        db.rollback()
        return True, None
    finally:
        db.close()


def finish_notification_usage(user_id: str, idempotency_key: str, success: bool) -> None:
    db = SessionLocal()
    try:
        event = db.query(UsageEventModel).filter(
            UsageEventModel.user_id == user_id,
            UsageEventModel.idempotency_key == idempotency_key,
        ).first()
        if event:
            event.status = "sent" if success else "failed"
            db.commit()
    finally:
        db.close()


class PaymentAdapter:
    provider = "base"

    def create_checkout(self, *, order: PaymentOrderModel, user: UserModel, callback_url: str) -> Dict[str, str]:
        raise NotImplementedError

    def verify_webhook(self, body: bytes, headers: Dict[str, str]) -> bool:
        raise NotImplementedError


class RazorpayAdapter(PaymentAdapter):
    provider = "razorpay"

    def create_checkout(self, *, order, user, callback_url):
        if not settings.razorpay_key_id or not settings.razorpay_key_secret:
            raise RuntimeError("Razorpay credentials are not configured.")
        payload = {
            "amount": order.amount_paise,
            "currency": order.currency,
            "description": f"Gmail Reminder {order.plan_code.title()} monthly subscription",
            "customer": {"name": user.full_name or user.email, "email": user.email},
            "callback_url": callback_url,
            "callback_method": "get",
            "notes": {"internal_order_id": order.id, "user_id": user.id, "plan_code": order.plan_code},
        }
        response = httpx.post(
            "https://api.razorpay.com/v1/payment_links",
            auth=(settings.razorpay_key_id, settings.razorpay_key_secret),
            json=payload,
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()
        return {"provider_order_id": data["id"], "checkout_url": data["short_url"]}

    def verify_webhook(self, body, headers):
        supplied = headers.get("x-razorpay-signature", "")
        expected = hmac.new(settings.razorpay_webhook_secret.encode(), body, hashlib.sha256).hexdigest()
        return bool(settings.razorpay_webhook_secret and hmac.compare_digest(supplied, expected))


class CashfreeAdapter(PaymentAdapter):
    provider = "cashfree"

    def create_checkout(self, *, order, user, callback_url):
        if not settings.cashfree_app_id or not settings.cashfree_secret_key:
            raise RuntimeError("Cashfree credentials are not configured.")
        base = "https://sandbox.cashfree.com/pg" if settings.cashfree_environment == "sandbox" else "https://api.cashfree.com/pg"
        payload = {
            "link_id": f"gm-{order.id}",
            "link_amount": float(Decimal(order.amount_paise) / Decimal(100)),
            "link_currency": order.currency,
            "link_purpose": f"Gmail Reminder {order.plan_code.title()} monthly subscription",
            "customer_details": {"customer_email": user.email, "customer_name": user.full_name or user.email},
            "link_meta": {"return_url": callback_url, "notify_url": callback_url},
            "link_notify": {"send_email": True, "send_sms": False},
        }
        response = httpx.post(
            f"{base}/links",
            headers={
                "x-client-id": settings.cashfree_app_id,
                "x-client-secret": settings.cashfree_secret_key,
                "x-api-version": "2023-08-01",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()
        return {"provider_order_id": data["link_id"], "checkout_url": data["link_url"]}

    def verify_webhook(self, body, headers):
        supplied = headers.get("x-webhook-signature", "")
        timestamp = headers.get("x-webhook-timestamp", "")
        if not settings.cashfree_webhook_secret or not supplied or not timestamp:
            return False
        expected = base64.b64encode(
            hmac.new(settings.cashfree_webhook_secret.encode(), timestamp.encode() + body, hashlib.sha256).digest()
        ).decode()
        return hmac.compare_digest(supplied, expected)


def get_payment_adapter(provider: str) -> PaymentAdapter:
    normalized = provider.lower()
    if normalized == "razorpay":
        return RazorpayAdapter()
    if normalized == "cashfree":
        return CashfreeAdapter()
    raise ValueError("Payment provider must be razorpay or cashfree.")


def activate_paid_subscription(db, order: PaymentOrderModel, payment_id: Optional[str] = None) -> None:
    if order.status == "paid":
        return
    now = utc_now()
    for old in db.query(SubscriptionModel).filter(
        SubscriptionModel.user_id == order.user_id,
        SubscriptionModel.status == "active",
    ).all():
        old.status = "replaced"
    order.status = "paid"
    order.provider_payment_id = payment_id
    order.paid_at = now
    db.add(SubscriptionModel(
        user_id=order.user_id,
        plan_code=order.plan_code,
        status="active",
        payment_provider=order.provider,
        provider_subscription_id=order.provider_order_id,
        current_period_start=now,
        current_period_end=now + timedelta(days=30),
    ))
    db.commit()
