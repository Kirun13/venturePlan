"""Users, sessions, project versions and node telemetry."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("auth_limits", sa.Column("key", sa.String(64), primary_key=True),
                    sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
                    sa.Column("attempts", sa.Integer(), nullable=False))
    op.create_table("users", sa.Column("id", UUID(as_uuid=True), primary_key=True),
                    sa.Column("email", sa.String(254), unique=True, nullable=False),
                    sa.Column("password_hash", sa.Text(), nullable=False),
                    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_table("user_sessions", sa.Column("token_hash", sa.String(64), primary_key=True),
                    sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
                    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])
    op.create_table("projects", sa.Column("id", UUID(as_uuid=True), primary_key=True),
                    sa.Column("owner_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
                    sa.Column("name", sa.String(120), nullable=False),
                    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_projects_owner_id", "projects", ["owner_id"])
    op.add_column("plan_jobs", sa.Column("owner_id", UUID(as_uuid=True), sa.ForeignKey("users.id")))
    op.add_column("plan_jobs", sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id")))
    op.add_column("plan_jobs", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    op.create_index("ix_plan_jobs_owner_id", "plan_jobs", ["owner_id"])
    op.create_index("ix_plan_jobs_project_id", "plan_jobs", ["project_id"])
    op.create_unique_constraint("uq_project_version", "plan_jobs", ["project_id", "version"])
    op.add_column("job_events", sa.Column("node", sa.String(32)))
    op.add_column("job_events", sa.Column("attempt", sa.Integer()))
    op.add_column("job_events", sa.Column("details", sa.JSON(), nullable=False, server_default="{}"))

def downgrade():
    for column in ("details", "attempt", "node"):
        op.drop_column("job_events", column)
    op.drop_constraint("uq_project_version", "plan_jobs")
    for column in ("version", "project_id", "owner_id"):
        op.drop_column("plan_jobs", column)
    for table in ("projects", "user_sessions", "users", "auth_limits"):
        op.drop_table(table)
