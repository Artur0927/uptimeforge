"""Create monitors and check history."""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "monitors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("interval_seconds", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(8), nullable=False),
        sa.Column("status_code", sa.Integer()),
        sa.Column("response_time_ms", sa.Float()),
        sa.Column("last_checked_at", sa.DateTime(timezone=True)),
        sa.Column("next_check_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("interval_seconds BETWEEN 30 AND 86400", name="valid_interval"),
        sa.CheckConstraint("status IN ('PENDING', 'UP', 'DOWN')", name="valid_monitor_status"),
    )
    op.create_index("ix_monitors_next_check_at", "monitors", ["next_check_at"])
    op.create_table(
        "check_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "monitor_id",
            sa.Integer(),
            sa.ForeignKey("monitors.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(8), nullable=False),
        sa.Column("status_code", sa.Integer()),
        sa.Column("response_time_ms", sa.Float(), nullable=False),
        sa.Column("target_url", sa.String(2048), nullable=False),
        sa.Column("error", sa.String(200)),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('UP', 'DOWN')", name="valid_check_status"),
    )
    op.create_index(
        "ix_check_results_monitor_time", "check_results", ["monitor_id", "checked_at", "id"]
    )
    op.create_index("ix_check_results_time", "check_results", ["checked_at", "id"])


def downgrade():
    # Dropping these tables is intentional only when an operator requests a downgrade.
    op.drop_table("check_results")
    op.drop_table("monitors")
