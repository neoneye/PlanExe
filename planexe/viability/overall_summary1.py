"""Overall viability roll-up (Step 4).

This module implements the mechanical aggregation rules described in
`planexe/viability/README.md` under "Step 4 — Emit Overall & Viability Summary".
It consumes the structured outputs from the previous viability steps
(`PillarsAssessment`, `Blockers`, `FixPack`) and emits a concise verdict that can
be serialized to JSON and markdown.

PROMPT> python -u -m planexe.viability.overall_summary1 | tee output1.txt
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from pydantic import BaseModel, ConfigDict, Field, ValidationError

# ---------------------------------------------------------------------------
# Pydantic payload models (lenient: accept extra fields)
# ---------------------------------------------------------------------------


class PillarItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    pillar: str
    status: str
    score: Optional[float] = None
    reason_codes: List[str] = Field(default_factory=list)
    evidence_todo: List[str] = Field(default_factory=list)


class PillarsPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    pillars: List[PillarItem]


class BlockerItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    pillar: str
    acceptance_tests: List[str] = Field(default_factory=list)


class BlockersPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    blockers: List[BlockerItem]


class FixPackItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    blocker_ids: List[str] = Field(default_factory=list)
    step_refs: List[str] = Field(default_factory=list)


class FixPacksPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    fix_packs: List[FixPackItem]


class OverallPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    score: Optional[int]
    status: str
    confidence: str


class ViabilitySummaryPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    recommendation: str
    why: List[str]
    what_flips_to_go: List[str]


class OverallSummaryPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    overall: OverallPayload
    viability_summary: ViabilitySummaryPayload


# ---------------------------------------------------------------------------
# Aggregation constants & helpers
# ---------------------------------------------------------------------------

STATUS_SEVERITY = {
    "RED": 3,
    "GRAY": 2,
    "YELLOW": 1,
    "GREEN": 0,
}

STATUS_UPGRADE_MAP = {
    "RED": "YELLOW",
    "GRAY": "YELLOW",
    "YELLOW": "GREEN",
    "GREEN": "GREEN",
}

PILLAR_DISPLAY_NAMES = {
    "HumanStability": "Human Stability",
    "EconomicResilience": "Economic Resilience",
    "EcologicalIntegrity": "Ecological Integrity",
    "Rights_Legality": "Rights & Legality",
}

RECOMMENDATION_GO = "GO"
RECOMMENDATION_GO_IF_FP0 = "GO_IF_FP0"
RECOMMENDATION_PROCEED = "PROCEED_WITH_CAUTION"


def _coerce_payload_dict(payload: Any, *, expected_field: str, context: str) -> Dict[str, Any]:
    """Best-effort conversion of various payload shapes into a dict containing `expected_field`."""

    try:
        if isinstance(payload, BaseModel):
            data = payload.model_dump()
        elif isinstance(payload, (bytes, bytearray)):
            data = json.loads(payload.decode("utf-8"))
        elif isinstance(payload, str):
            stripped = payload.strip()
            if not stripped:
                raise ValueError("empty string")
            data = json.loads(stripped)
        elif isinstance(payload, dict):
            data = payload
        else:
            raise TypeError(f"Unsupported payload type: {type(payload)!r}")
    except (TypeError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(f"Failed to parse {context} payload as JSON.") from exc

    # Some writers (older steps) may nest the useful content under a `response` key.
    if expected_field not in data:
        nested = data.get("response")
        if isinstance(nested, dict) and expected_field in nested:
            data = nested

    if expected_field not in data:
        raise ValueError(f"{context} payload missing '{expected_field}' field.")

    return data


def _parse_model(
    model: type[BaseModel],
    payload: Any,
    *,
    field_name: str,
    expected_field: str,
) -> BaseModel:
    if isinstance(payload, model):
        return payload
    data = _coerce_payload_dict(payload, expected_field=expected_field, context=field_name)
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise ValueError(f"Invalid {field_name} payload for overall summary.") from exc


def _worst_status(statuses: Iterable[str]) -> Optional[str]:
    worst: Tuple[int, Optional[str]] = (-1, None)
    for status in statuses:
        normalized = status.upper()
        severity = STATUS_SEVERITY.get(normalized, STATUS_SEVERITY["GRAY"])
        if severity > worst[0]:
            worst = (severity, normalized)
    return worst[1]


def _confidence_from_statuses(statuses: Sequence[str]) -> str:
    normalized = [status.upper() for status in statuses]
    if any(status == "RED" for status in normalized):
        return "Low"
    if any(status == "GRAY" for status in normalized):
        return "Low"
    if any(status == "YELLOW" for status in normalized):
        return "Medium"
    return "High"


def _compute_average_score(scores: Sequence[Optional[float]]) -> Optional[int]:
    numeric = [float(score) for score in scores if score is not None]
    if not numeric:
        return None
    return round(sum(numeric) / len(numeric))


def _collect_fp0_ids(fix_packs: Sequence[FixPackItem]) -> List[str]:
    for pack in fix_packs:
        if pack.id.upper() == "FP0":
            ids = pack.blocker_ids or pack.step_refs
            return [blocker_id for blocker_id in ids if blocker_id]
    return []


def _dedupe(strings: Iterable[str], limit: int) -> List[str]:
    seen: set[str] = set()
    result: List[str] = []
    for raw in strings:
        item = (raw or "").strip()
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
        if len(result) >= limit:
            break
    return result


def _pillar_focus_reason(pillar: PillarItem) -> Optional[str]:
    if pillar.reason_codes:
        joined = ", ".join(pillar.reason_codes[:3])
        return f"Reason codes: {joined}"
    if pillar.evidence_todo:
        joined = ", ".join(pillar.evidence_todo[:2])
        return f"Evidence to gather: {joined}"
    return None


# ---------------------------------------------------------------------------
# Result object
# ---------------------------------------------------------------------------


@dataclass
class OverallSummary:
    """Container for the step-4 roll-up."""

    overall: Dict[str, Any]
    viability_summary: Dict[str, Any]
    metadata: Dict[str, Any]
    markdown: str

    @classmethod
    def execute(
        cls,
        *,
        pillars_payload: Any,
        blockers_payload: Any,
        fix_packs_payload: Any,
        max_why: int = 3,
        max_flips: int = 5,
    ) -> "OverallSummary":
        """Compute the viability roll-up using the deterministic Step 4 rules."""

        pillars_model = _parse_model(
            PillarsPayload,
            pillars_payload,
            field_name="pillars",
            expected_field="pillars",
        )
        blockers_model = _parse_model(
            BlockersPayload,
            blockers_payload,
            field_name="blockers",
            expected_field="blockers",
        )
        fix_packs_model = _parse_model(
            FixPacksPayload,
            fix_packs_payload,
            field_name="fix_packs",
            expected_field="fix_packs",
        )

        if not pillars_model.pillars:
            raise ValueError("Pillars payload must include at least one pillar entry.")

        status_by_pillar: Dict[str, str] = {
            item.pillar: item.status.upper()
            for item in pillars_model.pillars
        }

        statuses: List[str] = list(status_by_pillar.values())
        worst_status = _worst_status(statuses)
        worst_status = worst_status or "GRAY"

        fp0_blocker_ids = set(_collect_fp0_ids(fix_packs_model.fix_packs))

        red_gray_blockers: set[str] = set()
        unmatched_blockers: set[str] = set()

        for blocker in blockers_model.blockers:
            pillar_status = status_by_pillar.get(blocker.pillar)
            if pillar_status in {"RED", "GRAY"}:
                red_gray_blockers.add(blocker.id)
            elif pillar_status is None:
                unmatched_blockers.add(blocker.id)

        has_red_or_gray_pillar = any(status in {"RED", "GRAY"} for status in statuses)
        red_gray_covered = (
            has_red_or_gray_pillar
            and not unmatched_blockers
            and red_gray_blockers.issubset(fp0_blocker_ids)
        )

        upgraded_status = worst_status
        if red_gray_covered:
            upgraded_status = STATUS_UPGRADE_MAP.get(worst_status, worst_status)

        overall_score = _compute_average_score([pillar.score for pillar in pillars_model.pillars])
        confidence = _confidence_from_statuses(statuses)

        recommendation = _determine_recommendation(
            statuses=statuses,
            red_gray_covered=red_gray_covered,
        )

        why_reasons = _build_why_list(
            pillars=pillars_model.pillars,
            max_items=max_why,
        )

        what_flips_to_go = _build_flips_list(
            blockers=blockers_model.blockers,
            fp0_ids=fp0_blocker_ids,
            max_items=max_flips,
        )

        overall_payload = OverallPayload(
            score=overall_score,
            status=upgraded_status,
            confidence=confidence,
        )

        viability_summary_payload = ViabilitySummaryPayload(
            recommendation=recommendation,
            why=why_reasons,
            what_flips_to_go=what_flips_to_go,
        )

        result_payload = OverallSummaryPayload(
            overall=overall_payload,
            viability_summary=viability_summary_payload,
        )

        metadata = _build_metadata(
            statuses=statuses,
            worst_status=worst_status,
            upgraded_status=upgraded_status,
            fp0_blocker_ids=sorted(fp0_blocker_ids),
            red_gray_blockers=sorted(red_gray_blockers),
            unmatched_blockers=sorted(unmatched_blockers),
            red_gray_covered=red_gray_covered,
        )

        markdown = cls.convert_to_markdown(result_payload)

        return cls(
            overall=result_payload.overall.model_dump(),
            viability_summary=result_payload.viability_summary.model_dump(),
            metadata=metadata,
            markdown=markdown,
        )

    @staticmethod
    def convert_to_markdown(payload: OverallSummaryPayload) -> str:
        lines: List[str] = []
        lines.append("## Overall Viability")
        lines.append(f"- Status: {payload.overall.status}")
        score_value = payload.overall.score
        lines.append(f"- Score: {score_value if score_value is not None else 'N/A'}")
        lines.append(f"- Confidence: {payload.overall.confidence}")
        lines.append("")
        lines.append("## Recommendation")
        lines.append(f"- {payload.viability_summary.recommendation}")
        lines.append("")
        lines.append("## Why")
        if payload.viability_summary.why:
            for item in payload.viability_summary.why:
                lines.append(f"- {item}")
        else:
            lines.append("- No major viability flags identified.")
        lines.append("")
        lines.append("## What Flips to GO")
        if payload.viability_summary.what_flips_to_go:
            for item in payload.viability_summary.what_flips_to_go:
                lines.append(f"- {item}")
        else:
            lines.append("- FP0 is empty; no gating acceptance tests.")
        return "\n".join(lines).rstrip()

    def to_dict(
        self,
        *,
        include_metadata: bool = True,
        include_markdown: bool = True,
    ) -> Dict[str, Any]:
        data = {
            "overall": self.overall,
            "viability_summary": self.viability_summary,
        }
        if include_metadata:
            data["metadata"] = self.metadata
        if include_markdown:
            data["markdown"] = self.markdown
        return data

    def save_raw(self, file_path: str) -> None:
        with open(file_path, "w", encoding="utf-8") as file_handle:
            json.dump(self.to_dict(), file_handle, indent=2)

    def save_markdown(self, file_path: str) -> None:
        with open(file_path, "w", encoding="utf-8") as file_handle:
            file_handle.write(self.markdown)


# ---------------------------------------------------------------------------
# Helper builders for summary fields & metadata
# ---------------------------------------------------------------------------


def _determine_recommendation(
    *,
    statuses: Sequence[str],
    red_gray_covered: bool,
) -> str:
    normalized = [status.upper() for status in statuses]
    has_red = any(status == "RED" for status in normalized)
    has_gray = any(status == "GRAY" for status in normalized)

    if has_red or has_gray:
        if red_gray_covered:
            return RECOMMENDATION_GO_IF_FP0
        return RECOMMENDATION_PROCEED

    return RECOMMENDATION_GO


def _build_why_list(*, pillars: Sequence[PillarItem], max_items: int) -> List[str]:
    reasons: List[Tuple[int, str]] = []
    for pillar in pillars:
        status = pillar.status.upper()
        if status == "GREEN":
            continue

        display = PILLAR_DISPLAY_NAMES.get(pillar.pillar, pillar.pillar)
        score_fragment = f"score {int(pillar.score)}" if pillar.score is not None else "no score"
        reason_fragment = _pillar_focus_reason(pillar)

        base_text = f"{display} {status} ({score_fragment})"
        text = f"{base_text}: {reason_fragment}" if reason_fragment else base_text

        reasons.append((STATUS_SEVERITY.get(status, STATUS_SEVERITY["GRAY"]), text))

    if not reasons:
        return []

    reasons.sort(key=lambda item: item[0], reverse=True)
    return [text for _, text in reasons[:max_items]]


def _build_flips_list(
    *,
    blockers: Sequence[BlockerItem],
    fp0_ids: Iterable[str],
    max_items: int,
) -> List[str]:
    fp0_set = set(fp0_ids)
    acceptance_tests: List[str] = []
    for blocker in blockers:
        if blocker.id not in fp0_set:
            continue
        acceptance_tests.extend(blocker.acceptance_tests)
    return _dedupe(acceptance_tests, max_items)


def _build_metadata(
    *,
    statuses: Sequence[str],
    worst_status: str,
    upgraded_status: str,
    fp0_blocker_ids: Sequence[str],
    red_gray_blockers: Sequence[str],
    unmatched_blockers: Sequence[str],
    red_gray_covered: bool,
) -> Dict[str, Any]:
    status_counter = Counter(statuses)
    return {
        "status_counts": dict(status_counter),
        "worst_status_before_upgrade": worst_status,
        "worst_status_after_upgrade": upgraded_status,
        "fp0_blocker_ids": list(fp0_blocker_ids),
        "red_gray_blockers": list(red_gray_blockers),
        "unmatched_blockers": list(unmatched_blockers),
        "red_gray_blockers_covered_by_fp0": red_gray_covered,
    }


__all__ = ["OverallSummary"]


if __name__ == "__main__":
    example_pillars = {
        "pillars": [
            {
                "pillar": "HumanStability",
                "status": "YELLOW",
                "score": 60,
                "reason_codes": ["STAFF_AVERSION"],
                "evidence_todo": ["Stakeholder survey"]
            },
            {
                "pillar": "EconomicResilience",
                "status": "RED",
                "score": 30,
                "reason_codes": ["CONTINGENCY_LOW"]
            },
            {
                "pillar": "EcologicalIntegrity",
                "status": "GREEN",
                "score": 80
            },
            {
                "pillar": "Rights_Legality",
                "status": "GRAY",
                "score": None,
                "evidence_todo": ["DPIA"]
            },
        ]
    }

    example_blockers = {
        "blockers": [
            {
                "id": "B1",
                "pillar": "EconomicResilience",
                "acceptance_tests": [">=10% contingency approved"]
            },
            {
                "id": "B2",
                "pillar": "Rights_Legality",
                "acceptance_tests": ["Finalize DPIA"]
            },
            {
                "id": "B3",
                "pillar": "HumanStability",
                "acceptance_tests": ["Stakeholder plan signed"]
            },
        ]
    }

    example_fix_packs = {
        "fix_packs": [
            {"id": "FP0", "blocker_ids": ["B1", "B2"]},
            {"id": "FP1", "blocker_ids": ["B3"]},
        ]
    }

    summary = OverallSummary.execute(
        pillars_payload=example_pillars,
        blockers_payload=example_blockers,
        fix_packs_payload=example_fix_packs,
    )

    print(json.dumps(summary.to_dict(include_metadata=True, include_markdown=False), indent=2))
    print("\nMarkdown:\n")
    print(summary.markdown)
