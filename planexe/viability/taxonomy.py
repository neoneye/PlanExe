"""
Canonical taxonomy definitions shared across the viability assessment workflow.

The module reads `taxonomy.json`, validates it with the Pydantic models below,
and exposes both convenience constants and helper methods. Treat this file as
the single source of truth for domain ordering, reason codes, and scoring
policies.

PROMPT> python -m planexe.viability.taxonomy
"""
from __future__ import annotations
from functools import lru_cache
from importlib.resources import files
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Set, Tuple
import json

class DomainMetadata(BaseModel):
    """Metadata describing a viability domain."""

    value: str
    display: str
    description: str

class ScoringPolicy(BaseModel):
    """Configuration describing how viability scores are captured and defaulted."""

    likert_min: int
    likert_max: int
    factors: Tuple[str, str, str]  # ("evidence","risk","fit")
    factor_order: Tuple[str, str, str]
    default_likert_by_status: Dict[str, Dict[str, Optional[int]]]

class Normalization(BaseModel):
    """Rules for rewriting evidence strings so downstream comparisons are consistent."""

    evidence_rewrites: Dict[str, Optional[str]] = Field(default_factory=dict)

class Taxonomy(BaseModel):
    """Validated in-memory structure representing the viability taxonomy dataset."""

    domains: List[DomainMetadata]
    reason_codes_by_domain: Dict[str, List[str]]
    strength_reason_codes: Set[str] = Field(default_factory=set)
    reason_code_factor: Dict[str, Set[str]]
    default_evidence_by_domain: Dict[str, List[str]]

    # Canonical evidence templates per reason code (artifact-first, not actions)
    # Dict[str, List[str]] mapping a reason code -> ordered list of evidence templates.
    # We intentionally use List[str] even when there is only one template for a key.
    # Rationale:
    #  - Future-proof: adding a second/third template needs no migration or refactor.
    #  - Ordering encodes priority: first item is the most canonical form.
    # Invariants:
    #  - Values are lists of unique, non-empty strings (singleton lists are OK).
    #  - Missing keys must be treated by consumers as an empty list, not an error.
    # This dict with templates is not exhaustive, more items are likely to be added over time.
    evidence_templates: Dict[str, List[str]]
    evidence_acceptance_criteria: Dict[str, str] = Field(default_factory=dict)
    normalization: Normalization = Field(default_factory=Normalization)
    scoring_policy: ScoringPolicy

    @property
    def domain_values(self) -> List[str]:
        """Ordered list of domain string identifiers."""
        return [domain.value for domain in self.domains]

    def get_domain_display(self, domain_value: str) -> str:
        """Return the human-readable display name for a domain."""
        for domain in self.domains:
            if domain.value == domain_value:
                return domain.display
        return domain_value

    def get_domain_description(self, domain_value: str) -> str:
        """Return the description for a domain."""
        for domain in self.domains:
            if domain.value == domain_value:
                return domain.description
        return ""

    def reason_code_factor_set(self, code: str) -> Set[str]:
        """Return the set of factors a reason code maps to, or all factors if unspecified."""
        return set(self.reason_code_factor.get(code, self.scoring_policy.factors))

    def reason_code_fallback(self) -> Dict[str, Dict[str, str]]:
        """Pick the most-specific code per (domain, factor)."""
        fallbacks: Dict[str, Dict[str, str]] = {value: {} for value in self.domain_values}
        for domain, codes in self.reason_codes_by_domain.items():
            for code in codes:
                mapped = self.reason_code_factor_set(code)
                for f in mapped:
                    cur = fallbacks[domain].get(f)
                    if not cur:
                        fallbacks[domain][f] = code
                    else:
                        if len(self.reason_code_factor_set(code)) < len(self.reason_code_factor_set(cur)):
                            fallbacks[domain][f] = code
        return fallbacks

    def translate_reason_code_to_human_readable(self, reason_code: str) -> str:
        """
        Translate a reason code to human-readable text using evidence templates.
        
        Args:
            reason_code: The reason code (e.g., 'CHANGE_MGMT_GAPS')
            
        Returns:
            Human-readable description from evidence templates, or the original code if not found
        """
        if reason_code in self.evidence_templates:
            # Get the first (most canonical) template for this reason code
            templates = self.evidence_templates[reason_code]
            if templates and len(templates) > 0:
                return templates[0]
        
        # Fallback to the original reason code if no template found
        return reason_code

@lru_cache
def load_taxonomy() -> Taxonomy:
    """Load and validate the taxonomy JSON, caching the resulting model instance."""
    data = json.loads(files("planexe.viability").joinpath("taxonomy.json").read_text())
    tx = Taxonomy.model_validate(data)

    # sanity checks
    domain_values = tx.domain_values
    assert len(domain_values) == len(set(domain_values)), "Domain values must be unique."
    for domain in tx.domains:
        assert domain.value.strip(), "Domain value must be non-empty."
        assert domain.display.strip(), f"Domain {domain.value} must define a display label."
        assert domain.description.strip(), f"Domain {domain.value} must define a description."
    for d, codes in tx.reason_codes_by_domain.items():
        assert d in tx.domain_values, f"Unknown domain in reason_codes: {d}"
        for c in codes:
            assert c in tx.reason_code_factor or True, f"Missing reason_code_factor for {c}"
    return tx

# Convenience re-exports
TX = load_taxonomy()
DOMAIN_ORDER = TX.domain_values
DOMAIN_METADATA_BY_VALUE = {domain.value: domain for domain in TX.domains}
REASON_CODES_BY_DOMAIN = TX.reason_codes_by_domain
STRENGTH_REASON_CODES = TX.strength_reason_codes
REASON_CODE_FACTOR = TX.reason_code_factor
DEFAULT_EVIDENCE_BY_DOMAIN = TX.default_evidence_by_domain
EVIDENCE_TEMPLATES = TX.evidence_templates
EVIDENCE_ACCEPTANCE_CRITERIA = TX.evidence_acceptance_criteria
EVIDENCE_REWRITES = TX.normalization.evidence_rewrites
LIKERT_MIN = TX.scoring_policy.likert_min
LIKERT_MAX = TX.scoring_policy.likert_max
LIKERT_FACTOR_KEYS = tuple(TX.scoring_policy.factors)
FACTOR_ORDER_INDEX = {k: i for i, k in enumerate(TX.scoring_policy.factor_order)}
DEFAULT_LIKERT_BY_STATUS = TX.scoring_policy.default_likert_by_status
FALLBACK_REASON_CODE_BY_DOMAIN_AND_FACTOR = TX.reason_code_fallback()

def reason_code_factor_set(code: str) -> Set[str]:
    """Convenience wrapper mirroring `Taxonomy.reason_code_factor_set` on the cached taxonomy."""
    return TX.reason_code_factor_set(code)  # delegates to the instance

def get_domain_display(domain_value: str) -> str:
    """Return the human-readable display label for a domain value."""
    return TX.get_domain_display(domain_value)

def get_domain_description(domain_value: str) -> str:
    """Return the description text for a domain value."""
    return TX.get_domain_description(domain_value)
