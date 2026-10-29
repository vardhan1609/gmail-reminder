"""add_theme_preference_to_preferences

Revision ID: c3d4e5f6a7b8
Revises: 8f1e1f1290a1
Create Date: 2026-10-30 00:52:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = '8f1e1f1290a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'notification_preferences',
        sa.Column('theme_preference', sa.String(length=20), nullable=False, server_default='system')
    )


def downgrade() -> None:
    op.drop_column('notification_preferences', 'theme_preference')

