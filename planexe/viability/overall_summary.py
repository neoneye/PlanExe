"""Overall viability roll-up (Step 4).

This module implements the mechanical aggregation rules described in
`planexe/viability/README.md` under "Step 4 — Emit Overall & Viability Summary".
It consumes the structured outputs from the previous viability steps
(`Domains`, `Blockers`, `FixPack`) and emits a concise verdict that can
be serialized to JSON and markdown.

PROMPT> python -u -m planexe.viability.overall_summary | tee output.txt
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from enum import StrEnum
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from planexe.markdown_util.escape_markdown import escape_markdown
from planexe.viability.model_domain import DomainEnum
from planexe.viability.model_status import StatusEnum

# ---------------------------------------------------------------------------
# Pydantic payload models (lenient: accept extra fields)
# ---------------------------------------------------------------------------


class DomainItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    domain: str
    status: str
    reason_codes: List[str] = Field(default_factory=list)
    evidence_todo: List[str] = Field(default_factory=list)


class DomainsPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    domains: List[DomainItem]


class BlockerItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    domain: str
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

class RecommendationEnum(StrEnum):
    """
    Canonical go/no-go style recommendation derived from per-domain statuses.

    Values
    ------
    GO
        No blocking (RED) or unknown (GRAY) findings remain. Proceed with normal
        execution; no additional gating is required.

    GO_IF_FP0
        There are RED and/or GRAY findings, but *every* such item is explicitly
        covered by the FP0 fixpack (i.e., there are concrete, owned, time-bound
        actions with clear success criteria). Proceed **only if** FP0 is accepted
        and treated as a gate—execution must include FP0 as an immediate, enforced
        prerequisite or parallel track.

    PROCEED_WITH_CAUTION
        No RED remains, but at least one GRAY (unknown/insufficient signal) exists
        that is **not** covered by FP0. You may proceed, but risks are active and
        must be monitored/mitigated; this is not a hard stop.

    HOLD
        At least one RED finding remains **not** covered by FP0. Do not proceed
        until the blocker is resolved or brought under FP0 coverage.

    Notes
    -----
    - “FP0” (FixPack 0) is the first, minimal risk-reduction bundle of tasks that
      must be executed immediately to unblock or de-risk the plan.
    - “Covered by FP0” means there is a specific task in FP0 that addresses the
      finding with an owner, time target, and acceptance criteria sufficient to
      make the decision safe to proceed.
    - Use `.value` at I/O boundaries (reports/JSON) to serialize the enum.
    """
    
    GO = "GO"
    GO_IF_FP0 = "GO_IF_FP0"
    PROCEED_WITH_CAUTION = "PROCEED_WITH_CAUTION"
    HOLD = "HOLD"

    @classmethod
    def determine(
        cls,
        *,
        statuses: Sequence[str],
        red_gray_covered: bool,
    ) -> "RecommendationEnum":
        """
        Map domain statuses + FP0 coverage into a single RecommendationEnum.

        Parameters
        ----------
        statuses :
            Sequence of per-domain status strings (case-insensitive). Expected values:
            "RED", "GRAY", "YELLOW", "GREEN". Unknown values are ignored (i.e., they
            do not contribute to RED/GRAY detection).
        red_gray_covered :
            True if **all** RED and GRAY findings are explicitly covered by FP0
            (see class docstring for what “covered” entails). If there are no RED/GRAY
            findings, this flag has no effect.

        Returns
        -------
        RecommendationEnum
            One of: GO, GO_IF_FP0, PROCEED_WITH_CAUTION, HOLD.

        Decision Rules (deterministic)
        ------------------------------
        - If ANY domain is RED and not fully covered by FP0 → HOLD.
        - Else if any domain is RED or GRAY and all such items are covered by FP0 → GO_IF_FP0.
        - Else if any domain is GRAY (unknowns) → PROCEED_WITH_CAUTION.
        - Else → GO.

        Examples
        --------
        >>> RecommendationEnum.determine(statuses=["GREEN", "YELLOW"], red_gray_covered=False)
        <RecommendationEnum.GO: 'GO'>
        >>> RecommendationEnum.determine(statuses=["GRAY"], red_gray_covered=False)
        <RecommendationEnum.PROCEED_WITH_CAUTION: 'PROCEED_WITH_CAUTION'>
        >>> RecommendationEnum.determine(statuses=["GRAY"], red_gray_covered=True)
        <RecommendationEnum.GO_IF_FP0: 'GO_IF_FP0'>
        >>> RecommendationEnum.determine(statuses=["RED"], red_gray_covered=False)
        <RecommendationEnum.HOLD: 'HOLD'>
        >>> RecommendationEnum.determine(statuses=["RED", "GRAY"], red_gray_covered=True)
        <RecommendationEnum.GO_IF_FP0: 'GO_IF_FP0'>
        """
        normalized = [status.upper() for status in statuses]
        has_red = any(status == StatusEnum.RED.value for status in normalized)
        has_gray = any(status == StatusEnum.GRAY.value for status in normalized)

        # Hard stop on uncovered RED
        if has_red and not red_gray_covered:
            return cls.HOLD

        # Gated go if RED/GRAY are covered by FP0
        if (has_red or has_gray) and red_gray_covered:
            return cls.GO_IF_FP0

        # Caution when unknowns remain (GRAY) without FP0 gating
        if has_gray:
            return cls.PROCEED_WITH_CAUTION

        # Otherwise we're clear to GO
        return cls.GO


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
    header_markdown: str
    critical_issues_markdown: str
    flips_to_go_markdown: str
    markdown: str

    @classmethod
    def execute(
        cls,
        *,
        domains_payload: Any,
        blockers_payload: Any,
        fix_packs_payload: Any,
        max_why: int = 3,
        max_flips: int = 5,
    ) -> "OverallSummary":
        """Compute the viability roll-up using the deterministic Step 4 rules."""

        domains_model = _parse_model(
            DomainsPayload,
            domains_payload,
            field_name="domains",
            expected_field="domains",
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

        if not domains_model.domains:
            raise ValueError("Domains payload must include at least one domain entry.")

        status_by_domain: Dict[str, str] = {
            item.domain: item.status.upper()
            for item in domains_model.domains
        }

        statuses: List[str] = list(status_by_domain.values())
        worst_status = _worst_status(statuses)
        worst_status = worst_status or StatusEnum.GRAY.value

        fp0_blocker_ids = set(_collect_fp0_ids(fix_packs_model.fix_packs))

        red_gray_blockers: set[str] = set()
        unmatched_blockers: set[str] = set()

        for blocker in blockers_model.blockers:
            domain_status = status_by_domain.get(blocker.domain)
            if domain_status in {StatusEnum.RED.value, StatusEnum.GRAY.value}:
                red_gray_blockers.add(blocker.id)
            elif domain_status is None:
                unmatched_blockers.add(blocker.id)

        has_red_or_gray_domain = any(status in {StatusEnum.RED.value, StatusEnum.GRAY.value} for status in statuses)
        red_gray_covered = (
            has_red_or_gray_domain
            and not unmatched_blockers
            and red_gray_blockers.issubset(fp0_blocker_ids)
        )

        upgraded_status = worst_status
        if red_gray_covered:
            upgraded_status = STATUS_UPGRADE_MAP.get(worst_status, worst_status)

        recommendation_value: RecommendationEnum = RecommendationEnum.determine(
            statuses=statuses,
            red_gray_covered=red_gray_covered,
        )
        recommendation: str = recommendation_value.value

        why_items = _build_why_list(
            domains=domains_model.domains,
            max_items=max_why,
        )

        what_flips_to_go = _build_flips_list(
            blockers=blockers_model.blockers,
            fp0_ids=fp0_blocker_ids,
            max_items=max_flips,
        )

        overall_payload = OverallPayload(
            status=upgraded_status,
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

        header_markdown = cls.format_header_markdown(payload=result_payload)
        critical_issues_markdown = cls.format_critical_issues_markdown(payload=result_payload)
        flips_to_go_markdown = cls.format_flips_to_go_markdown(payload=result_payload)
        markdown = cls.convert_to_markdown(payload=result_payload)

        return cls(
            overall=result_payload.overall.model_dump(),
            viability_summary=result_payload.viability_summary.model_dump(),
            metadata=metadata,
            header_markdown=header_markdown,
            critical_issues_markdown=critical_issues_markdown,
            flips_to_go_markdown=flips_to_go_markdown,
            markdown=markdown,
        )

    @staticmethod
    def format_header_markdown(*, payload: OverallSummaryPayload) -> str:
        lines: List[str] = []
        lines.append(f"- **Status:** {escape_markdown(payload.overall.status)}")
        lines.append(f"- **Recommendation:** {escape_markdown(payload.viability_summary.recommendation)}")
        return "\n".join(lines)

    @staticmethod
    def format_critical_issues_markdown(*, payload: OverallSummaryPayload) -> str:
        lines: List[str] = []
        if payload.viability_summary.why:
            # Build table header
            lines.append("| Domain | Status | Issue Codes |")
            lines.append("|--------|--------|-------------|")
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
        return "\n".join(lines)

    @staticmethod
    def format_flips_to_go_markdown(*, payload: OverallSummaryPayload) -> str:
        lines: List[str] = []
        lines.append('<p class="section-subtitle">Must be met to proceed.</p>')
        if payload.viability_summary.what_flips_to_go:
            for item in payload.viability_summary.what_flips_to_go:
                lines.append(f"- {escape_markdown(item)}")
        else:
            lines.append("- FP0 is empty; no gating acceptance tests.")
        return "\n".join(lines)

    @staticmethod
    def convert_to_markdown(*, payload: OverallSummaryPayload) -> str:
        lines: List[str] = []
        lines.append(OverallSummary.format_header_markdown(payload=payload))
        lines.append("")
        lines.append("### Summary of Critical Issues by Domain")
        lines.append(OverallSummary.format_critical_issues_markdown(payload=payload))
        lines.append("")
        lines.append("### Go/No-Go Criteria")
        lines.append(OverallSummary.format_flips_to_go_markdown(payload=payload))
        return "\n".join(lines)

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

    def save_header_markdown(self, file_path: str) -> None:
        with open(file_path, "w", encoding="utf-8") as file_handle:
            file_handle.write(self.header_markdown)

    def save_critical_issues_markdown(self, file_path: str) -> None:
        with open(file_path, "w", encoding="utf-8") as file_handle:
            file_handle.write(self.critical_issues_markdown)

    def save_flips_to_go_markdown(self, file_path: str) -> None:
        with open(file_path, "w", encoding="utf-8") as file_handle:
            file_handle.write(self.flips_to_go_markdown)

    def save_markdown(self, file_path: str) -> None:
        with open(file_path, "w", encoding="utf-8") as file_handle:
            file_handle.write(self.markdown)


# ---------------------------------------------------------------------------
# Helper builders for summary fields & metadata
# ---------------------------------------------------------------------------



def _build_why_list(*, domains: Sequence[DomainItem], max_items: int) -> List[WhyItem]:
    """Build a list of WhyItem dataclasses for the Why section."""
    reasons: List[Tuple[int, WhyItem]] = []
    for domain in domains:
        status = domain.status.upper()
        if status == StatusEnum.GREEN.value:
            continue

        display = DomainEnum.get_display_name(domain.domain)
        
        # Extract reason codes or evidence items
        if domain.reason_codes:
            codes = ", ".join(domain.reason_codes[:5])  # Show up to 5 codes
        elif domain.evidence_todo:
            codes = f"Evidence needed: {', '.join(domain.evidence_todo[:3])}"
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
    example_domains = {
        "domains": [
            {
                "domain": DomainEnum.HumanStability.value,
                "status": StatusEnum.YELLOW.value,
                "reason_codes": ["STAFF_AVERSION"],
                "evidence_todo": ["Stakeholder survey"]
            },
            {
                "domain": DomainEnum.EconomicResilience.value,
                "status": StatusEnum.RED.value,
                "reason_codes": ["CONTINGENCY_LOW"]
            },
            {
                "domain": DomainEnum.EcologicalIntegrity.value,
                "status": StatusEnum.GREEN.value
            },
            {
                "domain": DomainEnum.Rights_Legality.value,
                "status": StatusEnum.GRAY.value,
                "evidence_todo": ["DPIA"]
            },
        ]
    }

    example_blockers = {
        "blockers": [
            {
                "id": "B1",
                "domain": DomainEnum.EconomicResilience.value,
                "acceptance_tests": [">=10% contingency approved"]
            },
            {
                "id": "B2",
                "domain": DomainEnum.Rights_Legality.value,
                "acceptance_tests": ["Finalize DPIA"]
            },
            {
                "id": "B3",
                "domain": DomainEnum.HumanStability.value,
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
        domains_payload=example_domains,
        blockers_payload=example_blockers,
        fix_packs_payload=example_fix_packs,
    )

    print(json.dumps(summary.to_dict(include_metadata=True, include_markdown=False), indent=2))
    print("\nMarkdown:\n")
    print(summary.markdown)
