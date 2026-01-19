"""Add N=1 learning tables for workout selection

Revision ID: n1_learning_001
Revises: calendar_system_001
Create Date: 2026-01-17

Creates tables for the N=1 Learning Workout Selection Engine (ADR-036):
- athlete_calibrated_model: Persisted Banister model calibration
- athlete_workout_response: Stimulus type → response tracking
- athlete_learning: Banked intelligence (what works, what doesn't, injury triggers)
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision = 'n1_learning_001'
down_revision = 'calendar_system_001'
branch_labels = None
depends_on = None


def upgrade():
    # Add feature flag for 3D workout selection (initially disabled, 0% rollout)
    op.execute("""
        INSERT INTO feature_flag (id, key, name, description, enabled, rollout_percentage)
        VALUES (
            gen_random_uuid(),
            'plan.3d_workout_selection',
            'N=1 Workout Selection Engine',
            'ADR-036: Uses N=1 Learning Workout Selector for quality sessions instead of hardcoded prescriptions. Phase is a soft weight, selection informed by athlete response history and banked intelligence.',
            true,
            0
        )
        ON CONFLICT (key) DO NOTHING;
    """)
    
    # Create athlete_calibrated_model table
    # Persists Banister model calibration instead of recalculating each time
    op.create_table(
        'athlete_calibrated_model',
        sa.Column('athlete_id', UUID(as_uuid=True), sa.ForeignKey('athlete.id'), primary_key=True),
        
        # Banister parameters
        sa.Column('tau1', sa.Float(), nullable=False),  # Fitness decay (days)
        sa.Column('tau2', sa.Float(), nullable=False),  # Fatigue decay (days)
        sa.Column('k1', sa.Float(), nullable=False),    # Fitness scaling
        sa.Column('k2', sa.Float(), nullable=False),    # Fatigue scaling
        sa.Column('p0', sa.Float(), nullable=False),    # Baseline performance
        
        # Fit quality
        sa.Column('r_squared', sa.Float(), nullable=True),
        sa.Column('fit_error', sa.Float(), nullable=True),
        sa.Column('n_performance_markers', sa.Integer(), nullable=True),
        sa.Column('n_training_days', sa.Integer(), nullable=True),
        
        # Confidence and tier
        sa.Column('confidence', sa.Text(), nullable=False),  # 'high', 'moderate', 'low', 'uncalibrated'
        sa.Column('data_tier', sa.Text(), nullable=False),   # 'uncalibrated', 'learning', 'calibrated'
        sa.Column('confidence_notes', JSONB(), nullable=True),  # List of notes about calibration
        
        # Lifecycle
        sa.Column('calibrated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('valid_until', sa.Date(), nullable=True),  # Recalibrate after new race
    )
    
    # Create athlete_workout_response table
    # Tracks how an athlete responds to different workout stimulus types
    op.create_table(
        'athlete_workout_response',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('athlete_id', UUID(as_uuid=True), sa.ForeignKey('athlete.id'), nullable=False),
        sa.Column('stimulus_type', sa.Text(), nullable=False),  # 'intervals', 'continuous', 'hills', etc.
        
        # Aggregated response signals
        sa.Column('avg_rpe_gap', sa.Float(), nullable=True),       # mean(actual_rpe - expected_rpe)
        sa.Column('rpe_gap_stddev', sa.Float(), nullable=True),    # Consistency of RPE response
        sa.Column('completion_rate', sa.Float(), nullable=True),   # Fraction completed as prescribed
        sa.Column('adaptation_signal', sa.Float(), nullable=True), # EF trend post-workout (future)
        
        # Sample size
        sa.Column('n_observations', sa.Integer(), nullable=False, server_default='0'),
        
        # Timestamps
        sa.Column('first_observation', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_updated', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    
    op.create_index('ix_athlete_workout_response_athlete_id', 'athlete_workout_response', ['athlete_id'])
    op.create_index('ix_athlete_workout_response_stimulus', 'athlete_workout_response', ['stimulus_type'])
    op.create_unique_constraint('uq_athlete_stimulus_response', 'athlete_workout_response', ['athlete_id', 'stimulus_type'])
    
    # Create athlete_learning table
    # Banked learnings about what works/doesn't work for an athlete
    op.create_table(
        'athlete_learning',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('athlete_id', UUID(as_uuid=True), sa.ForeignKey('athlete.id'), nullable=False),
        
        # Learning classification
        sa.Column('learning_type', sa.Text(), nullable=False),  # 'what_works', 'what_doesnt_work', 'injury_trigger', 'preference'
        sa.Column('subject', sa.Text(), nullable=False),        # template_id, stimulus_type, or pattern description
        
        # Evidence and confidence
        sa.Column('evidence', JSONB(), nullable=True),       # Supporting data (build_ids, outcomes, etc.)
        sa.Column('confidence', sa.Float(), nullable=False, server_default='0.5'),  # 0-1, increases with repeated observations
        
        # Provenance
        sa.Column('discovered_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('source', sa.Text(), nullable=False),         # 'rpe_analysis', 'race_outcome', 'user_feedback', 'injury_correlation'
        
        # Lifecycle
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('superseded_by', UUID(as_uuid=True), sa.ForeignKey('athlete_learning.id'), nullable=True),
    )
    
    op.create_index('ix_athlete_learning_athlete_id', 'athlete_learning', ['athlete_id'])
    op.create_index('ix_athlete_learning_type', 'athlete_learning', ['learning_type'])
    op.create_index('ix_athlete_learning_subject', 'athlete_learning', ['subject'])
    op.create_index('ix_athlete_learning_active', 'athlete_learning', ['is_active'])


def downgrade():
    op.drop_table('athlete_learning')
    op.drop_table('athlete_workout_response')
    op.drop_table('athlete_calibrated_model')
