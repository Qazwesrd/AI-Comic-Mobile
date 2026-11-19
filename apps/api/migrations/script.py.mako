"""\u007bmessage\u007d

Revision ID: \u007brevision\u007d
Revises: \u007bdown_revision | comma,n\u007d
Create Date: \u007bcreate_date\u007d

"""
from alembic import op
import sqlalchemy as sa
\u007bimports if imports\u007d

revision = \u007brevision\u007d
down_revision = \u007bdown_revision\u007d
branch_labels = \u007bbranch_labels\u007d
depends_on = \u007bdepends_on\u007d


def upgrade():
    \u007bupgrades if upgrades else 'pass'\u007d


def downgrade():
    \u007bdowngrades if downgrades else 'pass'\u007d
