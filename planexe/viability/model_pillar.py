"""
Pillar model definitions for the viability assessment system.

This module contains the PillarEnum that represents the four CAS pillars
used in viability assessment: HumanStability, EconomicResilience, 
EcologicalIntegrity, and Rights_Legality.

CAS (Complex Adaptive Systems) Theory:
CAS is a framework for understanding systems that are composed of many
interacting components that adapt and evolve over time. For more information
on the foundational theory, see: https://en.wikipedia.org/wiki/Complex_adaptive_system

In the context of project viability assessment, CAS theory helps evaluate
whether a proposed project can thrive within the complex, interconnected
systems of human society, economy, and environment.

The four CAS pillars used in this system represent a custom application
of CAS theory to project viability assessment. These pillars are the
fundamental dimensions that must be stable and resilient for a project
to be viable:

1. HumanStability: Social acceptance, stakeholder buy-in, cultural fit,
   and human factors that could support or undermine the project
2. EconomicResilience: Financial sustainability, market viability,
   cost-effectiveness, and economic factors that ensure long-term success
3. EcologicalIntegrity: Environmental impact, sustainability,
   resource availability, and ecological factors that affect viability
4. Rights_Legality: Legal compliance, regulatory requirements,
   intellectual property, and rights-based considerations
"""
from enum import Enum

class PillarEnum(str, Enum):
    """Canonical set of pillars for viability assessment."""
    HumanStability = "HumanStability"
    EconomicResilience = "EconomicResilience"
    EcologicalIntegrity = "EcologicalIntegrity"
    Rights_Legality = "Rights_Legality"
    
    @property
    def display_name(self) -> str:
        """Human-readable title for UI."""
        return {
            PillarEnum.HumanStability: "Human Stability",
            PillarEnum.EconomicResilience: "Economic Resilience",
            PillarEnum.EcologicalIntegrity: "Ecological Integrity",
            PillarEnum.Rights_Legality: "Rights & Legality",
        }[self]
