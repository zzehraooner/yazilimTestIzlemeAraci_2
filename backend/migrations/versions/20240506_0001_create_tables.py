"""create monitoring tables

Revision ID: 20240506_0001
Revises:
Create Date: 2024-05-06 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20240506_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "test_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("command", sa.Text(), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('utc', now())"),
            nullable=False,
        ),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="running"),
        sa.Column("exit_code", sa.Integer(), nullable=True),
        sa.Column("baseline_run_id", sa.Integer(), sa.ForeignKey("test_runs.id"), nullable=True),
    )
    op.create_index("ix_test_runs_started_at", "test_runs", ["started_at"])

    op.create_table(
        "metric_samples",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "run_id",
            sa.Integer(),
            sa.ForeignKey("test_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cpu_percent", sa.Float(), nullable=False),
        sa.Column("rss_mb", sa.Float(), nullable=False),
    )
    op.create_index("ix_metric_samples_run_id", "metric_samples", ["run_id"])
    op.create_index("ix_metric_samples_ts", "metric_samples", ["ts"])

    op.create_table(
        "run_stats",
        sa.Column(
            "run_id",
            sa.Integer(),
            sa.ForeignKey("test_runs.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("avg_cpu", sa.Float(), nullable=True),
        sa.Column("p95_cpu", sa.Float(), nullable=True),
        sa.Column("max_cpu", sa.Float(), nullable=True),
        sa.Column("avg_rss_mb", sa.Float(), nullable=True),
        sa.Column("p95_rss_mb", sa.Float(), nullable=True),
        sa.Column("duration_s", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("run_stats")
    op.drop_index("ix_metric_samples_ts", table_name="metric_samples")
    op.drop_index("ix_metric_samples_run_id", table_name="metric_samples")
    op.drop_table("metric_samples")
    op.drop_index("ix_test_runs_started_at", table_name="test_runs")
    op.drop_table("test_runs")
