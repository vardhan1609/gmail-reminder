"""Add subscription billing, payment orders and monthly usage metering.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("plan_code", sa.String(length=30), nullable=False, server_default="basic"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="active"),
        sa.Column("payment_provider", sa.String(length=30), nullable=True),
        sa.Column("provider_customer_id", sa.String(length=255), nullable=True),
        sa.Column("provider_subscription_id", sa.String(length=255), nullable=True),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_subscriptions_user_id", "subscriptions", ["user_id"])
    op.create_index("ix_subscriptions_plan_code", "subscriptions", ["plan_code"])
    op.create_index("ix_subscriptions_status", "subscriptions", ["status"])

    op.create_table(
        "payment_orders",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("plan_code", sa.String(length=30), nullable=False),
        sa.Column("provider", sa.String(length=30), nullable=False),
        sa.Column("provider_order_id", sa.String(length=255), nullable=True),
        sa.Column("amount_paise", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="INR"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="created"),
        sa.Column("checkout_url", sa.Text(), nullable=True),
        sa.Column("provider_payment_id", sa.String(length=255), nullable=True),
        sa.Column("raw_webhook", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_order_id"),
    )
    op.create_index("ix_payment_orders_user_id", "payment_orders", ["user_id"])
    op.create_index("ix_payment_orders_provider", "payment_orders", ["provider"])
    op.create_index("ix_payment_orders_provider_order_id", "payment_orders", ["provider_order_id"])
    op.create_index("ix_payment_orders_status", "payment_orders", ["status"])

    op.create_table(
        "subscription_usage_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("usage_type", sa.String(length=50), nullable=False, server_default="notification"),
        sa.Column("channel", sa.String(length=30), nullable=True),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="reserved"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "idempotency_key", name="uq_usage_user_idempotency"),
    )
    op.create_index("ix_subscription_usage_events_user_id", "subscription_usage_events", ["user_id"])
    op.create_index("ix_subscription_usage_events_period_start", "subscription_usage_events", ["period_start"])
    op.create_index("ix_usage_user_period_status", "subscription_usage_events", ["user_id", "period_start", "status"])


def downgrade() -> None:
    op.drop_index("ix_usage_user_period_status", table_name="subscription_usage_events")
    op.drop_index("ix_subscription_usage_events_period_start", table_name="subscription_usage_events")
    op.drop_index("ix_subscription_usage_events_user_id", table_name="subscription_usage_events")
    op.drop_table("subscription_usage_events")
    op.drop_index("ix_payment_orders_status", table_name="payment_orders")
    op.drop_index("ix_payment_orders_provider_order_id", table_name="payment_orders")
    op.drop_index("ix_payment_orders_provider", table_name="payment_orders")
    op.drop_index("ix_payment_orders_user_id", table_name="payment_orders")
    op.drop_table("payment_orders")
    op.drop_index("ix_subscriptions_status", table_name="subscriptions")
    op.drop_index("ix_subscriptions_plan_code", table_name="subscriptions")
    op.drop_index("ix_subscriptions_user_id", table_name="subscriptions")
    op.drop_table("subscriptions")
