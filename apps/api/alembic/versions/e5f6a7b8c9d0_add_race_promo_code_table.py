"""Add race_promo_code table for race QR activation

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-01-31

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'e5f6a7b8c9d0'
down_revision = 'd4e5f6a7b8c9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create race_promo_code table
    op.create_table(
        'race_promo_code',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('code', sa.Text(), nullable=False, unique=True),
        sa.Column('race_name', sa.Text(), nullable=False),
        sa.Column('race_date', sa.Date(), nullable=True),
        sa.Column('trial_days', sa.Integer(), nullable=False, server_default='30'),
        sa.Column('valid_from', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('valid_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('max_uses', sa.Integer(), nullable=True),
        sa.Column('current_uses', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('athlete.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    
    # Create indexes
    op.create_index('ix_race_promo_code_code', 'race_promo_code', ['code'])
    op.create_index('ix_race_promo_code_is_active', 'race_promo_code', ['is_active'])
    
    # Add race_promo_code_id to athlete for attribution tracking
    op.add_column('athlete', sa.Column('race_promo_code_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        'fk_athlete_race_promo_code',
        'athlete', 'race_promo_code',
        ['race_promo_code_id'], ['id']
    )


def downgrade() -> None:
    op.drop_constraint('fk_athlete_race_promo_code', 'athlete', type_='foreignkey')
    op.drop_column('athlete', 'race_promo_code_id')
    op.drop_index('ix_race_promo_code_is_active', 'race_promo_code')
    op.drop_index('ix_race_promo_code_code', 'race_promo_code')
    op.drop_table('race_promo_code')
