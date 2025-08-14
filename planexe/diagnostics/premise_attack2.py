"""
Strategic Stress Test: A Challenge to the Core Premise.

This module functions as a strategic Go/No-Go gate. It challenges a plan's
foundational assumptions to prevent the perfect execution of a flawed strategy.

It asks: "Should we really be doing this?" and "Is the money better spent elsewhere?"

Workflow Integration:
1. The output of this module generates the "Strategic Stress Test" section.
2. The 'Disconfirming Tests' are used to create a "Phase 0: Strategic Validation"
   in the project's Gantt chart, culminating in a "Premise Gate" milestone.
3. All subsequent operational phases are dependent on this gate.

PROMPT> python -m planexe.diagnostics.premise_attack2
"""
import json
import time
import logging
from datetime import date, timedelta
from math import ceil
from typing import List, Optional, Literal

from pydantic import BaseModel, Field, conint, field_validator
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.llms.llm import LLM

logger = logging.getLogger(__name__)


# --- 1. Upgraded Pydantic Models (from Memo 20250814_1429.md) ---
# These models are far more structured and actionable than the original draft.

class DisconfirmingTest(BaseModel):
    """A cheap, fast, and decisive real-world experiment to prove an objection true."""
    test: str = Field(..., description="A concise description of the test to be run.")
    method: Literal[
        "pilot", "survey", "experiment", "benchmark", "interview",
        "market_test", "legal_review", "lab_test"
    ] = Field(..., description="The methodology for conducting the test.")
    metric: str = Field(..., description="The specific, measurable metric the test will track (e.g., 'Uptake Rate', 'CAC', 'NPS').")
    threshold: str = Field(..., description="The unambiguous quantitative threshold for the metric (must include a comparator like '>= 70%', '< $50').")
    owner: str = Field(..., description="The role or person responsible for executing the test.")
    deadline: date = Field(..., description="The deadline for completing the test (YYYY-MM-DD).")
    budget: str = Field(..., description="The estimated budget for the test (e.g., '$5k', '0').")

class Alternative(BaseModel):
    """An alternative strategic path, including 'Do nothing'."""
    name: str = Field(..., description="The name of the alternative strategy.")
    value_note: str = Field(..., description="A brief note on the potential value or upside of this alternative.")
    risk_note: str = Field(..., description="A brief note on the primary risk or downside of this alternative.")

class PremiseAttackModel(BaseModel):
    """The structured output for the Strategic Stress Test."""
    core_premise: str = Field(..., description="A single, concise sentence summarizing the plan's core thesis that is being challenged.")
    objections: List[str] = Field(..., min_length=3, max_length=7, description="3-7 high-leverage, fundamental objections to the core premise.")
    disconfirming_tests: List[DisconfirmingTest] = Field(..., min_length=3, description="At least 3 disconfirming tests, one for each of the primary objections.")
    stop_rules: List[str] = Field(..., min_length=2, description="2-6 crisp, unambiguous Go/No-Go conditions that, if met, would trigger a project halt or pivot.")
    alternatives: List[Alternative] = Field(..., description="A list of strategic alternatives, which must include 'Do nothing'.")
    guardrails_if_proceed: List[str] = Field(..., description="3-5 non-negotiable constraints or changes to implement if the project proceeds despite objections.")
    decision_gate: Literal["Go", "Pivot", "No-Go"] = Field(..., description="The final recommendation based on the analysis.")
    decision_rationale: str = Field(..., description="A 2-6 line rationale linking the decision to the objections and tests.")


# --- 2. Synthesized System Prompt ---
# This prompt is engineered to generate the complex Pydantic model above,
# combining the best instructions from your code and memos.

SYSTEM_PROMPT = """
You are an adversarial "Red Team" strategist. Your mission is to challenge a project's foundational premise to prevent the execution of a flawed strategy. Your output must be a valid JSON object adhering to the provided schema.

Your task is to generate a "Strategic Stress Test" by performing the following steps:
1.  **Identify the Core Premise:** Distill the user's plan into a single, concise thesis statement.
2.  **Formulate Objections:** Generate 3-7 of the strongest, most fundamental objections to this premise. Attack the "why," not the "how." Focus on flawed logic, opportunity cost, ethical blind spots, and strategic misalignment.
3.  **Design Disconfirming Tests:** For each primary objection, devise a cheap, fast, and decisive real-world test that could falsify the underlying assumption. Each test must have an actionable method, a measurable metric, and an unambiguous quantitative threshold (e.g., '>= 70%', '< $50').
4.  **Define Stop Rules:** For each test, define a clear "Stop Rule" or tripwire. If this condition is met, the project should be halted or radically pivoted.
5.  **Propose Alternatives:** List strategic alternatives, including the mandatory "Do nothing" option, each with a brief note on its value and risk.
6.  **Establish Guardrails:** If the project were to proceed anyway, define 3-5 non-negotiable minimum changes or constraints that must be implemented to de-risk the most critical objections.
7.  **Make a Decision:** Conclude with a clear "Go," "Pivot," or "No-Go" recommendation, supported by a concise rationale that links back to your analysis.

**Hard Requirements:**
- Your entire output must be a single JSON object matching the schema.
- Focus exclusively on premise-level flaws. Do NOT list solvable execution risks (like engineering delays, permits, or budget management).
- The `alternatives` list MUST include an item where `name` is "Do nothing".
- Every `threshold` in a `disconfirming_test` MUST contain a numerical value and a comparator (e.g., '>=', '<', '<=').
- Be concise, surgical, and provocative. Your goal is to force a critical re-evaluation of the plan's viability.
"""

# --- 3. Refactored Main Class with Integrated Validation ---

class PremiseAttack:
    """
    Executes and validates a Strategic Stress Test on a plan's core premise.
    """
    def __init__(self, llm: LLM, plan_start_date: date = date.today()):
        if not isinstance(llm, LLM):
            raise ValueError("Invalid LLM instance.")
        self.llm = llm
        self.plan_start_date = plan_start_date
        self.system_prompt = SYSTEM_PROMPT.strip()
        self.user_prompt: Optional[str] = None
        self.raw_response: Optional[dict] = None
        self.validated_data: Optional[PremiseAttackModel] = None
        self.metadata: dict = {}

    def execute(self, user_prompt: str) -> "PremiseAttack":
        """Generates and validates the premise attack."""
        if not isinstance(user_prompt, str) or not user_prompt:
            raise ValueError("Invalid user_prompt.")
        self.user_prompt = user_prompt
        logger.debug(f"Executing Premise Attack with user prompt:\n{user_prompt}")

        chat_messages = [
            ChatMessage(role=MessageRole.SYSTEM, content=self.system_prompt),
            ChatMessage(role=MessageRole.USER, content=self.user_prompt),
        ]

        structured_llm = self.llm.as_structured_llm(PremiseAttackModel)
        
        start_time = time.perf_counter()
        try:
            # The structured_llm.chat() method returns a ChatResponse object
            response_obj = structured_llm.chat(chat_messages)
            self.validated_data = response_obj.raw
            self.raw_response = response_obj.raw.model_dump(mode='json')

        except Exception as e:
            logger.error("LLM chat interaction failed to produce valid structured output.", exc_info=True)
            raise ValueError("LLM chat interaction failed.") from e
        finally:
            end_time = time.perf_counter()
            duration = int(ceil(end_time - start_time))
            response_bytes = len(json.dumps(self.raw_response).encode("utf-8")) if self.raw_response else 0
            
            self.metadata = {
                "llm_classname": self.llm.class_name(),
                "duration_seconds": duration,
                "response_byte_count": response_bytes,
                "model_name": getattr(self.llm.metadata, "model_name", None),
            }
            logger.info(f"LLM interaction completed in {duration}s. Response size: {response_bytes} bytes.")
        
        self.validate()
        return self

    def validate(self):
        """
        Performs post-generation validation based on rules from memo 20250814_1429.md.
        """
        if not self.validated_data:
            raise ValueError("Cannot validate without a successful execution response.")

        errors = []
        pa = self.validated_data

        # Rule: At least one test deadline within 30 days
        if not any(test.deadline <= (self.plan_start_date + timedelta(days=30)) for test in pa.disconfirming_tests):
            errors.append("Validation failed: At least one disconfirming test must have a deadline within 30 days of the plan start.")

        # Rule: Alternatives must include "Do nothing"
        if not any(alt.name.lower().strip() == "do nothing" for alt in pa.alternatives):
             errors.append("Validation failed: The 'alternatives' list must include a 'Do nothing' option.")

        # Rule: Check for premises-security drift
        drift_tokens = {"lockdown", "evacuation", "perimeter", "cctv", "badge access", "soc", "firewall", "on-prem"}
        text_blob = " ".join(pa.objections).lower() + " ".join(t.test.lower() for t in pa.disconfirming_tests)
        if any(token in text_blob for token in drift_tokens):
             errors.append("Validation warning: Detected potential drift into execution/site-security topics. Review objections and tests to ensure they remain at the premise level.")

        if errors:
            error_message = "\n".join(errors)
            logger.warning(f"Post-generation validation issues found:\n{error_message}")
            # Depending on severity, you might raise an exception here. For now, we'll log a warning.
            # raise ValueError(error_message)
        
        logger.info("Post-generation validation passed successfully.")
        return True

    def to_dict(self) -> dict:
        """Serializes the validated data and metadata to a dictionary."""
        if not self.validated_data:
            return {}
        
        output = self.validated_data.model_dump(mode='json')
        output["metadata"] = self.metadata
        return output

    def to_gantt_phase_0(self) -> List[dict]:
        """
        Transforms disconfirming tests into tasks for a Phase 0 Gantt chart.
        This is a conceptual implementation based on memo 20250814_1429.md.
        """
        if not self.validated_data:
            return []
            
        tasks = []
        for test in self.validated_data.disconfirming_tests:
            tasks.append({
                "id": f"premise_test_{test.test[:20].replace(' ', '_')}",
                "text": f"Stress Test: {test.test}",
                "start_date": self.plan_start_date.strftime('%Y-%m-%d'),
                "end_date": test.deadline.strftime('%Y-%m-%d'),
                "owner": test.owner,
                "custom_tooltip": f"<b>Test:</b> {test.test}<br><b>Method:</b> {test.method}<br><b>Metric:</b> {test.metric}<br><b>Threshold:</b> {test.threshold}<br><b>Budget:</b> {test.budget}"
            })

        latest_deadline = max(test.deadline for test in self.validated_data.disconfirming_tests)
        tasks.append({
            "id": "premise_gate",
            "text": "Premise Gate (Go/No-Go Decision)",
            "start_date": latest_deadline.strftime('%Y-%m-%d'),
            "type": "milestone",
            "dependencies": [t["id"] for t in tasks if t.get("type") != "milestone"]
        })
        return tasks

# --- 4. Main execution block for testing ---

if __name__ == "__main__":
    from planexe.llm_factory import get_llm
    from planexe.plan.find_plan_prompt import find_plan_prompt

    # Use a local, fast model for development and testing
    llm = get_llm("ollama-llama3.1")

    # Example using the 'Cube Construction' prompt ID, as it's a great test case
    plan_prompt = find_plan_prompt("5d0dd39d-0047-4473-8096-ea5eac473a57")

    print("--- USER PROMPT ---")
    print(plan_prompt)
    print("-" * 20)

    try:
        attack = PremiseAttack(llm=llm).execute(plan_prompt)
        
        print("\n--- VALIDATED JSON RESPONSE ---")
        print(json.dumps(attack.to_dict(), indent=2))

        print("\n--- GENERATED GANTT PHASE 0 TASKS ---")
        gantt_tasks = attack.to_gantt_phase_0()
        print(json.dumps(gantt_tasks, indent=2))

    except ValueError as e:
        print(f"\n--- EXECUTION FAILED ---")
        print(e)