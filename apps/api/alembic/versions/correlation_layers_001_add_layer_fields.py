"""Add correlation engine layers 1-4 fields

Layer 1: Threshold Detection (6 columns)
Layer 2: Asymmetric Response (5 columns)
Layer 4: Decay Curves (3 columns)
Layer 3: Cascade Detection (CorrelationMediator table)

Revision ID: correlation_layers_001
Revises: correlation_quality_001
Create Date: 2026-03-03
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'correlation_layers_001'
down_revision = 'correlation_quality_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Layer 1: Threshold Detection
    op.add_column('correlation_finding', sa.Column('threshold_value', sa.Float(), nullable=True))
    op.add_column('correlation_finding', sa.Column('threshold_direction', sa.Text(), nullable=True))
    op.add_column('correlation_finding', sa.Column('r_below_threshold', sa.Float(), nullable=True))
    op.add_column('correlation_finding', sa.Column('r_above_threshold', sa.Float(), nullable=True))
    op.add_column('correlation_finding', sa.Column('n_below_threshold', sa.Integer(), nullable=True))
    op.add_column('correlation_finding', sa.Column('n_above_threshold', sa.Integer(), nullable=True))

    # Layer 2: Asymmetric Response
    op.add_column('correlation_finding', sa.Column('asymmetry_ratio', sa.Float(), nullable=True))
    op.add_column('correlation_finding', sa.Column('asymmetry_direction', sa.Text(), nullable=True))
    op.add_column('correlation_finding', sa.Column('effect_below_baseline', sa.Float(), nullable=True))
    op.add_column('correlation_finding', sa.Column('effect_above_baseline', sa.Float(), nullable=True))
    op.add_column('correlation_finding', sa.Column('baseline_value', sa.Float(), nullable=True))

    # Layer 4: Decay Curves
    op.add_column('correlation_finding', sa.Column('lag_profile', postgresql.JSONB(), nullable=True))
    op.add_column('correlation_finding', sa.Column('decay_half_life_days', sa.Float(), nullable=True))
    op.add_column('correlation_finding', sa.Column('decay_type', sa.Text(), nullable=True))

    # Layer 3: Cascade Detection — CorrelationMediator table
    op.create_table(
        'correlation_mediator',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('finding_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('correlation_finding.id'), nullable=False),
        sa.Column('mediator_variable', sa.Text(), nullable=False),
        sa.Column('direct_effect', sa.Float(), nullable=False),
        sa.Column('indirect_effect', sa.Float(), nullable=False),
        sa.Column('mediation_ratio', sa.Float(), nullable=False),
        sa.Column('is_full_mediation', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('detected_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_mediator_finding', 'correlation_mediator', ['finding_id'])


def downgrade() -> None:
    op.drop_index('ix_mediator_finding', table_name='correlation_mediator')
    op.drop_table('correlation_mediator')

    op.drop_column('correlation_finding', 'decay_type')
    op.drop_column('correlation_finding', 'decay_half_life_days')
    op.drop_column('correlation_finding', 'lag_profile')

    op.drop_column('correlation_finding', 'baseline_value')
    op.drop_column('correlation_finding', 'effect_above_baseline')
    op.drop_column('correlation_finding', 'effect_below_baseline')
    op.drop_column('correlation_finding', 'asymmetry_direction')
    op.drop_column('correlation_finding', 'asymmetry_ratio')

    op.drop_column('correlation_finding', 'n_above_threshold')
    op.drop_column('correlation_finding', 'n_below_threshold')
    op.drop_column('correlation_finding', 'r_above_threshold')
    op.drop_column('correlation_finding', 'r_below_threshold')
    op.drop_column('correlation_finding', 'threshold_direction')
    op.drop_column('correlation_finding', 'threshold_value')
