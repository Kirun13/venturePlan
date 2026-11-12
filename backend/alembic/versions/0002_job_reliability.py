"""Lease ownership, delayed retries and generation mode."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("plan_jobs", sa.Column("attempt_token", UUID(as_uuid=True)))
    op.add_column("plan_jobs", sa.Column("available_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.add_column("plan_jobs", sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"))
    # Older records do not contain reliable mode information.
    op.add_column("plan_jobs", sa.Column("agent_mode", sa.String(20), nullable=False, server_default="unknown"))
    op.alter_column("plan_jobs", "agent_mode", server_default="mock")


def downgrade():
    for column in ("agent_mode", "max_attempts", "available_at", "attempt_token"):
        op.drop_column("plan_jobs", column)
