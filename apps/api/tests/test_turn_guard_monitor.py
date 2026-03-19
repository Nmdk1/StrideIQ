from services.turn_guard_monitor import build_rollout_report


def _line(msg: str) -> str:
    return f'{{"message":"{msg}"}}'


def test_excludes_synthetic_from_organic_gate():
    lines = [
        _line(
            "turn_guard_event event=pass_initial turn_id=t1 stage=initial athlete_id=a "
            "user_band=profile assistant_band=profile is_synthetic_probe=True is_organic=False"
        ),
        _line(
            "turn_guard_event event=mismatch_detected turn_id=t2 stage=initial athlete_id=a "
            "user_band=logistics assistant_band=analysis is_synthetic_probe=False is_organic=True"
        ),
        _line(
            "turn_guard_event event=fallback_used turn_id=t2 stage=fallback athlete_id=a "
            "user_band=logistics assistant_band=apology is_synthetic_probe=False is_organic=True"
        ),
    ]
    report = build_rollout_report(lines, min_organic_sample=1)
    assert report["counts"]["total_turns"] == 2
    assert report["counts"]["organic_turns"] == 1
    assert report["counts"]["synthetic_turns"] == 1
    assert report["overall"]["total_turns"] == 1


def test_turn_level_grouping_avoids_stage_double_count():
    lines = [
        _line(
            "turn_guard_event event=mismatch_detected turn_id=t9 stage=initial athlete_id=a "
            "user_band=planning assistant_band=analysis is_synthetic_probe=False is_organic=True"
        ),
        _line(
            "turn_guard_event event=retry_still_mismatch turn_id=t9 stage=retry athlete_id=a "
            "user_band=planning assistant_band=analysis is_synthetic_probe=False is_organic=True"
        ),
        _line(
            "turn_guard_event event=fallback_used turn_id=t9 stage=fallback athlete_id=a "
            "user_band=planning assistant_band=apology is_synthetic_probe=False is_organic=True"
        ),
    ]
    report = build_rollout_report(lines, min_organic_sample=1)
    assert report["counts"]["organic_turns"] == 1
    assert report["overall"]["mismatch_turns"] == 1
    assert report["overall"]["fallback_turns"] == 1


def test_recommended_actions_present_for_no_go():
    lines = [
        _line(
            "turn_guard_event event=mismatch_detected turn_id=t1 stage=initial athlete_id=a "
            "user_band=logistics assistant_band=analysis is_synthetic_probe=False is_organic=True"
        ),
        _line(
            "turn_guard_event event=fallback_used turn_id=t1 stage=fallback athlete_id=a "
            "user_band=logistics assistant_band=apology is_synthetic_probe=False is_organic=True"
        ),
    ]
    report = build_rollout_report(lines, min_organic_sample=1, min_band_sample=1)
    assert report["status"] == "NO_GO"
    assert any("Freeze broad rollout" in action for action in report["recommended_actions"])
