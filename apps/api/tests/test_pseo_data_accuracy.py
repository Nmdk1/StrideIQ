import json
from pathlib import Path

from services.rpi_calculator import calculate_rpi_from_race_time, calculate_training_paces
from services.wma_age_factors import get_wma_age_factor, get_wma_open_standard_seconds


REPO_ROOT = Path(__file__).resolve().parents[3]
AGE_TABLES_PATH = REPO_ROOT / "apps" / "web" / "data" / "age-grading-tables.json"
PACE_TABLES_PATH = REPO_ROOT / "apps" / "web" / "data" / "training-pace-tables.json"
AGE_PAGE_PATH = (
    REPO_ROOT / "apps" / "web" / "app" / "tools" / "age-grading-calculator" / "[distance]" / "page.tsx"
)
PACE_PAGE_PATH = (
    REPO_ROOT / "apps" / "web" / "app" / "tools" / "training-pace-calculator" / "[distance]" / "page.tsx"
)


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _js_round(value: float) -> int:
    # JS Math.round semantics (half up), not Python banker rounding.
    return int(value + 0.5)


def _format_time_js(total_seconds: float) -> str:
    rounded = _js_round(total_seconds)
    hours = rounded // 3600
    minutes = (rounded % 3600) // 60
    seconds = rounded % 60
    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def _format_mi_pace_js(total_seconds: float, distance_meters: float) -> str:
    miles = distance_meters / 1609.34
    sec_per_mile = _js_round(total_seconds / miles)
    minutes = sec_per_mile // 60
    seconds = sec_per_mile % 60
    return f"{minutes}:{seconds:02d}"


def _pace_to_seconds(pace: str) -> int:
    minutes, seconds = pace.split(":")
    return int(minutes) * 60 + int(seconds)


def test_age_grading_tables_match_backend_contract():
    age_tables = _load_json(AGE_TABLES_PATH)
    distance_map = {
        "5k": 5000.0,
        "10k": 10000.0,
        "half": 21097.5,
        "marathon": 42195.0,
    }

    mismatches = []

    for dist_key, dist_section in age_tables.items():
        distance_m = distance_map[dist_key]
        for gender in ("male", "female"):
            sex = "F" if gender == "female" else "M"
            for row in dist_section[gender]:
                age = row["age"]
                factor = get_wma_age_factor(age=age, sex=sex, distance_meters=distance_m)
                open_standard = get_wma_open_standard_seconds(sex=sex, distance_meters=distance_m)
                assert factor is not None
                assert open_standard is not None

                if abs(row["ageFactor"] - factor) > 1e-9:
                    mismatches.append(f"{dist_key}/{gender}/age{age}: ageFactor mismatch")

                expected_age_standard = round(open_standard * factor, 1)
                if abs(row["ageStandardSeconds"] - expected_age_standard) > 1e-9:
                    mismatches.append(f"{dist_key}/{gender}/age{age}: ageStandardSeconds mismatch")

                for pct in (50, 60, 70, 80, 90):
                    level = row["levels"][str(pct)]
                    raw_seconds = (open_standard * factor) / (pct / 100)

                    if level["timeSeconds"] != _js_round(raw_seconds):
                        mismatches.append(f"{dist_key}/{gender}/age{age}/{pct}: timeSeconds mismatch")
                    if level["timeFormatted"] != _format_time_js(raw_seconds):
                        mismatches.append(f"{dist_key}/{gender}/age{age}/{pct}: timeFormatted mismatch")
                    if level["pace"] != _format_mi_pace_js(raw_seconds, distance_m):
                        mismatches.append(f"{dist_key}/{gender}/age{age}/{pct}: pace mismatch")

    assert not mismatches, "Age-grading parity failures:\n" + "\n".join(mismatches[:50])


def test_training_pace_tables_match_rpi_calculator_contract():
    pace_tables = _load_json(PACE_TABLES_PATH)
    mismatches = []

    for dist_key, dist_section in pace_tables.items():
        distance_m = dist_section["distanceMeters"]
        for row in dist_section["rows"]:
            race_seconds = row["raceTimeSeconds"]

            expected_rpi = calculate_rpi_from_race_time(distance_m, race_seconds)
            assert expected_rpi is not None
            if abs(float(row["rpi"]) - float(expected_rpi)) > 0.1:
                mismatches.append(
                    f"{dist_key}/{row['raceTime']}: rpi json={row['rpi']} calc={expected_rpi}"
                )

            expected_paces = calculate_training_paces(float(expected_rpi))
            for zone in ("easy", "marathon", "threshold", "interval", "repetition"):
                json_mi = row["paces"][zone]["mi"]
                json_km = row["paces"][zone]["km"]
                calc_mi = expected_paces[zone]["mi"]
                calc_km = expected_paces[zone]["km"]
                # Generated table values are sourced from the enhanced public endpoint and can be
                # off by 1 second from the pure formula path due to different rounding details.
                if abs(_pace_to_seconds(json_mi) - _pace_to_seconds(calc_mi)) > 1:
                    mismatches.append(
                        f"{dist_key}/{row['raceTime']}/{zone}: mi json={json_mi} calc={calc_mi}"
                    )
                if abs(_pace_to_seconds(json_km) - _pace_to_seconds(calc_km)) > 1:
                    mismatches.append(
                        f"{dist_key}/{row['raceTime']}/{zone}: km json={json_km} calc={calc_km}"
                    )

    assert not mismatches, "Training-pace parity failures:\n" + "\n".join(mismatches[:50])


def _get_age_time(age_tables: dict, dist: str, gender: str, age: int, pct: int) -> str:
    rows = age_tables[dist][gender]
    row = next(r for r in rows if r["age"] == age)
    return row["levels"][str(pct)]["timeFormatted"]


def _get_age_pct_for_time(age_tables: dict, dist: str, gender: str, age: int, time_seconds: int) -> float:
    rows = age_tables[dist][gender]
    row = next(r for r in rows if r["age"] == age)
    return round((row["ageStandardSeconds"] / time_seconds) * 100, 1)


def _get_age_pct_for_time_int(age_tables: dict, dist: str, gender: str, age: int, time_seconds: int) -> int:
    # Page copy uses whole-number percentages with half values rounded down.
    return int(_get_age_pct_for_time(age_tables, dist, gender, age, time_seconds) + 0.499999)


def _get_pace_row(pace_tables: dict, dist: str, race_time: str) -> dict:
    return next(r for r in pace_tables[dist]["rows"] if r["raceTime"] == race_time)


def test_pseo_page_numeric_claims_match_tables():
    age_tables = _load_json(AGE_TABLES_PATH)
    pace_tables = _load_json(PACE_TABLES_PATH)

    age_page_source = AGE_PAGE_PATH.read_text(encoding="utf-8")
    pace_page_source = PACE_PAGE_PATH.read_text(encoding="utf-8")

    expected_age_fragments = [
        f"running {_get_age_time(age_tables, '5k', 'male', 50, 60)} scores 60%",
        f"requires {_get_age_time(age_tables, '5k', 'male', 50, 70)}",
        f"{_get_age_time(age_tables, '5k', 'male', 30, 50)} for a 30-year-old male",
        f"{_get_age_time(age_tables, '5k', 'male', 30, 70)}; a 60-year-old at the same 70% grade runs {_get_age_time(age_tables, '5k', 'male', 60, 70)}",
        f"about {_get_age_pct_for_time_int(age_tables, '5k', 'male', 30, 1200)}% age-graded",
        f"the same 20:00 scores {_get_age_pct_for_time_int(age_tables, '5k', 'male', 55, 1200)}%",
        f"it reaches {_get_age_pct_for_time_int(age_tables, '5k', 'male', 60, 1200)}%",
        f"running {_get_age_time(age_tables, '10k', 'male', 50, 60)} scores 60%",
        f"requires {_get_age_time(age_tables, '10k', 'male', 50, 70)}",
        f"{_get_age_time(age_tables, '10k', 'male', 50, 60)} = Local Class (60%), {_get_age_time(age_tables, '10k', 'male', 50, 70)} = Regional Class (70%), {_get_age_time(age_tables, '10k', 'male', 50, 80)} = National Class (80%)",
        f"the equivalent times are {_get_age_time(age_tables, '10k', 'female', 50, 60)}, {_get_age_time(age_tables, '10k', 'female', 50, 70)}, and {_get_age_time(age_tables, '10k', 'female', 50, 80)}",
        f"a 50:00 10K is about {_get_age_pct_for_time_int(age_tables, '10k', 'male', 30, 3000)}% age-graded",
        f"the same 50:00 is about {_get_age_pct_for_time_int(age_tables, '10k', 'male', 60, 3000)}%",
        f"it is about {_get_age_pct_for_time_int(age_tables, '10k', 'male', 70, 3000)}%",
        f"running {_get_age_time(age_tables, 'half', 'male', 50, 60)} scores 60%",
        f"requires {_get_age_time(age_tables, 'half', 'male', 50, 70)}",
        f"is about {_get_age_time(age_tables, 'half', 'male', 30, 50)}",
        f"{_get_age_time(age_tables, 'half', 'male', 40, 70)}; a 60-year-old at the same grade runs {_get_age_time(age_tables, 'half', 'male', 60, 70)}",
        f"sub-2:00 is about {_get_age_pct_for_time_int(age_tables, 'half', 'male', 30, 7200)}% age-graded",
        f"sub-2:00 scores about {_get_age_pct_for_time_int(age_tables, 'half', 'male', 60, 7200)}%",
        f"sub-2:00 is about {_get_age_pct_for_time_int(age_tables, 'half', 'male', 70, 7200)}%",
        f"running {_get_age_time(age_tables, 'marathon', 'male', 50, 60)} scores 60%",
        f"requires {_get_age_time(age_tables, 'marathon', 'male', 50, 70)}",
        f"{_get_age_time(age_tables, 'marathon', 'male', 40, 60)} = Local Class (60%), {_get_age_time(age_tables, 'marathon', 'male', 40, 70)} = Regional Class (70%), {_get_age_time(age_tables, 'marathon', 'male', 40, 80)} = National Class (80%)",
        f"the equivalent times are {_get_age_time(age_tables, 'marathon', 'female', 40, 60)}, {_get_age_time(age_tables, 'marathon', 'female', 40, 70)}, and {_get_age_time(age_tables, 'marathon', 'female', 40, 80)}",
        f"a 4:00:00 marathon is about {_get_age_pct_for_time_int(age_tables, 'marathon', 'male', 30, 14400)}% age-graded",
        f"the same time scores about {_get_age_pct_for_time_int(age_tables, 'marathon', 'male', 55, 14400)}%",
        f"it is about {_get_age_pct_for_time_int(age_tables, 'marathon', 'male', 65, 14400)}%",
    ]

    expected_pace_fragments = []
    for dist, race_time in (
        ("5k", "20:00"),
        ("5k", "25:00"),
        ("10k", "45:00"),
        ("10k", "50:00"),
        ("half", "1:45:00"),
        ("half", "2:00:00"),
        ("marathon", "3:30:00"),
        ("marathon", "4:00:00"),
    ):
        row = _get_pace_row(pace_tables, dist, race_time)
        rpi_str = f"{float(row['rpi']):.1f}"
        expected_pace_fragments.append(
            f"(RPI {rpi_str}) trains at {row['paces']['easy']['mi']}/mi easy, {row['paces']['threshold']['mi']}/mi threshold, and {row['paces']['interval']['mi']}/mi intervals"
        )

    row_330 = _get_pace_row(pace_tables, "marathon", "3:30:00")
    row_400 = _get_pace_row(pace_tables, "marathon", "4:00:00")
    expected_pace_fragments.extend(
        [
            f"Marathon-pace training runs at {row_330['paces']['marathon']['mi']}/mi.",
            f"with marathon-pace runs at {row_400['paces']['marathon']['mi']}/mi.",
            f"A 45:00 10K gives an RPI of {float(_get_pace_row(pace_tables, '10k', '45:00')['rpi']):.1f}.",
            f"For a 4:00:00 marathoner, that is {row_400['paces']['easy']['mi']}/mi",
        ]
    )

    for fragment in expected_age_fragments:
        assert fragment in age_page_source, f"Missing age-claim fragment: {fragment}"

    for fragment in expected_pace_fragments:
        assert fragment in pace_page_source, f"Missing pace-claim fragment: {fragment}"
