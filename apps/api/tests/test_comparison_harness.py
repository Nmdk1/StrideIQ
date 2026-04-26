from __future__ import annotations

import json

import pytest

from services.coaching.comparison_harness import (
    HARNESS_SOURCES,
    HarnessProviderMissing,
    load_acceptance_cases,
    build_typed_context_prompt,
    data_advantage_coverage,
    render_harness_report,
    run_harness,
)


def _case(case_id: str = "persistent_fact_recall_volume"):
    return {
        "eval_schema_version": "artifact7.v1",
        "id": case_id,
        "domain": "meta_memory",
        "case_type": "edge",
        "situation": {"athlete_state": "60mpw athlete", "context": "new thread"},
        "conversation_turns": [{"role": "athlete", "content": "Should I add hills?"}],
        "user_message": "Should I add hills?",
        "required_context": ["weekly_volume_mpw=60", "recent_threads remembers 60mpw"],
        "data_advantage_must_include": [
            "names weekly_volume_mpw=60 from the ledger by the specific number",
            "signals that the volume context is remembered from the prior thread or ledger",
        ],
    }


@pytest.mark.asyncio
async def test_run_harness_requires_injected_providers(tmp_path):
    path = tmp_path / "cases.json"
    path.write_text(json.dumps([_case()]), encoding="utf-8")

    with pytest.raises(HarnessProviderMissing):
        await run_harness(cases_path=path)


@pytest.mark.asyncio
async def test_harness_runs_against_mocked_llms_and_ranks_v2_first(tmp_path):
    path = tmp_path / "cases.json"
    path.write_text(json.dumps([_case()]), encoding="utf-8")

    async def answer_provider(case, source):
        if source == "strideiq_v2":
            return "You mentioned the 60 mpw volume context in the prior thread. Add hills as a substitution."
        return "Add hills if it feels right."

    async def judge_provider(case, answers):
        return {
            source: {
                "correctness": 5 if source == "strideiq_v2" else 3,
                "helpfulness": 5 if source == "strideiq_v2" else 3,
                "specificity": 5 if source == "strideiq_v2" else 2,
                "voice_alignment": 5 if source == "strideiq_v2" else 3,
                "outcome": 5 if source == "strideiq_v2" else 3,
                "notes": f"notes:{source}",
            }
            for source in HARNESS_SOURCES
        }

    report = await run_harness(
        cases_path=path,
        answer_provider=answer_provider,
        judge_provider=judge_provider,
    )

    assert report.v2_unanimous_number_one is True
    case_report = report.case_reports[0]
    assert case_report.rankings["correctness"][0] == "strideiq_v2"
    assert all(item.covered for item in case_report.data_advantage_coverage)


def test_data_advantage_coverage_identifies_misses():
    coverage = data_advantage_coverage(
        "The answer names 60 mpw but never says this came from memory.",
        [
            "names weekly_volume_mpw=60 from the ledger by the specific number",
            "names Achilles and calf tissue-load risk",
        ],
    )

    assert coverage[0].covered is True
    assert coverage[1].covered is False


@pytest.mark.asyncio
async def test_report_rendering_contains_required_sections(tmp_path):
    path = tmp_path / "cases.json"
    path.write_text(json.dumps([_case("grok_physiology_breathing")]), encoding="utf-8")

    def answer_provider(case, source):
        return "60 mpw from the ledger and prior thread."

    def judge_provider(case, answers):
        return {
            source: {
                "correctness": 4,
                "helpfulness": 4,
                "specificity": 4,
                "voice_alignment": 4,
                "outcome": 4,
                "notes": "ok",
            }
            for source in HARNESS_SOURCES
        }

    report = await run_harness(
        cases_path=path,
        answer_provider=answer_provider,
        judge_provider=judge_provider,
    )
    markdown = render_harness_report(report)

    assert "# Coach Runtime V2 Comparison Harness" in markdown
    assert "## grok_physiology_breathing" in markdown
    assert "### Ranking Matrix" in markdown
    assert "### Data Advantage Coverage" in markdown
    assert "### Answers" in markdown


def test_typed_context_prompt_excludes_strideiq_packet_access():
    forbidden = (
        "weekly_volume_mpw",
        "recent_threads",
        "athlete_facts",
        "cut_active",
        "target_event",
        "from ledger",
        "recent_activities",
        "required_context",
        "situation",
    )

    for case in load_acceptance_cases():
        prompt = build_typed_context_prompt(case)
        lower = prompt.lower()
        for term in forbidden:
            assert term not in lower


def test_typed_context_prompt_preserves_user_turns_verbatim():
    case = {
        "conversation_turns": [
            {"role": "athlete", "content": "First athlete turn."},
            {"role": "assistant", "content": "Assistant metadata must not leak."},
            {"role": "user", "content": "Final user turn?"},
        ],
        "user_message": "Different final message",
        "situation": {"athlete_state": "weekly_volume_mpw=60"},
        "required_context": ["cut_active.flag=true"],
    }

    prompt = build_typed_context_prompt(case)

    assert (
        "Use only the athlete's typed messages below. You do not have access to their training history, activities, or prior conversations."
        in prompt
    )
    assert "- First athlete turn." in prompt
    assert "- Final user turn?" in prompt
    assert "Assistant metadata must not leak." not in prompt
    assert "weekly_volume_mpw" not in prompt
    assert "cut_active" not in prompt
