"""seed provider import flags

Revision ID: b39bc8e9ddf1
Revises: 3b93fe19866f
Create Date: 2026-01-25 09:11:21.956144

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b39bc8e9ddf1'
down_revision: Union[str, None] = '3b93fe19866f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Phase 7: Provider file import flags (default OFF).
    op.execute(
        sa.text(
            """
            INSERT INTO feature_flag
                (key, name, description, enabled, requires_subscription, requires_tier, requires_payment, rollout_percentage, allowed_athlete_ids)
            VALUES
                ('integrations.garmin_file_import_v1', 'Garmin file import (v1)', 'Upload Garmin export zip and import activities asynchronously.', false, false, null, null, 100, null),
                ('integrations.coros_file_import_v1',  'COROS file import (v1)',  'Upload COROS export zip and import activities asynchronously.', false, false, null, null, 100, null),
                ('integrations.garmin_password_connect_legacy', 'Garmin password connect (legacy)', 'Deprecated: legacy username/password Garmin Connect sync. Keep disabled.', false, false, null, null, 100, null)
            ON CONFLICT (key) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            DELETE FROM feature_flag
            WHERE key IN (
                'integrations.garmin_file_import_v1',
                'integrations.coros_file_import_v1',
                'integrations.garmin_password_connect_legacy'
            )
            """
        )
    )




