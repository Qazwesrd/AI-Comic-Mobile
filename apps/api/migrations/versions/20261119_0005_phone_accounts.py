"""Add optional mainland phone identity to user accounts.

Revision ID: 20261119_0005
Revises: 20261119_0004
"""
from alembic import op
import sqlalchemy as sa

revision = "20261119_0005"
down_revision = "20261119_0004"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users") as batch:
        batch.alter_column("email", existing_type=sa.String(length=320), nullable=True)
        batch.add_column(sa.Column("phone", sa.String(length=20), nullable=True))
        batch.add_column(sa.Column("phone_verified", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.create_index("ix_users_phone", ["phone"], unique=True)


def downgrade():
    # Phone-only accounts cannot be represented by the previous schema.
    # Keep their identity data rather than destructively removing these columns.
    pass
