from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "0003_add_clean_text"
down_revision = "0002_add_threats"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column(
        "crawled_pages",
        sa.Column("clean_text", sa.Text(), nullable=True)
    )

def downgrade():
    op.drop_column("crawled_pages", "clean_text")
