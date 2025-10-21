"""
One-pager that generates blockers from domains assessment.

This code corresponds to "Step 2: Emit Blockers." in the readme.md file.

- The blockers summary derives from weak domains (YELLOW, RED, GRAY).
- Purpose: Convert weaknesses into 3-5 actionable blockers with acceptance tests and artifacts.
- Helps prioritize fixes: Each blocker has verifiable tests, required artifacts, owner, and ROM estimate.
- Provides execution clarity: Bundles risks into crisp, testable items for Fix Packs.

IDEA: Acceptance tests are too soft. eg
B4 (DPIA): include threat model, data flows, access controls, and red-team results. Evidence: DPIA_v1.pdf.

PROMPT> python -u -m planexe.viability.blockers | tee output.txt
"""
import os
import json
import time
import logging
from math import ceil
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from llama_index.core.llms.llm import LLM
from pydantic import BaseModel, Field
from llama_index.core.llms import ChatMessage, MessageRole
from planexe.markdown_util.escape_markdown import escape_markdown
from planexe.markdown_util.fix_bullet_lists import fix_bullet_lists
from planexe.viability.model_domain import DomainEnum
from planexe.viability.model_status import StatusEnum
from planexe.viability.taxonomy import TX

logger = logging.getLogger(__name__)

class Blocker(BaseModel):
    id: str = Field(description="Unique ID like 'B1', 'B2', etc.")
    domain: str = Field(description="The domain name from DomainEnum.")
    title: str = Field(description="A concise, descriptive title for the blocker.")
    reason_codes: Optional[List[str]] = Field(default_factory=list, description="Subset of reason codes from the domain's issues.")
    acceptance_tests: Optional[List[str]] = Field(default_factory=list, description="1-3 verifiable acceptance tests (e.g., '>=10% contingency approved').")
    artifacts_required: Optional[List[str]] = Field(default_factory=list, description="Required artifacts/deliverables (e.g., 'Budget_v2.pdf').")
    owner: Optional[str] = Field(default=None, description="Responsible role or team (e.g., 'PMO').")
    rom: Optional[Dict[str, Any]] = Field(default=None, description="ROM estimate: {'cost_band': 'LOW|MEDIUM|HIGH', 'eta_days': int}.")

class BlockersOutput(BaseModel):
    source_domains: List[str] = Field(description=f"Array of domain names that are {StatusEnum.YELLOW.value}, {StatusEnum.RED.value}, or {StatusEnum.GRAY.value}.")
    blockers: List[Blocker] = Field(description="3-5 blockers derived from source_domains.")

DOMAIN_ENUM = DomainEnum.value_list()
REASON_CODE_ENUM = [
    # Budget/Finance
    "CONTINGENCY_LOW", "SINGLE_CUSTOMER", "ALT_COST_UNKNOWN",
    # Rights/Compliance
    "DPIA_GAPS", "LICENSE_GAPS", "ABS_UNDEFINED", "PERMIT_COMPLEXITY",
    # Tech/Integration
    "LEGACY_IT", "INTEGRATION_RISK",
    # People/Adoption
    "TALENT_UNKNOWN", "STAFF_AVERSION",
    # Climate/Ecology
    "CLOUD_CARBON_UNKNOWN", "CLIMATE_UNQUANTIFIED", "WATER_STRESS",
    # Biosecurity
    "BIOSECURITY_GAPS",
    # Governance/Ethics
    "ETHICS_VAGUE"
]
COST_BAND_ENUM = ["LOW", "MEDIUM", "HIGH"]

BLOCKERS_SYSTEM_PROMPT = f"""
You are an expert risk assessor specializing in deriving actionable blockers from domain assessments in viability plans. Your task is to generate a complete blockers output as a valid JSON object that strictly adheres to the schema below. Do not include any extra text, markdown formatting, or additional keys.

The JSON object must include exactly the following keys:

{{
  "source_domains": ["HumanStability", "EconomicResilience"],  // Array of domain names from DomainEnum that have status YELLOW, RED, or GRAY
  "blockers": [  // Array of 3-5 Blocker objects, only from source_domains
    {{
      "id": "B1",
      "domain": "EconomicResilience",
      "title": "Contingency too low",
      "reason_codes": ["CONTINGENCY_LOW"],
      "acceptance_tests": [">=10% contingency approved", "Monte Carlo risk workbook attached"],
      "artifacts_required": ["Budget_v2.pdf", "Risk_MC.xlsx"],
      "owner": "PMO",
      "rom": {{"cost_band": "LOW", "eta_days": 14}}
    }}
  ]
}}

Instructions:
- source_domains: List only domains from the input assessment where status is {StatusEnum.YELLOW.value}, {StatusEnum.RED.value}, or {StatusEnum.GRAY.value}. Use exact names from DomainEnum: {', '.join(DOMAIN_ENUM)}.
- blockers: Derive 3-5 blockers total (cap at 5) only from source_domains. Distribute across domains logically. For each:
  - id: Sequential like "B1", "B2", etc.
  - domain: Match one from source_domains.
  - title: Concise and descriptive (e.g., "Contingency too low").
  - reason_codes: Subset of 1-2 codes from the domain's 'Issues' in the input. Use from REASON_CODE_ENUM if possible: {', '.join(REASON_CODE_ENUM)}; otherwise, use input terms.
  - acceptance_tests: 1-3 short, verifiable tests (e.g., ">=80% support in survey").
  - artifacts_required: 1-3 specific deliverables/files (e.g., "Plan_v1.pdf").
  - owner: A role/team (e.g., "PMO", "Engineering Lead").
  - rom: Always include {{"cost_band": one of {', '.join(COST_BAND_ENUM)}, "eta_days": realistic number like 14}}.
- Derivation: Base blockers on the domain's status, score, Issues, and Evidence Needed. Focus on turning weaknesses into testable fixes.
- Guardrails: No blockers from GREEN domains. Keep total <=5. Use professional, concise language.

Output Requirements:
- Your entire response must be a valid JSON object conforming exactly to the schema above.
- Do not include any extra text or formatting outside the JSON structure.

Remember: Your output must be valid JSON and nothing else.
"""

@dataclass
class ViabilityBlockers:
    system_prompt: Optional[str]
    user_prompt: str
    response: Dict[str, Any]
    markdown: str
    metadata: Dict[str, Any]

    @classmethod
    def execute(cls, llm: LLM, user_prompt: str) -> 'ViabilityBlockers':
        """
        Invoke LLM with domains assessment text to derive blockers.
        """
        if not isinstance(llm, LLM):
            raise ValueError("Invalid LLM instance.")
        if not isinstance(user_prompt, str):
            raise ValueError("Invalid user_prompt.")
        
        system_prompt = BLOCKERS_SYSTEM_PROMPT.strip()
        chat_message_list = [
            ChatMessage(
                role=MessageRole.SYSTEM,
                content=system_prompt,
            ),
            ChatMessage(
                role=MessageRole.USER,
                content=user_prompt,
            )
        ]

        sllm = llm.as_structured_llm(BlockersOutput)
        start_time = time.perf_counter()
        try:
            chat_response = sllm.chat(chat_message_list)
        except Exception as e:
            logger.debug(f"LLM chat interaction failed: {e}")
            logger.error("LLM chat interaction failed.", exc_info=True)
            raise ValueError("LLM chat interaction failed.") from e

        end_time = time.perf_counter()
        duration = int(ceil(end_time - start_time))
        response_byte_count = len(chat_response.message.content.encode('utf-8'))
        logger.info(f"LLM chat interaction completed in {duration} seconds. Response byte count: {response_byte_count}")

        json_response = chat_response.raw.model_dump()

        metadata = dict(llm.metadata)
        metadata["llm_classname"] = llm.class_name()
        metadata["duration"] = duration
        metadata["response_byte_count"] = response_byte_count

        markdown = cls.convert_to_markdown(chat_response.raw)

        result = ViabilityBlockers(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response=json_response,
            markdown=markdown,
            metadata=metadata,
        )
        logger.debug("Blockers instance created successfully.")
        return result    

    def to_dict(self, include_metadata=True, include_system_prompt=True, include_user_prompt=True) -> Dict[str, Any]:
        d = self.response.copy()
        d['markdown'] = self.markdown
        if include_metadata:
            d['metadata'] = self.metadata
        if include_system_prompt:
            d['system_prompt'] = self.system_prompt
        if include_user_prompt:
            d['user_prompt'] = self.user_prompt
        return d

    def save_raw(self, file_path: str) -> None:
        with open(file_path, 'w') as f:
            f.write(json.dumps(self.to_dict(), indent=2))

    @staticmethod
    def convert_to_markdown(blockers_output: BlockersOutput) -> str:
        """
        Convert the raw blockers output to markdown.
        """
        rows = []
        rows.append('<p class="section-subtitle">Actions that must be completed before proceeding.</p>')
        for blocker in blockers_output.blockers:
            rows.append(f"### {blocker.id}: {blocker.title}\n")
            human_readable_domain: str = DomainEnum.get_display_name(blocker.domain)
            rows.append(f"**Domain:** {human_readable_domain}\n")
            if blocker.reason_codes:
                rows.append("**Issues:**\n")
                for reason_code in blocker.reason_codes:
                    human_readable = TX.translate_reason_code_to_human_readable(reason_code)
                    rows.append(f"- <code>{reason_code}</code>: {human_readable}")
            if blocker.acceptance_tests:
                rows.append("\n**Acceptance Criteria:**\n")
                for test in blocker.acceptance_tests:
                    rows.append(f"- {escape_markdown(test)}")
            if blocker.artifacts_required:
                rows.append("\n**Artifacts Required:**\n")
                for artifact in blocker.artifacts_required:
                    rows.append(f"- {escape_markdown(artifact)}")
            if blocker.owner:
                rows.append(f"\n**Owner:** {blocker.owner}\n")
            if blocker.rom:
                rows.append(f"\n**Rough Order of Magnitude (ROM):** {blocker.rom['cost_band']} cost, {blocker.rom['eta_days']} days\n")
            rows.append("")
        markdown = "\n".join(rows)
        markdown = fix_bullet_lists(markdown)
        return markdown

    def save_markdown(self, output_file_path: str):
        with open(output_file_path, 'w', encoding='utf-8') as out_f:
            out_f.write(self.markdown)
    
if __name__ == "__main__":
    from planexe.llm_factory import get_llm

    # Extracted Domains Assessment from report
    domains_text = """
<div class="domains-grid">
  <!-- Green Domain Card -->
  <div class="domain-card domain-card--green domain-card--count-zero" role="status" aria-labelledby="domains-green-title">
    <div class="domain-card__header">
      <div class="domain-card__left">
        <span class="domain-card__icon" aria-hidden="true">✔</span>
        <span id="domains-green-title" class="domain-card__status-name">GREEN</span>
      </div>
      <span class="domain-card__count">0 domains</span>
    </div>
    <div class="domain-card__body">
      <p>Good to go. You have solid evidence and no open critical unknowns. Proceed. Any remaining tasks are minor polish.</p>
    </div>
  </div>

  <!-- Yellow Domain Card -->
  <div class="domain-card domain-card--yellow " role="status" aria-labelledby="domains-yellow-title">
    <div class="domain-card__header">
      <div class="domain-card__left">
        <span class="domain-card__icon" aria-hidden="true">!</span>
        <span id="domains-yellow-title" class="domain-card__status-name">YELLOW</span>
      </div>
      <span class="domain-card__count">2 domains</span>
    </div>
    <div class="domain-card__body">
      <p>Conditionally ready; key risks/unknowns remain. There is promise, but is missing proof on key points or has non-fatal risks. Proceed with caution and a focused checklist.</p>
    </div>
  </div>

  <!-- Red Domain Card -->
  <div class="domain-card domain-card--red " role="status" aria-labelledby="domains-red-title">
    <div class="domain-card__header">
      <div class="domain-card__left">
        <span class="domain-card__icon" aria-hidden="true">✖</span>
        <span id="domains-red-title" class="domain-card__status-name">RED</span>
      </div>
      <span class="domain-card__count">2 domains</span>
    </div>
    <div class="domain-card__body">
      <p>Not ready; fix blockers before proceeding. A concrete blocker or negative evidence exists (legal, technical, economic) that stops execution until fixed. Pause or pivot.</p>
    </div>
  </div>

  <!-- Gray Domain Card -->
  <div class="domain-card domain-card--gray domain-card--count-zero" role="status" aria-labelledby="domains-gray-title">
    <div class="domain-card__header">
      <div class="domain-card__left">
        <span class="domain-card__icon" aria-hidden="true">?</span>
        <span id="domains-gray-title" class="domain-card__status-name">GRAY</span>
      </div>
      <span class="domain-card__count">0 domains</span>
    </div>
    <div class="domain-card__body">
      <p>Unknown / unassessed. Insufficient information to judge. Do not guess—initiate a “first measurement” task to resolve uncertainty.</p>
    </div>
  </div>
</div>




### Legend: How to Read the Scores

Each domain’s health is scored on a 1–5 scale across three key metrics. Higher scores are better.

| Metric | Strong Negative (1) | Weak Negative (2) | Neutral (3) | Weak Positive (4) | Strong Positive (5) |
|--------|--------------------|-------------------|-------------|-------------------|---------------------|
| **Evidence** | No/contradictory evidence; claims only | Anecdotes/unstable drafts | Inconclusive; limited data | Internal tests/pilot support | Independent, reproducible validation; monitored |
| **Risk** | Severe exposure; blockers/unknowns | Major exposure; mitigations not in place | Moderate; mitigations planned/in progress | Low residual risk; mitigations in place | Minimal residual risk; contingencies tested |
| **Fit** | Conflicts with constraints/strategy | Low alignment; major trade-offs | Mixed/unclear alignment | Good alignment; minor trade-offs | Strong alignment; directly reinforces strategy |

### Domain: Human Stability

**Status**: RED — driven by risk (stakeholder conflict, staff aversion, governance weak).

**Metrics**: evidence=2, risk=1, fit=2

**Issues:**

- <code>STAKEHOLDER_CONFLICT</code>: Stakeholder conflict resolution framework + escalation matrix
- <code>STAFF_AVERSION</code>: Change readiness survey v1 + incentive/retention plan
- <code>GOVERNANCE_WEAK</code>: RACI + decision log v1 (scope: this plan)

**Evidence Needed:**

- Stakeholder map + skills gap snapshot — acceptance criteria: top 20 stakeholders include influence/interest scores, critical role gaps quantified, and HR lead sign-off captured.
- Business impact analysis v1 (RTO/RPO, critical processes) — acceptance criteria: BIA lists critical processes with RTO/RPO targets, impact scoring completed, and continuity manager sign-off logged.


### Domain: Economic Resilience

**Status**: YELLOW — driven by evidence (unit econ).

**Metrics**: evidence=2, risk=3, fit=3

**Issues:**

- <code>CONTINGENCY_LOW</code>: Budget v2 with ≥10% contingency + Monte Carlo risk workbook
- <code>UNIT_ECON_UNKNOWN</code>: Unit economics model v1 + sensitivity table (key drivers)

**Evidence Needed:**

- Assumption ledger v1 + sensitivity table — acceptance criteria: ledger lists top 10 assumptions with owners and rationale, sensitivity table shows +/-20% scenario impact, and file stored in shared workspace.
- Unit economics model v1 + sensitivity table (key drivers) — acceptance criteria: model includes CAC, LTV, gross margin, sensitivity table covers +/-20% price and COGS, and CFO sign-off attached.


### Domain: Ecological Integrity

**Status**: RED — driven by risk (biodiversity risk, climate unquantified).

**Metrics**: evidence=1, risk=2, fit=2

**Issues:**

- <code>BIODIVERSITY_RISK_UNSET</code>: Biodiversity screening memo (species/habitat, mitigation)
- <code>WASTE_MANAGEMENT_GAPS</code>: Waste management plan v1 (types, handling, compliance)
- <code>CLIMATE_UNQUANTIFIED</code>: Climate exposure maps (2030/2040/2050) + site vulnerability memo

**Evidence Needed:**

- Environmental baseline note (scope, metrics) — acceptance criteria: scope, metrics, measurement methods, and data sources detailed with sustainability lead sign-off.
- EIA_MISSING — acceptance criteria: artifact is published to the workspace with an owner, acceptance evidence, and review date recorded.


### Domain: Rights & Legality

**Status**: YELLOW — driven by fit (ethics vague).

**Metrics**: evidence=3, risk=3, fit=2

**Issues:**

- <code>ETHICS_VAGUE</code>: Normative Charter v1.0 with auditable rules & dissent logging

**Evidence Needed:**

- Regulatory mapping v1 + open questions list — acceptance criteria: applicable regulations by jurisdiction linked to control owners, open questions assigned with due dates, and compliance counsel acknowledged.
- DPIA_GAPS — acceptance criteria: artifact is published to the workspace with an owner, acceptance evidence, and review date recorded.
    """

    model_name = "ollama-llama3.1"
    llm = get_llm(model_name)

    query = domains_text
    print(f"Query: {query}")
    result = ViabilityBlockers.execute(llm, query)

    print("\nResponse:")
    json_response = result.to_dict(include_system_prompt=False, include_user_prompt=False)
    print(json.dumps(json_response, indent=2))

    print(f"\n\nMarkdown:\n{result.markdown}")
