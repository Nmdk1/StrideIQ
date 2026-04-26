from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable, Mapping, Sequence

ACCEPTANCE_SET_PATH = (
    Path(__file__).resolve().parents[2]
    / "tests"
    / "fixtures"
    / "v2_acceptance_set.json"
)

HARNESS_SOURCES = ("sonnet_4_6", "gpt_5_5", "opus_4_6", "strideiq_v2")
JUDGE_DIMENSIONS = (
    "correctness",
    "helpfulness",
    "specificity",
    "voice_alignment",
    "outcome",
)


class HarnessProviderMissing(RuntimeError):
    """Raised when the on-demand harness is run without injected providers."""


AnswerProvider = Callable[[Mapping[str, Any], str], Awaitable[str] | str]
JudgeProvider = Callable[
    [Mapping[str, Any], Mapping[str, str]],
    Awaitable[Mapping[str, Mapping[str, Any]]] | Mapping[str, Mapping[str, Any]],
]


@dataclass(frozen=True)
class HarnessAnswer:
    source: str
    text: str


@dataclass(frozen=True)
class DataAdvantageCoverage:
    required_atom: str
    covered: bool
    matched_terms: tuple[str, ...] = ()


@dataclass(frozen=True)
class HarnessCaseReport:
    case_id: str
    rankings: dict[str, list[str]]
    scores: dict[str, dict[str, float]]
    qualitative_notes: dict[str, str]
    data_advantage_coverage: list[DataAdvantageCoverage]
    answers: dict[str, HarnessAnswer]
    v2_unanimous_number_one: bool


@dataclass(frozen=True)
class HarnessReport:
    case_reports: list[HarnessCaseReport] = field(default_factory=list)

    @property
    def v2_unanimous_number_one(self) -> bool:
        return bool(self.case_reports) and all(
            case.v2_unanimous_number_one for case in self.case_reports
        )


def load_acceptance_cases(path: Path = ACCEPTANCE_SET_PATH) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def select_cases(
    cases: Sequence[Mapping[str, Any]],
    case_ids: Sequence[str] | None,
) -> list[Mapping[str, Any]]:
    if not case_ids:
        return list(cases)
    wanted = set(case_ids)
    selected = [case for case in cases if str(case.get("id")) in wanted]
    missing = wanted - {str(case.get("id")) for case in selected}
    if missing:
        raise KeyError(f"acceptance_cases_missing:{','.join(sorted(missing))}")
    return selected


def build_typed_context_prompt(case: Mapping[str, Any]) -> str:
    """Competitor prompt: what a frontier model gets without StrideIQ packet data."""

    turns = case.get("conversation_turns") or []
    user_turns = [
        str(turn.get("content") or "").strip()
        for turn in turns
        if str(turn.get("role") or "").lower() in {"athlete", "user"}
        and str(turn.get("content") or "").strip()
    ]
    if not user_turns and case.get("user_message"):
        user_turns = [str(case["user_message"]).strip()]
    return "\n".join(
        [
            "You are evaluating a coaching question from an endurance athlete.",
            "Use only the athlete's typed messages below. You do not have access to their training history, activities, or prior conversations.",
            "",
            "Athlete typed messages:",
            *[f"- {message}" for message in user_turns],
        ]
    )


async def _maybe_await(value: Awaitable[Any] | Any) -> Any:
    if hasattr(value, "__await__"):
        return await value
    return value


async def _answer_source(
    case: Mapping[str, Any],
    source: str,
    answer_provider: AnswerProvider,
) -> HarnessAnswer:
    text = await _maybe_await(answer_provider(case, source))
    return HarnessAnswer(source=source, text=str(text or "").strip())


def _important_terms(required_atom: str) -> tuple[str, ...]:
    text = required_atom.lower()
    raw_terms = set(re.findall(r"\b\d+(?::\d+)?\b|\b[a-z][a-z0-9_:-]{2,}\b", text))
    terms = set(raw_terms)
    for term in raw_terms:
        if "_" in term:
            terms.update(part for part in term.split("_") if part)
    stop = {
        "and",
        "the",
        "from",
        "that",
        "with",
        "must",
        "include",
        "names",
        "drawn",
        "specific",
        "recent",
        "ledger",
        "activity",
        "activities",
        "thread",
        "threads",
        "answer",
    }
    return tuple(sorted(term for term in terms if term not in stop))


def data_advantage_coverage(
    answer_text: str,
    required_atoms: Sequence[str],
) -> list[DataAdvantageCoverage]:
    lower = (answer_text or "").lower()
    coverage = []
    for atom in required_atoms:
        terms = _important_terms(atom)
        matched = tuple(term for term in terms if term in lower)
        required_count = min(2, len(terms))
        coverage.append(
            DataAdvantageCoverage(
                required_atom=atom,
                covered=len(matched) >= required_count,
                matched_terms=matched,
            )
        )
    return coverage


def rank_sources(scores: Mapping[str, Mapping[str, float]]) -> dict[str, list[str]]:
    rankings: dict[str, list[str]] = {}
    for dimension in JUDGE_DIMENSIONS:
        rankings[dimension] = sorted(
            scores.keys(),
            key=lambda source: float(scores[source].get(dimension, 0)),
            reverse=True,
        )
    return rankings


def _case_v2_unanimous_number_one(rankings: Mapping[str, Sequence[str]]) -> bool:
    return all(
        ranking and ranking[0] == "strideiq_v2"
        for dimension, ranking in rankings.items()
        if dimension in JUDGE_DIMENSIONS
    )


async def run_harness(
    *,
    case_ids: Sequence[str] | None = None,
    cases_path: Path = ACCEPTANCE_SET_PATH,
    answer_provider: AnswerProvider | None = None,
    judge_provider: JudgeProvider | None = None,
) -> HarnessReport:
    if answer_provider is None or judge_provider is None:
        raise HarnessProviderMissing(
            "run_harness requires injected answer_provider and judge_provider; "
            "CI tests use mocks and B10 wires real providers."
        )

    cases = select_cases(load_acceptance_cases(cases_path), case_ids)
    reports = []
    for case in cases:
        answers = {
            answer.source: answer
            for answer in [
                await _answer_source(case, source, answer_provider)
                for source in HARNESS_SOURCES
            ]
        }
        raw_scores = await _maybe_await(
            judge_provider(
                case, {source: answer.text for source, answer in answers.items()}
            )
        )
        scores = {
            source: {
                dimension: float((raw_scores.get(source) or {}).get(dimension, 0))
                for dimension in JUDGE_DIMENSIONS
            }
            for source in HARNESS_SOURCES
        }
        notes = {
            source: str((raw_scores.get(source) or {}).get("notes") or "")
            for source in HARNESS_SOURCES
        }
        rankings = rank_sources(scores)
        coverage = data_advantage_coverage(
            answers["strideiq_v2"].text,
            list(case.get("data_advantage_must_include") or []),
        )
        reports.append(
            HarnessCaseReport(
                case_id=str(case.get("id") or "unknown_case"),
                rankings=rankings,
                scores=scores,
                qualitative_notes=notes,
                data_advantage_coverage=coverage,
                answers=answers,
                v2_unanimous_number_one=_case_v2_unanimous_number_one(rankings),
            )
        )
    return HarnessReport(case_reports=reports)


def render_harness_report(report: HarnessReport) -> str:
    lines = [
        "# Coach Runtime V2 Comparison Harness",
        "",
        f"Aggregate V2 unanimous #1: {'YES' if report.v2_unanimous_number_one else 'NO'}",
        "",
    ]
    for case in report.case_reports:
        lines.extend(
            [
                f"## {case.case_id}",
                "",
                f"V2 unanimous #1: {'YES' if case.v2_unanimous_number_one else 'NO'}",
                "",
                "### Ranking Matrix",
                "",
                "| Dimension | Rank 1 | Rank 2 | Rank 3 | Rank 4 |",
                "|---|---|---|---|---|",
            ]
        )
        for dimension in JUDGE_DIMENSIONS:
            ranking = list(case.rankings.get(dimension) or [])
            ranking = ranking + [""] * (4 - len(ranking))
            lines.append(
                f"| {dimension} | {ranking[0]} | {ranking[1]} | {ranking[2]} | {ranking[3]} |"
            )
        lines.extend(
            [
                "",
                "### Data Advantage Coverage",
                "",
                "| Required Atom | Covered | Matched Terms |",
                "|---|---:|---|",
            ]
        )
        for item in case.data_advantage_coverage:
            lines.append(
                f"| {item.required_atom} | {'yes' if item.covered else 'no'} | {', '.join(item.matched_terms)} |"
            )
        lines.extend(["", "### Answers", ""])
        for source in HARNESS_SOURCES:
            lines.extend(
                [
                    f"#### {source}",
                    "",
                    case.answers[source].text or "_No answer returned._",
                    "",
                    f"Judge notes: {case.qualitative_notes.get(source) or '_none_'}",
                    "",
                ]
            )
    return "\n".join(lines).rstrip() + "\n"
