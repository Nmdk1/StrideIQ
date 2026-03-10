"""Migrate StoredFingerprintFinding to AthleteFinding schema.

Living Fingerprint Spec — H1 resolution.
Keep tablename 'fingerprint_finding', rename model, add/rename/drop columns.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = 'lfp_003_finding'
down_revision = 'lfp_002_shape'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns
    op.add_column('fingerprint_finding', sa.Column('investigation_name', sa.Text(), nullable=True))
    op.add_column('fingerprint_finding', sa.Column('receipts', JSONB, nullable=True))
    op.add_column('fingerprint_finding', sa.Column('confidence', sa.Text(), nullable=True))
    op.add_column('fingerprint_finding', sa.Column('first_detected_at', sa.DateTime(timezone=True),
                                                    server_default=sa.func.now()))
    op.add_column('fingerprint_finding', sa.Column('last_confirmed_at', sa.DateTime(timezone=True),
                                                    server_default=sa.func.now()))
    op.add_column('fingerprint_finding', sa.Column('superseded_at', sa.DateTime(timezone=True),
                                                    nullable=True))
    op.add_column('fingerprint_finding', sa.Column('is_active', sa.Boolean(),
                                                    nullable=True, server_default='true'))

    # Backfill existing rows
    op.execute("""
        UPDATE fingerprint_finding
        SET investigation_name = 'legacy_layer' || layer::text,
            receipts = evidence,
            confidence = confidence_tier,
            is_active = true
        WHERE investigation_name IS NULL
    """)

    # Make new columns NOT NULL after backfill
    op.alter_column('fingerprint_finding', 'investigation_name', nullable=False)
    op.alter_column('fingerprint_finding', 'receipts', nullable=False)
    op.alter_column('fingerprint_finding', 'confidence', nullable=False)
    op.alter_column('fingerprint_finding', 'is_active', nullable=False)

    # Drop old columns
    op.drop_column('fingerprint_finding', 'layer')
    op.drop_column('fingerprint_finding', 'evidence')
    op.drop_column('fingerprint_finding', 'statistical_confidence')
    op.drop_column('fingerprint_finding', 'effect_size')
    op.drop_column('fingerprint_finding', 'sample_size')
    op.drop_column('fingerprint_finding', 'confidence_tier')


def downgrade() -> None:
    # Restore old columns
    op.add_column('fingerprint_finding', sa.Column('layer', sa.Integer(), nullable=True))
    op.add_column('fingerprint_finding', sa.Column('evidence', JSONB, nullable=True))
    op.add_column('fingerprint_finding', sa.Column('statistical_confidence', sa.Float(), nullable=True))
    op.add_column('fingerprint_finding', sa.Column('effect_size', sa.Float(), nullable=True))
    op.add_column('fingerprint_finding', sa.Column('sample_size', sa.Integer(), nullable=True))
    op.add_column('fingerprint_finding', sa.Column('confidence_tier', sa.Text(), nullable=True))

    # Restore data
    op.execute("""
        UPDATE fingerprint_finding
        SET layer = 0,
            evidence = receipts,
            statistical_confidence = 0,
            effect_size = 0,
            sample_size = 0,
            confidence_tier = confidence
    """)

    # Drop new columns
    op.drop_column('fingerprint_finding', 'investigation_name')
    op.drop_column('fingerprint_finding', 'receipts')
    op.drop_column('fingerprint_finding', 'confidence')
    op.drop_column('fingerprint_finding', 'first_detected_at')
    op.drop_column('fingerprint_finding', 'last_confirmed_at')
    op.drop_column('fingerprint_finding', 'superseded_at')
    op.drop_column('fingerprint_finding', 'is_active')
