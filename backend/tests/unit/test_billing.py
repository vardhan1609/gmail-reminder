import base64
import hashlib
import hmac

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
    timestamp = "1761900000"
    signature = base64.b64encode(
        hmac.new(b"test-secret", timestamp.encode() + body, hashlib.sha256).digest()
    ).decode()
    headers = {"x-webhook-signature": signature, "x-webhook-timestamp": timestamp}
    assert CashfreeAdapter().verify_webhook(body, headers)
    assert not CashfreeAdapter().verify_webhook(body, {"x-webhook-signature": "invalid"})
