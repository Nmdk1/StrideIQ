"""add_workout_template_registry_and_audit

Revision ID: e8f9a0b1c2d3
Revises: d3e4f5a6b7c8
Create Date: 2026-01-24

Adds:
- workout_template (DB-backed authoritative registry)
- workout_selection_audit_event (append-only audit log)

Seeds a minimal template set (Phase 1 scope):
- 2 base templates
- 2 build templates
- 1 taper template
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "e8f9a0b1c2d3"
down_revision: Union[str, None] = "d3e4f5a6b7c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workout_template",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("intensity_tier", sa.Text(), nullable=False),
        sa.Column("phase_compatibility", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("progression_logic", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("variance_tags", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("constraints", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("dont_follow", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_workout_template_intensity_tier", "workout_template", ["intensity_tier"], unique=False)

    op.create_table(
        "workout_selection_audit_event",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("athlete_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("athlete.id"), nullable=False),
        sa.Column("trigger", sa.Text(), nullable=False),
        sa.Column("plan_generation_id", sa.Text(), nullable=True),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("training_plan.id"), nullable=True),
        sa.Column("target_date", sa.Date(), nullable=True),
        sa.Column("phase", sa.Text(), nullable=True),
        sa.Column("phase_week", sa.Integer(), nullable=True),
        sa.Column("selected_template_id", sa.Text(), sa.ForeignKey("workout_template.id"), nullable=True),
        sa.Column("selection_mode", sa.Text(), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.create_index("ix_workout_selection_audit_event_created_at", "workout_selection_audit_event", ["created_at"], unique=False)
    op.create_index("ix_workout_selection_audit_event_athlete_id", "workout_selection_audit_event", ["athlete_id"], unique=False)
    op.create_index("ix_workout_selection_audit_event_plan_generation_id", "workout_selection_audit_event", ["plan_generation_id"], unique=False)
    op.create_index("ix_workout_selection_audit_event_plan_id", "workout_selection_audit_event", ["plan_id"], unique=False)
    op.create_index("ix_workout_selection_audit_event_target_date", "workout_selection_audit_event", ["target_date"], unique=False)
    op.create_index("ix_workout_selection_audit_event_phase", "workout_selection_audit_event", ["phase"], unique=False)
    op.create_index("ix_workout_selection_audit_event_selected_template_id", "workout_selection_audit_event", ["selected_template_id"], unique=False)

    # Seed minimal templates (representative only; not a full library).
    # Progression logic uses "steps" that the selector maps to week_in_phase.
    op.execute(
        """
        INSERT INTO workout_template (id, name, intensity_tier, phase_compatibility, progression_logic, variance_tags, constraints, dont_follow)
        VALUES
          (
            'base_strides_6x20',
            'Strides 6×20s',
            'AEROBIC',
            '["base"]'::jsonb,
            '{
              "type": "steps",
              "steps": [
                {"key": "s1", "structure": "6x20s strides", "description_template": "Easy run, then 6×20s strides. Full recovery. Stay relaxed."}
              ]
            }'::jsonb,
            '["LOW_IMPACT","TIME_CRUNCHED"]'::jsonb,
            '{"min_time_min": 20}'::jsonb,
            '[]'::jsonb
          ),
          (
            'base_hill_sprints_8x10',
            'Hill Sprints 8×10s',
            'ANAEROBIC',
            '["base"]'::jsonb,
            '{
              "type": "steps",
              "steps": [
                {"key": "s1", "structure": "6x10s hill sprints", "description_template": "Warm up easy. 6×10s hill sprints. Walk back recovery. Cool down."},
                {"key": "s2", "structure": "8x10s hill sprints", "description_template": "Warm up easy. 8×10s hill sprints. Walk back recovery. Cool down."}
              ]
            }'::jsonb,
            '["LOW_IMPACT"]'::jsonb,
            '{"min_time_min": 30, "requires": ["hill_access"]}'::jsonb,
            '["base_strides_6x20"]'::jsonb
          ),
          (
            'build_threshold_2x10',
            'Threshold 2×10min',
            'THRESHOLD',
            '["build"]'::jsonb,
            '{
              "type": "steps",
              "steps": [
                {"key": "s1", "structure": "2x10min @ T", "description_template": "Warm up. 2×10min @ {t_pace} with 2min jog. Cool down."},
                {"key": "s2", "structure": "3x10min @ T", "description_template": "Warm up. 3×10min @ {t_pace} with 2min jog. Cool down."}
              ]
            }'::jsonb,
            '["TREADMILL_FRIENDLY"]'::jsonb,
            '{"min_time_min": 45}'::jsonb,
            '[]'::jsonb
          ),
          (
            'build_vo2_6x400',
            'VO2 6×400',
            'VO2MAX',
            '["build"]'::jsonb,
            '{
              "type": "steps",
              "steps": [
                {"key": "s1", "structure": "5x400 @ I", "description_template": "Warm up. 5×400 @ {i_pace} with 200 jog. Cool down."},
                {"key": "s2", "structure": "6x400 @ I", "description_template": "Warm up. 6×400 @ {i_pace} with 200 jog. Cool down."}
              ]
            }'::jsonb,
            '["TIME_CRUNCHED","TRACK_FRIENDLY"]'::jsonb,
            '{"min_time_min": 40, "requires": ["track_access"]}'::jsonb,
            '["build_threshold_2x10"]'::jsonb
          ),
          (
            'taper_sharpen_6x200',
            'Sharpening 6×200',
            'ANAEROBIC',
            '["taper"]'::jsonb,
            '{
              "type": "steps",
              "steps": [
                {"key": "s1", "structure": "6x200 fast", "description_template": "Warm up. 6×200 fast-but-relaxed. Full recovery. Stop if you strain."}
              ]
            }'::jsonb,
            '["LOW_IMPACT","TIME_CRUNCHED"]'::jsonb,
            '{"min_time_min": 30}'::jsonb,
            '[]'::jsonb
          )
        ON CONFLICT (id) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.drop_index("ix_workout_selection_audit_event_selected_template_id", table_name="workout_selection_audit_event")
    op.drop_index("ix_workout_selection_audit_event_phase", table_name="workout_selection_audit_event")
    op.drop_index("ix_workout_selection_audit_event_target_date", table_name="workout_selection_audit_event")
    op.drop_index("ix_workout_selection_audit_event_plan_id", table_name="workout_selection_audit_event")
    op.drop_index("ix_workout_selection_audit_event_plan_generation_id", table_name="workout_selection_audit_event")
    op.drop_index("ix_workout_selection_audit_event_athlete_id", table_name="workout_selection_audit_event")
    op.drop_index("ix_workout_selection_audit_event_created_at", table_name="workout_selection_audit_event")
    op.drop_table("workout_selection_audit_event")

    op.drop_index("ix_workout_template_intensity_tier", table_name="workout_template")
    op.drop_table("workout_template")

