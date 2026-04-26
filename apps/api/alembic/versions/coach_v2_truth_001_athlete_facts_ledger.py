"""Add Coach V2 athlete facts ledger tables.

Revision ID: coach_v2_truth_001
Revises: coach_runtime_v2_001
Create Date: 2026-04-26
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "coach_v2_truth_001"
down_revision = "coach_runtime_v2_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "athlete_facts",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "athlete_id",
            UUID(as_uuid=True),
            sa.ForeignKey("athlete.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "payload",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("athlete_id", name="uq_athlete_facts_athlete_id"),
    )
    op.create_index(
        "ix_athlete_facts_athlete_id",
        "athlete_facts",
        ["athlete_id"],
        unique=False,
    )

    op.create_table(
        "athlete_facts_audit",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "athlete_id",
            UUID(as_uuid=True),
            sa.ForeignKey("athlete.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("field", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("previous_value", JSONB(), nullable=True),
        sa.Column("new_value", JSONB(), nullable=True),
        sa.Column("confidence", sa.Text(), nullable=True),
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("asserted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_athlete_facts_audit_athlete_id",
        "athlete_facts_audit",
        ["athlete_id"],
        unique=False,
    )
    op.create_index(
        "ix_athlete_facts_audit_athlete_field",
        "athlete_facts_audit",
        ["athlete_id", "field"],
        unique=False,
    )
    op.create_index(
        "ix_athlete_facts_audit_created_at",
        "athlete_facts_audit",
        ["created_at"],
        unique=False,
    )
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_athlete_facts_audit_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'athlete_facts_audit is append-only';
        END;
        $$ LANGUAGE plpgsql;
        """)
    op.execute("""
        CREATE TRIGGER athlete_facts_audit_append_only
        BEFORE UPDATE OR DELETE ON athlete_facts_audit
        FOR EACH ROW EXECUTE FUNCTION prevent_athlete_facts_audit_mutation();
        """)


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS athlete_facts_audit_append_only ON athlete_facts_audit;"
    )
    op.execute("DROP FUNCTION IF EXISTS prevent_athlete_facts_audit_mutation();")
    op.drop_index("ix_athlete_facts_audit_created_at", table_name="athlete_facts_audit")
    op.drop_index(
        "ix_athlete_facts_audit_athlete_field",
        table_name="athlete_facts_audit",
    )
    op.drop_index("ix_athlete_facts_audit_athlete_id", table_name="athlete_facts_audit")
    op.drop_table("athlete_facts_audit")
    op.drop_index("ix_athlete_facts_athlete_id", table_name="athlete_facts")
    op.drop_table("athlete_facts")
