"""Add visual asset relation to story entities.

Revision ID: 20261119_0002
Revises: 20261119_0001
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "20261119_0002"
down_revision = "20261119_0001"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    from app.database import Base
    from app import models  # noqa: F401
    Base.metadata.create_all(bind=bind, checkfirst=True)
    if inspect(bind).has_table("story_entities"):
        columns = {column["name"] for column in inspect(bind).get_columns("story_entities")}
        if "visual_asset_id" not in columns:
            op.add_column("story_entities", sa.Column("visual_asset_id", sa.Integer(), nullable=True))
            with op.batch_alter_table("story_entities") as batch:
                batch.create_foreign_key(
                    "fk_story_entities_visual_asset_id_media_assets",
                    "media_assets", ["visual_asset_id"], ["id"], ondelete="SET NULL",
                )


def downgrade():
    pass
