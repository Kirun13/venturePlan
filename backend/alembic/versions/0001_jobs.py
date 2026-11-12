"""initial jobs and events
Revision ID: 0001
Revises:
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("plan_jobs", sa.Column("id", UUID(as_uuid=True), primary_key=True), sa.Column("status", sa.String(20), nullable=False, server_default="queued"), sa.Column("input_data", sa.JSON(), nullable=False), sa.Column("result_data", sa.JSON()), sa.Column("error", sa.Text()), sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("started_at", sa.DateTime(timezone=True)), sa.Column("finished_at", sa.DateTime(timezone=True)), sa.Column("lease_until", sa.DateTime(timezone=True)))
    op.create_index("ix_plan_jobs_status_created", "plan_jobs", ["status", "created_at"])
    op.create_table("job_events", sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True), sa.Column("job_id", UUID(as_uuid=True), sa.ForeignKey("plan_jobs.id", ondelete="CASCADE"), nullable=False), sa.Column("kind", sa.String(32), nullable=False), sa.Column("message", sa.Text(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_index("ix_job_events_job_id", "job_events", ["job_id"])

def downgrade():
    op.drop_table("job_events")
    op.drop_table("plan_jobs")
