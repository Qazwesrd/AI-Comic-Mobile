"""Add independent AI video editing workspace tables.

Revision ID: 20261119_0003
Revises: 20261119_0002
"""
from alembic import op

revision = "20261119_0003"
down_revision = "20261119_0002"
branch_labels = None
depends_on = None


def upgrade():
    from app.database import Base
    from app import models  # noqa: F401
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade():
    # Keep user editing history intact; destructive downgrade is intentionally disabled.
    pass
