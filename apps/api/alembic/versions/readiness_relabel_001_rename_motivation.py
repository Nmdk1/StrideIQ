"""Rename motivation_1_5 to readiness_1_5

Column rename on daily_checkin (metadata-only, no table rewrite).
Update historical CorrelationFinding rows.

Revision ID: readiness_relabel_001
Revises: correlation_layers_001
Create Date: 2026-03-03
"""
from alembic import op

revision = 'readiness_relabel_001'
down_revision = 'correlation_layers_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column('daily_checkin', 'motivation_1_5',
                    new_column_name='readiness_1_5')

    op.execute("""
        UPDATE correlation_finding
        SET input_name = 'readiness_1_5'
        WHERE input_name = 'motivation_1_5'
    """)


def downgrade() -> None:
    op.alter_column('daily_checkin', 'readiness_1_5',
                    new_column_name='motivation_1_5')

    op.execute("""
        UPDATE correlation_finding
        SET input_name = 'motivation_1_5'
        WHERE input_name = 'readiness_1_5'
    """)
