"""
Author: Claude Code using Haiku 4.5
Date: 2025-10-21
PURPOSE: Define the Pydantic schema for structured intake data captured through
         OpenAI Responses API conversations. This schema enforces collection of 10 key
         planning variables (budget, timeline, team, location, scale, risk, constraints,
         stakeholders, success criteria, domain) before Luigi pipeline execution.
SRP and DRY check: Pass - Single responsibility of intake schema definition.
                   Reused across conversation service, API models, and pipeline setup.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum
from datetime import datetime


class RiskTolerance(str, Enum):
    """User's willingness to experiment vs. play it safe."""
    conservative = "conservative"
    moderate = "moderate"
    aggressive = "aggressive"
    experimental = "experimental"


class ProjectScale(str, Enum):
    """Project scope/ambition level."""
    personal = "personal"
    local = "local"
    regional = "regional"
    national = "national"
    global_ = "global"


class GeographicScope(BaseModel):
    """Where the project will physically/virtually happen."""
    is_digital_only: bool = Field(
        description="True if project is purely digital/online, false if requires physical locations"
    )
    physical_locations: List[str] = Field(
        default_factory=list,
        description="List of cities, regions, or countries where project happens (empty if digital_only)"
    )
    notes: Optional[str] = Field(
        None,
        description="Additional geographic context or logistics constraints"
    )


class BudgetInfo(BaseModel):
    """Financial information and constraints."""
    estimated_total: Optional[str] = Field(
        None,
        description="Total budget estimate as user phrased it (e.g., '$50,000', '€2M', 'bootstrapped', 'limited')"
    )
    funding_sources: List[str] = Field(
        default_factory=list,
        description="Where money comes from (e.g., 'personal savings', 'investor funding', 'grant', 'bootstrapped')"
    )
    currency: Optional[str] = Field(
        None,
        description="Primary currency for budgeting (USD, EUR, GBP, etc.)"
    )


class TimelineInfo(BaseModel):
    """Project scheduling and milestones."""
    target_completion: Optional[str] = Field(
        None,
        description="When project should be complete (e.g., '6 months', 'Q4 2025', 'ASAP', 'by end of year')"
    )
    key_milestones: List[str] = Field(
        default_factory=list,
        description="Important phases or deadline dates (e.g., 'MVP launch in 3 months', 'Beta testing by June')"
    )
    urgency: Optional[str] = Field(
        None,
        description="Urgency level and context (e.g., 'ASAP - market opportunity closing', 'flexible', 'deadline driven')"
    )


class EnrichedPlanIntake(BaseModel):
    """
    Structured intake schema for PlanExe conversation flow.

    Captures 10 key variables through natural multi-turn conversation:
    1. Project title & objective
    2. Scale & ambition
    3. Risk tolerance
    4. Budget & funding
    5. Timeline & deadlines
    6. Team & resources
    7. Geographic scope
    8. Hard constraints
    9. Success criteria
    10. Key stakeholders & governance

    This schema is enforced with 100% compliance via OpenAI Responses API
    `response_format` with `strict=true`, guaranteeing valid structured output.
    """

    # Core Project Identity (variables 1)
    project_title: str = Field(
        description="Concise project name or title (3-8 words, user's own words)"
    )
    refined_objective: str = Field(
        description="Clear statement of what user wants to achieve (2-3 sentences, user's own words)"
    )
    original_prompt: str = Field(
        description="User's original vague prompt before conversation (for reference)"
    )

    # Strategic Context (variables 2, 3, 7)
    scale: ProjectScale = Field(
        description="Project scope/ambition: personal (solo), local (community), regional, national, or global"
    )
    risk_tolerance: RiskTolerance = Field(
        description="User's willingness to experiment: conservative (proven path), moderate, aggressive, or experimental (cutting edge)"
    )
    domain: str = Field(
        description="Industry/field/domain (e.g., 'dog breeding business', 'SaaS startup', 'event planning', 'home renovation')"
    )

    # Resources (variable 5, 6)
    budget: BudgetInfo = Field(
        description="Budget and funding information"
    )
    timeline: TimelineInfo = Field(
        description="Timeline, deadlines, and milestone information"
    )
    team_size: Optional[str] = Field(
        None,
        description="How many people working on this? (e.g., 'solo', '2-3 people', '10-15 team', 'growing team')"
    )
    existing_resources: List[str] = Field(
        default_factory=list,
        description="What user already has available (skills, tools, connections, facilities, etc.)"
    )

    # Geography & Logistics (variable 4)
    geography: GeographicScope = Field(
        description="Physical or digital scope of operations"
    )

    # Constraints & Requirements (variable 8, 9)
    hard_constraints: List[str] = Field(
        default_factory=list,
        description="Things that absolutely CANNOT change (regulations, technical limits, dependencies, etc.)"
    )
    success_criteria: List[str] = Field(
        default_factory=list,
        description="How to measure success - specific, measurable outcomes (3-5 criteria)"
    )

    # Governance (variable 10)
    key_stakeholders: List[str] = Field(
        default_factory=list,
        description="Who needs to approve/be involved/care about success (e.g., 'CEO', 'board', 'customers', 'regulatory body')"
    )
    regulatory_context: Optional[str] = Field(
        None,
        description="Any laws, regulations, or compliance requirements that apply"
    )

    # Enrichment Metadata (agent's assessment)
    conversation_summary: str = Field(
        description="Agent's concise summary of conversation and what was learned about the plan"
    )
    confidence_score: int = Field(
        ge=1,
        le=10,
        description="Agent's confidence in gathered information (1=very uncertain, 10=very clear and complete)"
    )
    areas_needing_clarification: List[str] = Field(
        default_factory=list,
        description="Aspects where user was vague or agent needs more detail (informs pipeline)"
    )

    # Metadata
    captured_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When this intake was captured"
    )


# Minimal schema for testing and backwards compatibility
class MinimalPlanIntake(BaseModel):
    """
    Minimal intake schema - just the absolute essentials.
    Used when user opts for quick mode or existing system.
    """
    project_title: str
    refined_objective: str
    original_prompt: str
    domain: str
    scale: ProjectScale
