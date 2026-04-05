# alembic/versions/0002_add_threats.py
"""add threats table

Revision ID: 0002_add_threats
Revises: 0001_create_tables
Create Date: 2025-12-08 00:10:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0002_add_threats"
down_revision = "0001_create_tables"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "threats",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("org_id", sa.Integer(), sa.ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("crawled_page_id", sa.Integer(), sa.ForeignKey("crawled_pages.id", ondelete="CASCADE"), nullable=True),
        sa.Column("indicator_type", sa.String(length=100), nullable=False),
        sa.Column("indicator", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False, server_default=sa.text("'low'")),
        sa.Column("evidence", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )

def downgrade():
    op.drop_table("threats")
