"""
Author: Claude Code using Sonnet 4.5
Date: 2025-10-21
PURPOSE: Helper utilities for Luigi tasks to read and use enriched intake data from the
         conversation flow. Allows tasks to skip LLM calls when structured data is already
         available from the EnrichedPlanIntake schema captured via Responses API.

         Key Functions:
         - read_enriched_intake(): Load enriched_intake.json from run directory
         - has_enriched_intake(): Check if enriched intake data exists
         - should_skip_location_task(): Check if PhysicalLocationsTask can use enriched data
         - should_skip_currency_task(): Check if CurrencyStrategyTask can use enriched data
         - get_*(): Various getters for extracting specific intake variables

SRP and DRY check: Pass - Single responsibility of intake data access utilities.
                   Used by multiple Luigi tasks (PhysicalLocationsTask, CurrencyStrategyTask, etc.)
                   to avoid code duplication when reading/parsing enriched_intake.json.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


def read_enriched_intake(run_id_dir: Path) -> Optional[Dict[str, Any]]:
    """
    Read enriched_intake.json from the run directory if it exists.

    Args:
        run_id_dir: Path to the run directory (e.g., run/some-uuid/)

    Returns:
        Dictionary containing enriched intake data, or None if file doesn't exist

    Example:
        >>> intake = read_enriched_intake(Path("run/abc-123"))
        >>> if intake:
        ...     print(intake['project_title'])
    """
    enriched_intake_path = run_id_dir / "enriched_intake.json"

    if not enriched_intake_path.exists():
        logger.debug(f"No enriched_intake.json found at {enriched_intake_path}")
        return None

    try:
        with open(enriched_intake_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            logger.info(f"Successfully loaded enriched intake data from {enriched_intake_path}")
            return data
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse enriched_intake.json: {e}")
        return None
    except Exception as e:
        logger.error(f"Error reading enriched_intake.json: {e}")
        return None


def has_enriched_intake(run_id_dir: Path) -> bool:
    """
    Check if enriched intake data exists and is valid.

    Args:
        run_id_dir: Path to the run directory

    Returns:
        True if enriched_intake.json exists and contains valid data
    """
    intake = read_enriched_intake(run_id_dir)
    return intake is not None and isinstance(intake, dict) and len(intake) > 0


def should_skip_location_task(enriched_intake: Dict[str, Any]) -> bool:
    """
    Determine if PhysicalLocationsTask can skip LLM call using enriched intake data.

    Args:
        enriched_intake: Dictionary containing enriched intake data

    Returns:
        True if geography data is sufficient to skip the LLM task

    Logic:
        - If is_digital_only is True, we have enough info (no physical locations needed)
        - If is_digital_only is False and physical_locations list is populated, we have locations
        - Otherwise, fall back to LLM task
    """
    if not enriched_intake:
        return False

    geography = enriched_intake.get('geography')
    if not geography or not isinstance(geography, dict):
        return False

    # Digital-only projects don't need location analysis
    if geography.get('is_digital_only') is True:
        logger.info("Geography is digital-only from enriched intake - can skip PhysicalLocationsTask LLM call")
        return True

    # Physical projects with specified locations can skip LLM
    physical_locations = geography.get('physical_locations', [])
    if isinstance(physical_locations, list) and len(physical_locations) > 0:
        logger.info(f"Physical locations specified in enriched intake: {physical_locations} - can skip PhysicalLocationsTask LLM call")
        return True

    logger.info("Geography data incomplete - PhysicalLocationsTask will use LLM")
    return False


def should_skip_currency_task(enriched_intake: Dict[str, Any]) -> bool:
    """
    Determine if CurrencyStrategyTask can skip LLM call using enriched intake data.

    Args:
        enriched_intake: Dictionary containing enriched intake data

    Returns:
        True if budget currency data is sufficient to skip the LLM task

    Logic:
        - If budget.currency is specified, we have enough info
        - Otherwise, fall back to LLM task
    """
    if not enriched_intake:
        return False

    budget = enriched_intake.get('budget')
    if not budget or not isinstance(budget, dict):
        return False

    currency = budget.get('currency')
    if currency and isinstance(currency, str) and len(currency.strip()) > 0:
        logger.info(f"Currency specified in enriched intake: {currency} - can skip CurrencyStrategyTask LLM call")
        return True

    logger.info("Currency not specified - CurrencyStrategyTask will use LLM")
    return False


# Getter utilities for extracting specific intake variables

def get_project_title(enriched_intake: Dict[str, Any]) -> Optional[str]:
    """Extract project title from enriched intake."""
    return enriched_intake.get('project_title')


def get_refined_objective(enriched_intake: Dict[str, Any]) -> Optional[str]:
    """Extract refined objective from enriched intake."""
    return enriched_intake.get('refined_objective')


def get_domain(enriched_intake: Dict[str, Any]) -> Optional[str]:
    """Extract domain/industry from enriched intake."""
    return enriched_intake.get('domain')


def get_scale(enriched_intake: Dict[str, Any]) -> Optional[str]:
    """Extract project scale (personal/local/regional/national/global) from enriched intake."""
    return enriched_intake.get('scale')


def get_risk_tolerance(enriched_intake: Dict[str, Any]) -> Optional[str]:
    """Extract risk tolerance (conservative/moderate/aggressive/experimental) from enriched intake."""
    return enriched_intake.get('risk_tolerance')


def get_budget_info(enriched_intake: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract full budget information from enriched intake."""
    return enriched_intake.get('budget')


def get_budget_estimated_total(enriched_intake: Dict[str, Any]) -> Optional[str]:
    """Extract budget estimate from enriched intake."""
    budget = get_budget_info(enriched_intake)
    return budget.get('estimated_total') if budget else None


def get_budget_currency(enriched_intake: Dict[str, Any]) -> Optional[str]:
    """Extract budget currency from enriched intake."""
    budget = get_budget_info(enriched_intake)
    return budget.get('currency') if budget else None


def get_budget_funding_sources(enriched_intake: Dict[str, Any]) -> List[str]:
    """Extract budget funding sources from enriched intake."""
    budget = get_budget_info(enriched_intake)
    if budget:
        sources = budget.get('funding_sources', [])
        return sources if isinstance(sources, list) else []
    return []


def get_timeline_info(enriched_intake: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract full timeline information from enriched intake."""
    return enriched_intake.get('timeline')


def get_timeline_target_completion(enriched_intake: Dict[str, Any]) -> Optional[str]:
    """Extract target completion date from enriched intake."""
    timeline = get_timeline_info(enriched_intake)
    return timeline.get('target_completion') if timeline else None


def get_timeline_urgency(enriched_intake: Dict[str, Any]) -> Optional[str]:
    """Extract urgency level from enriched intake."""
    timeline = get_timeline_info(enriched_intake)
    return timeline.get('urgency') if timeline else None


def get_timeline_milestones(enriched_intake: Dict[str, Any]) -> List[str]:
    """Extract key milestones from enriched intake."""
    timeline = get_timeline_info(enriched_intake)
    if timeline:
        milestones = timeline.get('key_milestones', [])
        return milestones if isinstance(milestones, list) else []
    return []


def get_geography_info(enriched_intake: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract full geography information from enriched intake."""
    return enriched_intake.get('geography')


def get_is_digital_only(enriched_intake: Dict[str, Any]) -> Optional[bool]:
    """Extract whether project is digital-only from enriched intake."""
    geography = get_geography_info(enriched_intake)
    return geography.get('is_digital_only') if geography else None


def get_physical_locations(enriched_intake: Dict[str, Any]) -> List[str]:
    """Extract physical locations from enriched intake."""
    geography = get_geography_info(enriched_intake)
    if geography:
        locations = geography.get('physical_locations', [])
        return locations if isinstance(locations, list) else []
    return []


def get_team_size(enriched_intake: Dict[str, Any]) -> Optional[str]:
    """Extract team size from enriched intake."""
    return enriched_intake.get('team_size')


def get_existing_resources(enriched_intake: Dict[str, Any]) -> List[str]:
    """Extract existing resources from enriched intake."""
    resources = enriched_intake.get('existing_resources', [])
    return resources if isinstance(resources, list) else []


def get_hard_constraints(enriched_intake: Dict[str, Any]) -> List[str]:
    """Extract hard constraints from enriched intake."""
    constraints = enriched_intake.get('hard_constraints', [])
    return constraints if isinstance(constraints, list) else []


def get_success_criteria(enriched_intake: Dict[str, Any]) -> List[str]:
    """Extract success criteria from enriched intake."""
    criteria = enriched_intake.get('success_criteria', [])
    return criteria if isinstance(criteria, list) else []


def get_key_stakeholders(enriched_intake: Dict[str, Any]) -> List[str]:
    """Extract key stakeholders from enriched intake."""
    stakeholders = enriched_intake.get('key_stakeholders', [])
    return stakeholders if isinstance(stakeholders, list) else []


def get_regulatory_context(enriched_intake: Dict[str, Any]) -> Optional[str]:
    """Extract regulatory context from enriched intake."""
    return enriched_intake.get('regulatory_context')


def get_confidence_score(enriched_intake: Dict[str, Any]) -> Optional[int]:
    """Extract agent's confidence score (1-10) from enriched intake."""
    return enriched_intake.get('confidence_score')


def get_areas_needing_clarification(enriched_intake: Dict[str, Any]) -> List[str]:
    """Extract areas needing clarification from enriched intake."""
    areas = enriched_intake.get('areas_needing_clarification', [])
    return areas if isinstance(areas, list) else []


def get_conversation_summary(enriched_intake: Dict[str, Any]) -> Optional[str]:
    """Extract conversation summary from enriched intake."""
    return enriched_intake.get('conversation_summary')
