"""Overall viability roll-up (Step 4).

This module implements the mechanical aggregation rules described in
`planexe/viability/README.md` under "Step 4 — Emit Overall & Viability Summary".
It consumes the structured outputs from the previous viability steps
(`PillarsAssessment`, `Blockers`, `FixPack`) and emits a concise verdict that can
be serialized to JSON and markdown.

PROMPT> python -u -m planexe.viability.overall_summary | tee output.txt

IDEA: Re-enable "score" within the overall_summary when I have gotton the pillars_assessment.py likert scores to work.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from planexe.markdown_util.escape_markdown import escape_markdown
from planexe.viability.model_pillar import PillarEnum
from planexe.viability.model_status import StatusEnum

# ---------------------------------------------------------------------------
# Pydantic payload models (lenient: accept extra fields)
# ---------------------------------------------------------------------------


class PillarItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    pillar: str
    status: str
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

    status: str
    confidence: str


class ViabilitySummaryPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    recommendation: str
    why: List[Any]  # Can be List[str] (legacy) or List[Tuple[str, str, str]] (table format)
    what_flips_to_go: List[str]


class OverallSummaryPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    overall: OverallPayload
    viability_summary: ViabilitySummaryPayload


# ---------------------------------------------------------------------------
# Aggregation constants & helpers
# ---------------------------------------------------------------------------

STATUS_SEVERITY = {
    StatusEnum.RED.value: 3,
    StatusEnum.GRAY.value: 2,
    StatusEnum.YELLOW.value: 1,
    StatusEnum.GREEN.value: 0,
}

STATUS_UPGRADE_MAP = {
    StatusEnum.RED.value: StatusEnum.YELLOW.value,
    StatusEnum.GRAY.value: StatusEnum.YELLOW.value,
    StatusEnum.YELLOW.value: StatusEnum.GREEN.value,
    StatusEnum.GREEN.value: StatusEnum.GREEN.value,
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
        severity = STATUS_SEVERITY.get(normalized, STATUS_SEVERITY[StatusEnum.GRAY.value])
        if severity > worst[0]:
            worst = (severity, normalized)
    return worst[1]


def _confidence_from_statuses(statuses: Sequence[str]) -> str:
    normalized = [status.upper() for status in statuses]
    if any(status == StatusEnum.RED.value for status in normalized):
        return "Low"
    if any(status == StatusEnum.GRAY.value for status in normalized):
        return "Low"
    if any(status == StatusEnum.YELLOW.value for status in normalized):
        return "Medium"
    return "High"


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
class WhyItem:
    """Represents a single entry in the 'Why' section."""
    display: str
    status: str
    codes: str


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
        worst_status = worst_status or StatusEnum.GRAY.value

        fp0_blocker_ids = set(_collect_fp0_ids(fix_packs_model.fix_packs))

        red_gray_blockers: set[str] = set()
        unmatched_blockers: set[str] = set()

        for blocker in blockers_model.blockers:
            pillar_status = status_by_pillar.get(blocker.pillar)
            if pillar_status in {StatusEnum.RED.value, StatusEnum.GRAY.value}:
                red_gray_blockers.add(blocker.id)
            elif pillar_status is None:
                unmatched_blockers.add(blocker.id)

        has_red_or_gray_pillar = any(status in {StatusEnum.RED.value, StatusEnum.GRAY.value} for status in statuses)
        red_gray_covered = (
            has_red_or_gray_pillar
            and not unmatched_blockers
            and red_gray_blockers.issubset(fp0_blocker_ids)
        )

        upgraded_status = worst_status
        if red_gray_covered:
            upgraded_status = STATUS_UPGRADE_MAP.get(worst_status, worst_status)

        confidence = _confidence_from_statuses(statuses)

        recommendation = _determine_recommendation(
            statuses=statuses,
            red_gray_covered=red_gray_covered,
        )

        why_items = _build_why_list(
            pillars=pillars_model.pillars,
            max_items=max_why,
        )

        what_flips_to_go = _build_flips_list(
            blockers=blockers_model.blockers,
            fp0_ids=fp0_blocker_ids,
            max_items=max_flips,
        )

        overall_payload = OverallPayload(
            status=upgraded_status,
            confidence=confidence,
        )

        # Convert WhyItem dataclasses to dicts for JSON serialization
        why_reasons = [
            {"display": item.display, "status": item.status, "codes": item.codes}
            for item in why_items
        ]

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
        lines.append(f"- Status: {payload.overall.status}")
        lines.append(f"- Confidence: {payload.overall.confidence}")
        lines.append("")
        lines.append("## Recommendation")
        lines.append(f"- {payload.viability_summary.recommendation}")
        lines.append("")
        lines.append("## Why")
        if payload.viability_summary.why:
            # Build table header
            lines.append("| Pillar | Status | Reasoning Codes |")
            lines.append("|--------|--------|-----------------|")
            # Build table rows
            for item in payload.viability_summary.why:
                # Each item is a WhyItem dataclass or dict
                if isinstance(item, dict):
                    display = item.get('display', '—')
                    status = item.get('status', '—')
                    codes = item.get('codes', '—')
                elif hasattr(item, 'display'):
                    display = item.display
                    status = item.status
                    codes = item.codes
                else:
                    # Fallback for unexpected format
                    display = '—'
                    status = '—'
                    codes = str(item)
                lines.append(f"| {escape_markdown(display)} | {escape_markdown(status)} | {escape_markdown(codes)} |")
        else:
            lines.append("- No major viability flags identified.")
        lines.append("")
        lines.append("## What Flips to GO")
        if payload.viability_summary.what_flips_to_go:
            for item in payload.viability_summary.what_flips_to_go:
                lines.append(f"- {escape_markdown(item)}")
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
    has_red = any(status == StatusEnum.RED.value for status in normalized)
    has_gray = any(status == StatusEnum.GRAY.value for status in normalized)

    if has_red or has_gray:
        if red_gray_covered:
            return RECOMMENDATION_GO_IF_FP0
        return RECOMMENDATION_PROCEED

    return RECOMMENDATION_GO


def _build_why_list(*, pillars: Sequence[PillarItem], max_items: int) -> List[WhyItem]:
    """Build a list of WhyItem dataclasses for the Why section."""
    reasons: List[Tuple[int, WhyItem]] = []
    for pillar in pillars:
        status = pillar.status.upper()
        if status == StatusEnum.GREEN.value:
            continue

        display = PillarEnum.get_display_name(pillar.pillar)
        
        # Extract reason codes or evidence items
        if pillar.reason_codes:
            codes = ", ".join(pillar.reason_codes[:5])  # Show up to 5 codes
        elif pillar.evidence_todo:
            codes = f"Evidence needed: {', '.join(pillar.evidence_todo[:3])}"
        else:
            codes = "—"

        severity = STATUS_SEVERITY.get(status, STATUS_SEVERITY[StatusEnum.GRAY.value])
        why_item = WhyItem(display=display, status=status, codes=codes)
        reasons.append((severity, why_item))

    if not reasons:
        return []

    reasons.sort(key=lambda item: item[0], reverse=True)
    return [why_item for _, why_item in reasons[:max_items]]


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
                "pillar": PillarEnum.HumanStability.value,
                "status": StatusEnum.YELLOW.value,
                "reason_codes": ["STAFF_AVERSION"],
                "evidence_todo": ["Stakeholder survey"]
            },
            {
                "pillar": PillarEnum.EconomicResilience.value,
                "status": StatusEnum.RED.value,
                "reason_codes": ["CONTINGENCY_LOW"]
            },
            {
                "pillar": PillarEnum.EcologicalIntegrity.value,
                "status": StatusEnum.GREEN.value
            },
            {
                "pillar": PillarEnum.Rights_Legality.value,
                "status": StatusEnum.GRAY.value,
                "evidence_todo": ["DPIA"]
            },
        ]
    }

    example_blockers = {
        "blockers": [
            {
                "id": "B1",
                "pillar": PillarEnum.EconomicResilience.value,
                "acceptance_tests": [">=10% contingency approved"]
            },
            {
                "id": "B2",
                "pillar": PillarEnum.Rights_Legality.value,
                "acceptance_tests": ["Finalize DPIA"]
            },
            {
                "id": "B3",
                "pillar": PillarEnum.HumanStability.value,
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
