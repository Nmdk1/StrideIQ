from routers.home import _valid_home_briefing_contract
from routers.progress import ProgressCoachCard, _valid_progress_card_contract


def test_home_briefing_contract_requires_interpretive_assessment_and_action():
    payload = {
        "coach_noticed": "Strong aerobic control across recent long efforts.",
        "today_context": "Keep tomorrow easy to absorb this load and protect Thursday quality.",
        "week_assessment": "This sets up a productive week if recovery stays disciplined.",
        "checkin_reaction": "Glad you feel good; keep sleep and fueling tight tonight.",
    }
    assert _valid_home_briefing_contract(payload, checkin_data={"status": "ok"}, race_data=None) is True


def test_home_briefing_contract_rejects_numeric_only_assessment():
    payload = {
        "coach_noticed": "You ran 8:46/mi at 122 bpm over 20 miles.",
        "today_context": "Keep tomorrow easy and recover.",
        "week_assessment": "Week trend is steady.",
    }
    assert _valid_home_briefing_contract(payload, checkin_data=None, race_data=None) is False


def test_progress_card_contract_accepts_aia_shape():
    card = ProgressCoachCard(
        id="fitness_momentum",
        title="Fitness Momentum",
        summary="Strong consistency is carrying your fitness forward.",
        trend_context="That keeps your current block stable heading into quality sessions.",
        drivers="Recent volume stayed consistent without major execution volatility.",
        next_step="Keep tomorrow easy and hold quality work for your next key session.",
        ask_coach_query="How should I sequence my next quality days?",
    )
    assert _valid_progress_card_contract(card) is True


def test_progress_card_contract_rejects_internal_label_leakage():
    card = ProgressCoachCard(
        id="fitness_momentum",
        title="Fitness Momentum",
        summary="Strong trend.",
        trend_context="AUTHORITATIVE FACT CAPSULE indicates momentum.",
        drivers="Recorded pace vs marathon pace: slower by 0:09/mi",
        next_step="Keep tomorrow easy.",
        ask_coach_query="What should I do next?",
    )
    assert _valid_progress_card_contract(card) is False
