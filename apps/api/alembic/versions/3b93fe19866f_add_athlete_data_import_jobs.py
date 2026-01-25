"""add athlete data import jobs

Revision ID: 3b93fe19866f
Revises: ab12cd34ef56
Create Date: 2026-01-25 08:54:48.494331

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '3b93fe19866f'
down_revision: Union[str, None] = 'ab12cd34ef56'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "athlete_data_import_job",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("athlete_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("athlete.id"), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),  # 'garmin' | 'coros'
        sa.Column("status", sa.Text(), nullable=False),  # 'queued'|'running'|'success'|'error'
        sa.Column("original_filename", sa.Text(), nullable=True),
        sa.Column("stored_path", sa.Text(), nullable=True),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("file_sha256", sa.Text(), nullable=True),
        sa.Column("stats", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("error", sa.Text(), nullable=True),
    )

    op.create_index("ix_athlete_data_import_job_created_at", "athlete_data_import_job", ["created_at"], unique=False)
    op.create_index("ix_athlete_data_import_job_athlete_id", "athlete_data_import_job", ["athlete_id"], unique=False)
    op.create_index("ix_athlete_data_import_job_provider", "athlete_data_import_job", ["provider"], unique=False)
    op.create_index("ix_athlete_data_import_job_status", "athlete_data_import_job", ["status"], unique=False)
    op.create_index("ix_athlete_data_import_job_file_sha256", "athlete_data_import_job", ["file_sha256"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_athlete_data_import_job_file_sha256", table_name="athlete_data_import_job")
    op.drop_index("ix_athlete_data_import_job_status", table_name="athlete_data_import_job")
    op.drop_index("ix_athlete_data_import_job_provider", table_name="athlete_data_import_job")
    op.drop_index("ix_athlete_data_import_job_athlete_id", table_name="athlete_data_import_job")
    op.drop_index("ix_athlete_data_import_job_created_at", table_name="athlete_data_import_job")
    op.drop_table("athlete_data_import_job")




