from sqlalchemy import Column, Integer, BigInteger, Boolean, CheckConstraint, Float, Date, DateTime, ForeignKey, Numeric, Text, String, Index, UniqueConstraint, text
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from core.database import Base
import uuid
from typing import Optional
from datetime import datetime, timezone

class AthleteFinding(Base):
    """Persistent store for investigation findings (Living Fingerprint).

    Keeps tablename 'fingerprint_finding' for migration continuity.
    Supersession logic: one active finding per (investigation_name, finding_type).
    """
    __tablename__ = "fingerprint_finding"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"),
                        nullable=False, index=True)
    investigation_name = Column(Text, nullable=False)
    finding_type = Column(Text, nullable=False)
    layer = Column(Text, nullable=False, server_default='B')
    sentence = Column(Text, nullable=False)
    receipts = Column(JSONB, nullable=False)
    confidence = Column(Text, nullable=False)  # 'table_stakes', 'genuine', 'suggestive'
    computation_version = Column(Integer, nullable=False, default=2)
    first_detected_at = Column(DateTime(timezone=True), server_default=func.now())
    last_confirmed_at = Column(DateTime(timezone=True), server_default=func.now())
    superseded_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)

class InsightFeedback(Base):
    """
    User feedback on insights to refine correlation engine thresholds.
    
    Tracks which insights users find helpful vs not helpful.
    Used to improve insight quality and correlation thresholds.
    """
    __tablename__ = "insight_feedback"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False)  # Index in __table_args__
    insight_type = Column(Text, nullable=False)  # 'correlation', 'activity_insight', 'efficiency_trend', etc.
    insight_id = Column(Text, nullable=True)  # ID of the insight (correlation ID, activity ID, etc.)
    insight_text = Column(Text, nullable=False)  # The actual insight text shown to user
    helpful = Column(Boolean, nullable=False)  # True = helpful, False = not helpful
    feedback_text = Column(Text, nullable=True)  # Optional user comment
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    __table_args__ = (
        Index("ix_insight_feedback_athlete_id", "athlete_id"),
        Index("ix_insight_feedback_insight_type", "insight_type"),
        Index("ix_insight_feedback_created_at", "created_at"),
    )

class ThresholdCalibrationLog(Base):
    """
    Logs every readiness-at-decision + outcome pair.

    This is the data that feeds the per-athlete threshold calibration process.
    Pattern: every workout → log readiness + scheduled type + outcome.
    When N >= 30: estimate per-athlete thresholds from outcome data.
    """
    __tablename__ = "threshold_calibration_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False, index=True)
    workout_id = Column(UUID(as_uuid=True), ForeignKey("planned_workout.id"), nullable=True)

    # State at decision point
    readiness_score = Column(Float, nullable=False)
    workout_type_scheduled = Column(Text, nullable=True)

    # Outcome
    outcome = Column(Text, nullable=True)                  # "completed", "skipped", "modified"
    efficiency_delta = Column(Float, nullable=True)        # Next-day efficiency change
    subjective_feel = Column(Integer, nullable=True)       # From check-in if available (1-5)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_threshold_cal_log_athlete_date", "athlete_id", "created_at"),
    )


# =========================================================================
# Phase 2B: Self-Regulation + Intelligence Logging
# =========================================================================

class SelfRegulationLog(Base):
    """
    Records every planned ≠ actual delta as first-class data.

    When an athlete deviates from the plan — running quality instead of easy,
    cutting a long run short, adding an unplanned session — the delta is
    logged here with the outcome tracked over the following days.

    This data feeds:
    - Self-regulation pattern recognition ("you override easy → quality well")
    - Threshold calibration (readiness at decision → outcome)
    - Intelligence engine SUGGEST mode (personal patterns from outcome data)
    """
    __tablename__ = "self_regulation_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False, index=True)
    workout_id = Column(UUID(as_uuid=True), ForeignKey("planned_workout.id"), nullable=True)
    activity_id = Column(UUID(as_uuid=True), ForeignKey("activity.id"), nullable=True)

    # What was planned
    planned_type = Column(Text, nullable=True)                  # e.g., "easy"
    planned_distance_km = Column(Float, nullable=True)
    planned_intensity = Column(Text, nullable=True)             # e.g., "easy_pace"

    # What actually happened
    actual_type = Column(Text, nullable=True)                   # e.g., "tempo_run"
    actual_distance_km = Column(Float, nullable=True)
    actual_intensity = Column(Text, nullable=True)              # e.g., "threshold_pace"

    # Delta classification
    delta_type = Column(Text, nullable=False)                   # "type_change", "distance_change", "intensity_change", "unplanned", "skipped"
    delta_direction = Column(Text, nullable=True)               # "upgraded" (easy→quality), "downgraded" (quality→easy), "shortened", "extended"

    # Context at time of decision
    readiness_at_decision = Column(Float, nullable=True)        # Readiness score
    trigger_date = Column(Date, nullable=False)

    # Outcome tracking (populated asynchronously, next day or later)
    outcome_efficiency_delta = Column(Float, nullable=True)     # Next-day efficiency change
    outcome_subjective = Column(Integer, nullable=True)         # From check-in if available (1-5)
    outcome_classification = Column(Text, nullable=True)        # "positive", "neutral", "negative" (set by outcome analysis)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_self_reg_log_athlete_date", "athlete_id", "trigger_date"),
    )

class InsightLog(Base):
    """
    Records every intelligence insight produced by the daily engine.

    Every INFORM, SUGGEST, FLAG, ASK, and LOG insight is persisted here.
    This provides:
    - Audit trail of what the system told the athlete
    - Data for measuring insight accuracy over time
    - Input for the narration trust scoring system (Phase 3)
    """
    __tablename__ = "insight_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False, index=True)

    # Insight identity
    rule_id = Column(Text, nullable=False)                      # e.g., "LOAD_SPIKE", "SELF_REG_DELTA"
    mode = Column(Text, nullable=False)                         # "inform", "suggest", "flag", "ask", "log"
    message = Column(Text, nullable=True)                       # Human-readable insight text
    data_cited = Column(JSONB, nullable=True)                   # Evidence backing the insight

    # Context
    trigger_date = Column(Date, nullable=False)
    readiness_score = Column(Float, nullable=True)              # Readiness at time of insight
    confidence = Column(Float, nullable=True)                   # 0-1 confidence in the insight

    # Athlete response tracking
    athlete_seen = Column(Boolean, default=False, nullable=False)
    athlete_response = Column(Text, nullable=True)              # "acknowledged", "dismissed", "acted_on"
    athlete_response_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Phase 3A: Coach narration attached to this insight
    narrative = Column(Text, nullable=True)                      # AI-generated explanation of this insight
    narrative_score = Column(Float, nullable=True)               # 0-1 score from narration scorer
    narrative_contradicts = Column(Boolean, nullable=True)       # True if narration contradicted engine

    __table_args__ = (
        Index("ix_insight_log_athlete_date", "athlete_id", "trigger_date"),
        Index("ix_insight_log_rule_id", "rule_id"),
    )

class NarrationLog(Base):
    """
    Records every narration scoring evaluation.

    Each time the coach generates a narration for an intelligence insight,
    the narration is scored against the engine's ground truth on 3 binary
    criteria. Results stored here feed the Phase 3B gate (90% for 4 weeks).

    This is the AUDIT TRAIL for coach narration quality.
    """
    __tablename__ = "narration_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False, index=True)
    insight_log_id = Column(UUID(as_uuid=True), ForeignKey("insight_log.id"), nullable=True)

    # The narration
    trigger_date = Column(Date, nullable=False)
    rule_id = Column(Text, nullable=False)                       # Which rule was narrated
    narration_text = Column(Text, nullable=True)                 # The generated narration
    prompt_used = Column(Text, nullable=True)                    # The prompt sent to the LLM (for debugging)

    # Ground truth
    ground_truth = Column(JSONB, nullable=True)                  # Engine data at narration time

    # 3 binary scoring criteria
    factually_correct = Column(Boolean, nullable=True)
    no_raw_metrics = Column(Boolean, nullable=True)
    actionable_language = Column(Boolean, nullable=True)
    criteria_passed = Column(Integer, nullable=True)             # 0-3
    score = Column(Float, nullable=True)                         # 0.0-1.0

    # Contradiction detection
    contradicts_engine = Column(Boolean, default=False, nullable=False)
    contradiction_detail = Column(Text, nullable=True)

    # Quality gate
    suppressed = Column(Boolean, default=False, nullable=False)  # True if narration quality too low → hidden
    suppression_reason = Column(Text, nullable=True)             # Why it was suppressed

    # LLM metadata
    model_used = Column(Text, nullable=True)                     # e.g., "gemini-2.5-flash"
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    latency_ms = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_narration_log_athlete_date", "athlete_id", "trigger_date"),
        Index("ix_narration_log_score", "score"),
    )

class CorrelationFinding(Base):
    """
    Persists significant correlation discoveries for each athlete.

    When the correlation engine finds a significant relationship (e.g.,
    "sleep > 7h → efficiency +8% two days later"), it is recorded here.
    Each subsequent confirmation of the same pattern increments
    times_confirmed, building reproducibility weight.

    Only reproducible findings (times_confirmed >= SURFACING_THRESHOLD)
    are eligible to be narrated to the athlete.  The coach speaks only
    when the pattern is real — not after a single lucky coincidence.

    Lifecycle:
        1. Correlation engine discovers a significant (p < 0.05, |r| >= 0.3)
           relationship between an input (e.g. sleep_hours) and an output
           metric (e.g. efficiency).
        2. persist_correlation_findings() upserts the row:
           - New finding → times_confirmed = 1.
           - Existing finding → times_confirmed += 1, stats updated.
        3. If a previously-significant finding drops below threshold in a
           later run, is_active is set to False (patterns can fade).
        4. Daily intelligence checks for reproducible findings
           (times_confirmed >= 3, is_active) and emits InsightLog entries
           with rule_id = "CORRELATION_CONFIRMED".
    """
    __tablename__ = "correlation_finding"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False, index=True)

    # --- What was correlated ---
    input_name = Column(Text, nullable=False)          # e.g. "sleep_hours", "soreness_1_5"
    output_metric = Column(Text, nullable=False)       # e.g. "efficiency", "pace_easy"
    direction = Column(Text, nullable=False)           # "positive" or "negative"
    time_lag_days = Column(Integer, default=0, nullable=False)

    # --- Statistical strength (most recent computation) ---
    correlation_coefficient = Column(Float, nullable=False)
    p_value = Column(Float, nullable=False)
    sample_size = Column(Integer, nullable=False)
    strength = Column(Text, nullable=False)            # "weak", "moderate", "strong"

    # --- Reproducibility tracking ---
    times_confirmed = Column(Integer, default=1, nullable=False)
    first_detected_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_confirmed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_surfaced_at = Column(DateTime(timezone=True), nullable=True)

    # --- Human-readable insight text ---
    insight_text = Column(Text, nullable=True)

    # --- Categorization ---
    category = Column(Text, nullable=False)            # "what_works", "what_doesnt", "pattern"
    confidence = Column(Float, nullable=False)         # 0.0-1.0

    # --- Lifecycle ---
    is_active = Column(Boolean, default=True, nullable=False)

    # --- Confounder control (Phase 1) ---
    partial_correlation_coefficient = Column(Float, nullable=True)
    confounder_variable = Column(Text, nullable=True)
    is_confounded = Column(Boolean, default=False, nullable=False)
    direction_expected = Column(Text, nullable=True)
    direction_counterintuitive = Column(Boolean, default=False, nullable=False)

    # --- Layer 1: Threshold Detection ---
    threshold_value = Column(Float, nullable=True)
    threshold_direction = Column(Text, nullable=True)
    r_below_threshold = Column(Float, nullable=True)
    r_above_threshold = Column(Float, nullable=True)
    n_below_threshold = Column(Integer, nullable=True)
    n_above_threshold = Column(Integer, nullable=True)

    # --- Layer 2: Asymmetric Response ---
    asymmetry_ratio = Column(Float, nullable=True)
    asymmetry_direction = Column(Text, nullable=True)
    effect_below_baseline = Column(Float, nullable=True)
    effect_above_baseline = Column(Float, nullable=True)
    baseline_value = Column(Float, nullable=True)

    # --- Layer 4: Decay Curves ---
    lag_profile = Column(JSONB, nullable=True)
    decay_half_life_days = Column(Float, nullable=True)
    decay_type = Column(Text, nullable=True)

    # --- AutoDiscovery Phase 1: discovery provenance + stability metadata ---
    discovery_source = Column(Text, nullable=True)          # "daily_sweep" | "auto_discovery"
    discovery_window_days = Column(Integer, nullable=True)  # window where first found
    stability_class = Column(Text, nullable=True)           # stable|recent_only|strengthening|unstable|degrading
    windows_confirmed = Column(Integer, nullable=True)      # count of windows passing significance
    stability_checked_at = Column(DateTime(timezone=True), nullable=True)

    # --- Phase 3: Limiter Lifecycle ---
    # See LIMITER_TAXONOMY_ANNOTATED.md for state definitions.
    # Values: emerging, active, active_fixed, resolving, closed, structural
    lifecycle_state = Column(Text, nullable=True)
    lifecycle_state_updated_at = Column(DateTime(timezone=True), nullable=True)

    # --- Phase 4: Coach layer integration ---
    # Brief attribution string captured at active → resolving transition.
    # Coach reads this to explain *what the athlete did* that caused the shift.
    resolving_context = Column(Text, nullable=True)

    __table_args__ = (
        # One row per unique (athlete, input, output, lag) combination.
        Index(
            "uq_corr_finding_natural_key",
            "athlete_id", "input_name", "output_metric", "time_lag_days",
            unique=True,
        ),
        Index("ix_corr_finding_active", "athlete_id", "is_active"),
    )


# ---------------------------------------------------------------------------
# AutoDiscovery Phase 1 — live mutation models
# ---------------------------------------------------------------------------

class CorrelationMediator(Base):
    """
    Mediator variables detected for confirmed correlation findings (Layer 3).

    When A→C is confirmed, mediation analysis tests whether B explains
    the relationship (A→B→C).  Each row represents one mediator for one
    finding.
    """
    __tablename__ = "correlation_mediator"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    finding_id = Column(UUID(as_uuid=True), ForeignKey("correlation_finding.id"), nullable=False, index=True)
    mediator_variable = Column(Text, nullable=False)
    direct_effect = Column(Float, nullable=False)
    indirect_effect = Column(Float, nullable=False)
    mediation_ratio = Column(Float, nullable=False)
    is_full_mediation = Column(Boolean, default=False, nullable=False)
    detected_at = Column(DateTime(timezone=True), server_default=func.now())

class NarrativeFeedback(Base):
    """
    Athlete feedback on the progress narrative page.

    Tracks whether the narrative resonated, felt off, or prompted
    a coach conversation. Used for future narrative quality calibration.
    """
    __tablename__ = "narrative_feedback"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    feedback_type = Column(Text, nullable=False)       # "positive", "negative", "coach"
    feedback_detail = Column(Text, nullable=True)       # Optional detail for "negative" sub-options

    __table_args__ = (
        Index("ix_narrative_feedback_athlete_created", "athlete_id", "created_at"),
    )

class AutoDiscoveryRun(Base):
    """
    One founder-only nightly shadow research session.

    Tracks the overall lifecycle of a single AutoDiscovery pass:
    which loop families ran, how many experiments were conducted,
    and the full structured nightly report (JSONB).

    Phase 0: shadow mode only — no live mutation permitted.
    """
    __tablename__ = "auto_discovery_run"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    finished_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(Text, nullable=False, server_default="running")  # running|completed|failed|partial
    loop_types = Column(JSONB, nullable=False, server_default="[]")
    experiment_count = Column(Integer, nullable=False, server_default="0")
    kept_count = Column(Integer, nullable=False, server_default="0")
    discarded_count = Column(Integer, nullable=False, server_default="0")
    report = Column(JSONB, nullable=True)
    notes = Column(Text, nullable=True)

    __table_args__ = (
        Index("ix_auto_discovery_run_athlete_started", "athlete_id", "started_at"),
        Index("ix_auto_discovery_run_status_started", "status", "started_at"),
    )

class AutoDiscoveryExperiment(Base):
    """
    One experiment within a single AutoDiscoveryRun.

    Records the complete before/after state of one candidate change:
    baseline config, candidate config, FQS scores, keep/discard decision,
    and a result summary.

    Phase 0: every experiment is shadow-only; kept=True means
    'worth reviewing', not 'applied to production'.
    """
    __tablename__ = "auto_discovery_experiment"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(UUID(as_uuid=True), ForeignKey("auto_discovery_run.id"), nullable=False)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False)
    loop_type = Column(Text, nullable=False)  # correlation_rescan|interaction_scan|registry_tuning
    target_name = Column(Text, nullable=False)  # investigation name, input name, or pair id
    baseline_config = Column(JSONB, nullable=False, server_default="{}")
    candidate_config = Column(JSONB, nullable=False, server_default="{}")
    baseline_score = Column(Float, nullable=True)
    candidate_score = Column(Float, nullable=True)
    score_delta = Column(Float, nullable=True)
    kept = Column(Boolean, nullable=False, server_default="false")
    runtime_ms = Column(Integer, nullable=True)
    result_summary = Column(JSONB, nullable=True)
    failure_reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_auto_disc_exp_run_id", "run_id"),
        Index("ix_auto_disc_exp_athlete_loop_created", "athlete_id", "loop_type", "created_at"),
        Index("ix_auto_disc_exp_loop_kept_created", "loop_type", "kept", "created_at"),
    )

class AutoDiscoveryCandidate(Base):
    """
    Durable cross-run candidate memory for AutoDiscovery (Phase 0C).

    Groups recurring shadow candidates across nightly runs by a deterministic
    stable key.  The founder can review and approve/reject/defer candidates;
    approved candidates can be staged for controlled promotion.

    Safety guarantees:
    - Candidate rows never directly mutate athlete-facing surfaces.
    - Staging intent (promotion_target) is a label only — no auto-mutation.
    - current_status transitions are explicit founder actions only.
    """
    __tablename__ = "auto_discovery_candidate"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False)
    # Type of candidate: stable_finding, strengthened_finding, interaction, registry_tuning
    candidate_type = Column(Text, nullable=False)
    # Deterministic stable key — unique per (athlete_id, candidate_type, candidate_key).
    candidate_key = Column(Text, nullable=False)
    first_seen_run_id = Column(UUID(as_uuid=True), ForeignKey("auto_discovery_run.id"), nullable=False)
    last_seen_run_id = Column(UUID(as_uuid=True), ForeignKey("auto_discovery_run.id"), nullable=False)
    times_seen = Column(Integer, nullable=False, server_default="1")
    # Review state: open | approved | rejected | deferred | promoted
    current_status = Column(Text, nullable=False, server_default="open")
    latest_summary = Column(JSONB, nullable=True)  # compact candidate payload
    latest_score = Column(Float, nullable=True)
    latest_score_delta = Column(Float, nullable=True)
    provenance_snapshot = Column(JSONB, nullable=True)  # score_provenance block
    # Promotion staging: null until founder approves and stages.
    # Values: surface_candidate | registry_change_candidate |
    #         investigation_upgrade_candidate | manual_research_candidate
    promotion_target = Column(Text, nullable=True)
    promotion_note = Column(Text, nullable=True)  # optional short founder note
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    reviewed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        # Uniqueness enforced at DB level — same candidate must not have duplicate rows.
        UniqueConstraint("athlete_id", "candidate_type", "candidate_key",
                         name="uq_auto_disc_candidate_athlete_type_key"),
        Index("ix_auto_disc_candidate_athlete_status", "athlete_id", "current_status"),
        Index("ix_auto_disc_candidate_type_status", "candidate_type", "current_status"),
        Index("ix_auto_disc_candidate_times_seen", "athlete_id", "times_seen"),
    )

class AutoDiscoveryReviewLog(Base):
    """
    Audit log for founder review actions on AutoDiscoveryCandidate rows.

    Each row records one explicit founder action (approve/reject/defer/stage).
    Enables full auditability without overwriting the candidate row history.
    """
    __tablename__ = "auto_discovery_review_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id = Column(UUID(as_uuid=True), ForeignKey("auto_discovery_candidate.id"), nullable=False)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False)
    action = Column(Text, nullable=False)  # approve | reject | defer | stage
    previous_status = Column(Text, nullable=True)
    new_status = Column(Text, nullable=False)
    promotion_target = Column(Text, nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_auto_disc_review_log_candidate", "candidate_id"),
        Index("ix_auto_disc_review_log_athlete_created", "athlete_id", "created_at"),
    )

class N1InsightSuppression(Base):
    """Per-insight suppression record for Phase 3C graduation control.

    Allows founders to suppress individual 3C insight patterns without
    disabling all of 3C globally.  Suppression is keyed by (athlete_id,
    insight_fingerprint) where the fingerprint is a stable hash of
    input_name:direction:output_metric — so the same pattern stays
    suppressed even if the generated text changes.

    Lifecycle:
      1. Founder reviews generated 3C outputs via /v1/admin/insights/n1-review.
      2. If an insight is wrong/weak/badly phrased, POST to
         /v1/admin/insights/n1-suppress with athlete_id + fingerprint.
      3. generate_n1_insights() checks suppressions before surfacing.
      4. Only the specific pattern is suppressed; the rest of 3C continues.
    """
    __tablename__ = "n1_insight_suppression"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False)
    insight_fingerprint = Column(Text, nullable=False)  # input_name:direction:output_metric
    suppressed_by = Column(Text, nullable=True)          # "founder" or founder email
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("athlete_id", "insight_fingerprint",
                         name="uq_n1_suppression_athlete_fingerprint"),
        Index("ix_n1_suppression_athlete", "athlete_id"),
    )


# ---------------------------------------------------------------------------
# AutoDiscovery Phase 1 — live mutation models
# ---------------------------------------------------------------------------

class AutoDiscoveryChangeLog(Base):
    """Typed durable change ledger.  Every live mutation from AutoDiscovery
    writes one row here, enabling audit and revert operations.
    """
    __tablename__ = "auto_discovery_change_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("auto_discovery_run.id", ondelete="SET NULL"),
        nullable=True,
    )
    athlete_id = Column(UUID(as_uuid=True), nullable=False)
    change_type = Column(Text, nullable=False)
    change_key = Column(Text, nullable=False)
    before_state = Column(JSONB, nullable=True)
    after_state = Column(JSONB, nullable=True)
    reverted = Column(Boolean, nullable=False, default=False)
    reverted_at = Column(DateTime(timezone=True), nullable=True)
    reverted_by = Column(Text, nullable=True)
    revert_reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "athlete_id", "change_type", "change_key", "run_id",
            name="uq_adcl_athlete_type_key_run",
        ),
        Index("ix_auto_discovery_change_log_athlete_id", "athlete_id"),
        Index("ix_auto_discovery_change_log_run_id", "run_id"),
        Index("ix_auto_discovery_change_log_reverted", "athlete_id", "reverted"),
    )

class AutoDiscoveryScanCoverage(Base):
    """Tracks which (athlete, input, output, window) combinations have been
    tested, preventing redundant work and enabling progress reporting.
    """
    __tablename__ = "auto_discovery_scan_coverage"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), nullable=False)
    loop_type = Column(Text, nullable=False)
    test_key = Column(Text, nullable=False)
    input_a = Column(Text, nullable=False)
    input_b = Column(Text, nullable=True)
    output_metric = Column(Text, nullable=False)
    window_days = Column(Integer, nullable=True)
    last_scanned_at = Column(DateTime(timezone=True), nullable=False)
    result = Column(Text, nullable=False)  # signal / no_signal / error
    scan_count = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "athlete_id", "loop_type", "test_key",
            name="uq_adsc_athlete_loop_test_key",
        ),
        Index("ix_adsc_athlete_loop", "athlete_id", "loop_type"),
        Index("ix_adsc_athlete_last_scanned", "athlete_id", "last_scanned_at"),
    )

