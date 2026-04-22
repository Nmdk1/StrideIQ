"""country-aware preferred_units default + explicit-set flag

Adds `athlete.preferred_units_set_explicitly` (default false) so we can
distinguish a deliberate Settings choice from an inherited default. Then:

  1. Marks every athlete whose CURRENT `preferred_units` value diverges from
     the timezone-derived default as explicit (their stored value was either
     a deliberate Settings toggle or a side-effect of an older mass-flip;
     either way, we honor it going forward and stop second-guessing).

  2. For athletes whose stored value matches the timezone-derived default,
     leaves explicit=false so the Strava-OAuth derivation path can keep them
     in sync if their timezone is ever updated.

  3. One-shot data fix: any athlete in a US timezone whose stored
     `preferred_units = 'metric'` is flipped to `'imperial'` and treated as
     explicit=false. This corrects the small population (notably one US
     beta tester whose row was set to metric prior to the explicit-flag
     mechanism existing) without disturbing the explicitly-metric Europeans
     or the explicitly-metric Canadians.

Revision ID: country_aware_units_001
Revises: strength_v1_002
Create Date: 2026-04-22
"""
from alembic import op
import sqlalchemy as sa


revision = "country_aware_units_001"
down_revision = "strength_v1_002"
branch_labels = None
depends_on = None


# Keep this list in sync with services/units_default.py::US_TIMEZONES.
# The migration must NOT import application code (alembic loads in a
# minimal environment), so the list is duplicated here on purpose.
US_TIMEZONES_SQL = """(
    'America/New_York', 'America/Detroit',
    'America/Kentucky/Louisville', 'America/Kentucky/Monticello',
    'America/Indiana/Indianapolis', 'America/Indiana/Vincennes',
    'America/Indiana/Winamac', 'America/Indiana/Marengo',
    'America/Indiana/Petersburg', 'America/Indiana/Vevay',
    'America/Indiana/Tell_City', 'America/Indiana/Knox',
    'America/Chicago', 'America/Menominee',
    'America/North_Dakota/Center', 'America/North_Dakota/New_Salem',
    'America/North_Dakota/Beulah',
    'America/Denver', 'America/Boise', 'America/Phoenix',
    'America/Los_Angeles',
    'America/Anchorage', 'America/Juneau', 'America/Sitka',
    'America/Metlakatla', 'America/Yakutat', 'America/Nome', 'America/Adak',
    'Pacific/Honolulu',
    'America/Puerto_Rico', 'Pacific/Guam', 'Pacific/Saipan',
    'Pacific/Pago_Pago', 'America/St_Thomas'
)"""


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_cols = {col["name"] for col in inspector.get_columns("athlete")}

    if "preferred_units_set_explicitly" not in existing_cols:
        op.add_column(
            "athlete",
            sa.Column(
                "preferred_units_set_explicitly",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )

    # Step 1: mark as explicit any athlete whose current preference is
    # provably a deliberate choice — i.e. it does NOT match what the
    # country-aware derivation would have produced.
    #
    # Matrix (country default in parentheses):
    #   US tz + imperial         (imperial) → matches    → explicit=false (no-op)
    #   US tz + metric           (imperial) → BUG, fixed separately in step 2
    #   non-US tz + metric       (metric)   → matches    → explicit=false (no-op)
    #   non-US tz + imperial     (metric)   → DIVERGES   → explicit=true
    #   unknown tz + imperial    (imperial) → matches    → explicit=false (no-op)
    #   unknown tz + metric      (imperial) → DIVERGES   → explicit=true
    op.execute(
        f"""
        UPDATE athlete
           SET preferred_units_set_explicitly = TRUE
         WHERE (timezone IS NOT NULL
                  AND timezone NOT IN {US_TIMEZONES_SQL}
                  AND preferred_units = 'imperial')
            OR (timezone IS NULL AND preferred_units = 'metric');
        """
    )

    # Step 2: one-shot data fix for US athletes incorrectly stuck on metric.
    # Founder-flagged 2026-04-22 (Bobby Watts, America/Chicago, signed up
    # 2026-04-18, somehow wound up on metric despite the imperial default).
    # Flip them and leave explicit=false so future timezone changes can
    # continue to derive correctly.
    op.execute(
        f"""
        UPDATE athlete
           SET preferred_units = 'imperial',
               preferred_units_set_explicitly = FALSE
         WHERE timezone IN {US_TIMEZONES_SQL}
           AND preferred_units = 'metric';
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_cols = {col["name"] for col in inspector.get_columns("athlete")}
    if "preferred_units_set_explicitly" in existing_cols:
        op.drop_column("athlete", "preferred_units_set_explicitly")
