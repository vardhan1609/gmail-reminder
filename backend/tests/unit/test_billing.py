import base64
import hashlib
import hmac
from datetime import datetime, timezone

from app.config import settings
from app.services.billing import (
    PLAN_CATALOG,
    CashfreeAdapter,
    RazorpayAdapter,
    get_payment_adapter,
)


def test_basic_and_premium_plan_entitlements():
    basic = PLAN_CATALOG["basic"]
    premium = PLAN_CATALOG["premium"]

    assert basic["gmail_accounts"] == 1
    assert basic["monthly_notifications"] == 100
    assert basic["channels"] == ["telegram"]
    assert basic["google_calendar"] is True
    assert basic["whatsapp"] is False

    assert premium["gmail_accounts"] == 4
    assert premium["monthly_notifications"] == 500
    assert premium["channels"] == ["telegram", "whatsapp"]
    assert premium["google_calendar"] is True
    assert premium["whatsapp"] is True


def test_payment_adapter_factory():
    assert isinstance(get_payment_adapter("razorpay"), RazorpayAdapter)
    assert isinstance(get_payment_adapter("cashfree"), CashfreeAdapter)


def test_razorpay_webhook_signature(monkeypatch):
    monkeypatch.setattr(settings, "razorpay_webhook_secret", "test-secret")
    body = b'{"event":"payment_link.paid"}'
    signature = hmac.new(b"test-secret", body, hashlib.sha256).hexdigest()
    assert RazorpayAdapter().verify_webhook(body, {"x-razorpay-signature": signature})
    assert not RazorpayAdapter().verify_webhook(body, {"x-razorpay-signature": "invalid"})


def test_cashfree_webhook_signature(monkeypatch):
    monkeypatch.setattr(settings, "cashfree_webhook_secret", "test-secret")
    body = b'{"type":"PAYMENT_LINK_EVENT"}'
    timestamp = str(int(datetime.now(timezone.utc).timestamp()))
    signature = base64.b64encode(
        hmac.new(b"test-secret", timestamp.encode() + body, hashlib.sha256).digest()
    ).decode()
    headers = {"x-webhook-signature": signature, "x-webhook-timestamp": timestamp}
    assert CashfreeAdapter().verify_webhook(body, headers)
    assert not CashfreeAdapter().verify_webhook(body, {"x-webhook-signature": "invalid"})

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.db_models import Base, SubscriptionModel, UserModel
import app.services.billing as billing


def test_basic_monthly_quota_and_whatsapp_gate(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(billing, "SessionLocal", TestSession)

    with TestSession() as db:
        user = UserModel(
            email="billing-test@example.com",
            password_hash="not-used",
            is_verified=True,
            is_active=True,
            is_admin=False,
            mfa_enabled=False,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        db.add(SubscriptionModel(
            user_id=user.id,
            plan_code="basic",
            status="active",
            current_period_start=datetime.now(timezone.utc),
            current_period_end=datetime(2099, 1, 1, tzinfo=timezone.utc),
        ))
        db.commit()
        user_id = user.id

    allowed, reason = billing.reserve_notification_usage(user_id, "whatsapp-test", "whatsapp")
    assert not allowed
    assert "Premium" in reason

    for index in range(100):
        key = f"basic-quota-{index}"
        allowed, reason = billing.reserve_notification_usage(user_id, key, "telegram")
        assert allowed, reason
        billing.finish_notification_usage(user_id, key, True)

    allowed, reason = billing.reserve_notification_usage(user_id, "basic-quota-over", "telegram")
    assert not allowed
    assert "100" in reason
    engine.dispose()
