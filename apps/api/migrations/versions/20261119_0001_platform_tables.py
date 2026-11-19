"""Add email verification, recovery, commerce and platform tables.

Revision ID: 20261119_0001
Revises:
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "20261119_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    columns = {c["name"] for c in inspect(bind).get_columns("users")} if inspect(bind).has_table("users") else set()
    if "email_verified" not in columns and columns:
        op.add_column("users", sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.false()))
    if "is_admin" not in columns and columns:
        op.add_column("users", sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()))

    from app.database import Base
    from app import models  # noqa: F401
    Base.metadata.create_all(bind=bind, checkfirst=True)


def downgrade():
    # Downgrade is intentionally conservative; user/order history must not be dropped automatically.
    pass
