"""Add per-account encrypted AI provider configuration.

Revision ID: 20261119_0004
Revises: 20261119_0003
"""
from alembic import op

revision = "20261119_0004"
down_revision = "20261119_0003"
branch_labels = None
depends_on = None


def upgrade():
    from app.database import Base
    from app import models  # noqa: F401
    from app import ai_config_models  # noqa: F401
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade():
    # Keep configuration and usage history; removal is an explicit operator action.
    pass
