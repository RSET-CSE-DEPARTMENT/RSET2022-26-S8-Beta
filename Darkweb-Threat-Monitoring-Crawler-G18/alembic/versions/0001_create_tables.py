"""create initial tables

Revision ID: 0001_create_tables
Revises: 
Create Date: 2025-12-08 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0001_create_tables"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # orgs table
    op.create_table(
        "orgs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=255), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )

    # queries table
    op.create_table(
        "queries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("org_id", sa.Integer(), sa.ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=True),
        sa.Column("q_text", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=50), server_default=sa.text("'created'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )

    # crawled_pages table
    op.create_table(
        "crawled_pages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("org_id", sa.Integer(), sa.ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("query_id", sa.Integer(), sa.ForeignKey("queries.id", ondelete="SET NULL"), nullable=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("content_snippet", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )

def downgrade():
    op.drop_table("crawled_pages")
    op.drop_table("queries")
    op.drop_table("orgs")
