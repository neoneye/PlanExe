"""
Pillar model definitions for the viability assessment system.

This module contains the PillarEnum that represents the four CAS pillars
used in viability assessment: HumanStability, EconomicResilience, 
EcologicalIntegrity, and Rights_Legality.
"""

from enum import Enum


class PillarEnum(str, Enum):
    """The four CAS pillars for viability assessment."""
    HumanStability = "HumanStability"
    EconomicResilience = "EconomicResilience"
    EcologicalIntegrity = "EcologicalIntegrity"
    Rights_Legality = "Rights_Legality"
    
    @property
    def display_name(self) -> str:
        """Return human-readable display name for the pillar."""
        display_names = {
            "HumanStability": "Human Stability",
            "EconomicResilience": "Economic Resilience", 
            "EcologicalIntegrity": "Ecological Integrity",
            "Rights_Legality": "Rights & Legality",
        }
        return display_names[self.value]
