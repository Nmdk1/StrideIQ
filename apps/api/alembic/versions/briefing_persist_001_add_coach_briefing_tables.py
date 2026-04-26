"""Persist generated home briefings and the inputs that produced them.

Adds two linked tables:

  coach_briefing        — one row per materially distinct briefing the coach
                          produced for an athlete. Captures the seven output
                          text fields, the model/source metadata, and which
                          output validators fired during generation.

  coach_briefing_input  — one row per briefing (1:1, FK cascade) holding the
                          full prompt text sent to the LLM plus structured
                          JSONB snapshots of every input the coach saw when
                          writing the brief (today's run, planned workout,
                          check-in, race data, upcoming plan, injected
                          correlation findings).

Retention: indefinite. No reader in this revision — the tables exist as a
corpus the founder can query directly and as the substrate future admin/
marketing read paths will build on.

Athlete-local date is captured explicitly so "show me today's brief for
athlete X" lines up with the date the athlete was on when the brief was
served, not UTC.

Revision ID: briefing_persist_001
Revises: tool_telemetry_001
Create Date: 2026-04-16
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


revision = "briefing_persist_001"
down_revision = "tool_telemetry_001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "coach_briefing",
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
            "generated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        # generated_at truncated to the minute, in UTC, stored explicitly so
        # a unique index can dedupe same-minute retries. We cannot use
        # date_trunc() inside a Postgres index because it is not IMMUTABLE.
        sa.Column(
            "generated_at_minute",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.text("date_trunc('minute', (now() AT TIME ZONE 'UTC'))"),
        ),
        sa.Column("athlete_local_date", sa.Date(), nullable=False),
        sa.Column("data_fingerprint", sa.String(length=32), nullable=False),
        sa.Column("source_model", sa.Text(), nullable=False),
        sa.Column("briefing_source", sa.Text(), nullable=False),
        sa.Column("briefing_is_interim", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default=sa.text("2")),
        sa.Column("coach_noticed", sa.Text(), nullable=True),
        sa.Column("today_context", sa.Text(), nullable=True),
        sa.Column("week_assessment", sa.Text(), nullable=True),
        sa.Column("checkin_reaction", sa.Text(), nullable=True),
        sa.Column("race_assessment", sa.Text(), nullable=True),
        sa.Column("morning_voice", sa.Text(), nullable=True),
        sa.Column("workout_why", sa.Text(), nullable=True),
        sa.Column("payload_json", JSONB(), nullable=False),
        sa.Column("validation_flags", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.create_index(
        "ix_coach_briefing_athlete_id",
        "coach_briefing",
        ["athlete_id"],
    )
    op.create_index(
        "ix_coach_briefing_athlete_local_date",
        "coach_briefing",
        ["athlete_id", "athlete_local_date"],
    )
    op.create_index(
        "ix_coach_briefing_generated_at",
        "coach_briefing",
        ["generated_at"],
    )
    # Collapse same-minute duplicate inserts for the same (athlete, fingerprint).
    # generated_at keeps sub-second precision; generated_at_minute is a
    # pre-computed, IMMUTABLE-safe column the unique index can use directly.
    op.create_index(
        "ux_coach_briefing_athlete_fp_minute",
        "coach_briefing",
        ["athlete_id", "data_fingerprint", "generated_at_minute"],
        unique=True,
    )

    op.create_table(
        "coach_briefing_input",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "briefing_id",
            UUID(as_uuid=True),
            sa.ForeignKey("coach_briefing.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "athlete_id",
            UUID(as_uuid=True),
            sa.ForeignKey("athlete.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("today_completed", JSONB(), nullable=True),
        sa.Column("planned_workout", JSONB(), nullable=True),
        sa.Column("checkin_data", JSONB(), nullable=True),
        sa.Column("race_data", JSONB(), nullable=True),
        sa.Column("upcoming_plan", JSONB(), nullable=True),
        sa.Column("findings_injected", JSONB(), nullable=True),
        sa.Column("prompt_text", sa.Text(), nullable=False),
        sa.Column("garmin_sleep_h", sa.Numeric(4, 2), nullable=True),
    )
    op.create_index(
        "ix_coach_briefing_input_athlete_id",
        "coach_briefing_input",
        ["athlete_id"],
    )


def downgrade():
    op.drop_index("ix_coach_briefing_input_athlete_id", table_name="coach_briefing_input")
    op.drop_table("coach_briefing_input")
    op.drop_index("ux_coach_briefing_athlete_fp_minute", table_name="coach_briefing")
    op.drop_index("ix_coach_briefing_generated_at", table_name="coach_briefing")
    op.drop_index("ix_coach_briefing_athlete_local_date", table_name="coach_briefing")
    op.drop_index("ix_coach_briefing_athlete_id", table_name="coach_briefing")
    op.drop_table("coach_briefing")
