"""add_garmin_fields_and_encrypt_tokens

Revision ID: 728acc5f0965
Revises: 7665bd301d46
Create Date: 2026-01-05 07:22:11.086551

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '728acc5f0965'
down_revision: Union[str, None] = '7665bd301d46'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add Garmin fields to athlete table
    op.add_column('athlete', sa.Column('garmin_username', sa.Text(), nullable=True))
    op.add_column('athlete', sa.Column('garmin_password_encrypted', sa.Text(), nullable=True))
    op.add_column('athlete', sa.Column('garmin_connected', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('athlete', sa.Column('last_garmin_sync', sa.DateTime(timezone=True), nullable=True))
    op.add_column('athlete', sa.Column('garmin_sync_enabled', sa.Boolean(), server_default='true', nullable=False))
    
    # Add recovery metrics to daily_checkin table
    op.add_column('daily_checkin', sa.Column('hrv_rmssd', sa.Numeric(), nullable=True))  # HRV rMSSD value
    op.add_column('daily_checkin', sa.Column('hrv_sdnn', sa.Numeric(), nullable=True))  # HRV SDNN value
    op.add_column('daily_checkin', sa.Column('resting_hr', sa.Integer(), nullable=True))  # Resting heart rate
    op.add_column('daily_checkin', sa.Column('overnight_avg_hr', sa.Numeric(), nullable=True))  # Overnight average HR
    
    # Note: Token encryption migration will be handled by a data migration script
    # Existing tokens will be encrypted on first access


def downgrade() -> None:
    op.drop_column('daily_checkin', 'overnight_avg_hr')
    op.drop_column('daily_checkin', 'resting_hr')
    op.drop_column('daily_checkin', 'hrv_sdnn')
    op.drop_column('daily_checkin', 'hrv_rmssd')
    op.drop_column('athlete', 'garmin_sync_enabled')
    op.drop_column('athlete', 'last_garmin_sync')
    op.drop_column('athlete', 'garmin_connected')
    op.drop_column('athlete', 'garmin_password_encrypted')
    op.drop_column('athlete', 'garmin_username')




