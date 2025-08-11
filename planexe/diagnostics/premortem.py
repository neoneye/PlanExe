"""
Imagine that the project has failed, and work backwards to identify plausible reasons why.

https://en.wikipedia.org/wiki/Pre-mortem
Premortem is a risk assessment method by Gary A. Klein
https://en.wikipedia.org/wiki/Gary_A._Klein

PROMPT> python -m planexe.diagnostics.premortem

`assumptions_to_kill` are the INPUTS. They are the foundational beliefs held before the project begins. They represent the project's 
most significant areas of uncertainty. The list of assumptions is, in itself, a high-value deliverable for a project kickoff. 
It's the "here's what we believe to be true, but we need to prove it" list.

`failure_modes` are the potential OUTCOMES. They are the narrative stories of what could happen if an assumption proves false. 
They explore the consequences and the causal chain of failure.
"""
import json
import time
import logging
from math import ceil
from dataclasses import dataclass
from typing import Optional, List
from pydantic import BaseModel, Field
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.llms.llm import LLM

logger = logging.getLogger(__name__)

class AssumptionItem(BaseModel):
    assumption_id: str = Field(description="A unique ID for the assumption, enumerated as 'A1', 'A2', 'A3'.")
    statement: str = Field(description="The core assumption we are making that, if false, would kill the project.")
    test_now: str = Field(description="A concrete, immediate action to test if this assumption is true.")
    falsifier: str = Field(description="The specific result from the test that would prove the assumption false.")

class FailureModeItem(BaseModel):
    failure_mode_index: int = Field(description="Enumerate the failure_mode items starting from 1")
    root_cause_assumption_id: str = Field(description="The 'assumption_id' (e.g., 'A1') of the single assumption that is the primary root cause of this failure mode.")
    failure_mode_archetype: str = Field(description="The archetype of failure: 'Process/Financial', 'Technical/Logistical', or 'Market/Human'.")
    failure_mode_title: str = Field(description="A compelling, story-like title (e.g., 'The Gridlock Gamble').")
    risk_analysis: str = Field(
        description="Structured, factual breakdown of causes, contributing factors, and impacts for the failure mode. Use bullet points or short factual sentences. Avoid narratives or fictional elements."
    )
    early_warning_signs: List[str] = Field(
        description="Clear, measurable indicators that this failure mode may occur. Each must be objectively testable."
    )
    owner: Optional[str] = Field(None, description="The single role who owns this risk (e.g., 'Permitting Lead', 'Head of Engineering').")
    likelihood_5: Optional[int] = Field(None, description="Integer from 1 (rare) to 5 (almost certain) of this failure occurring.")
    impact_5: Optional[int] = Field(None, description="Integer from 1 (minor) to 5 (catastrophic) if this failure occurs.")
    tripwires: Optional[List[str]] = Field(None, description="Array of 2-3 short, specific strings with NUMERIC thresholds that signal this failure is imminent (e.g., 'Permit delays exceed 90 days').")
    playbook: Optional[List[str]] = Field(None, description="Array of exactly 3 brief, imperative action steps for the owner to take if a tripwire is hit.")
    stop_rule: Optional[str] = Field(None, description="A single, short, hard stop condition that would trigger project cancellation or a major pivot.")

class PremortemAnalysis(BaseModel):
    assumptions_to_kill: List[AssumptionItem] = Field(description="A list of 3 critical, underlying assumptions to test immediately.")
    failure_modes: List[FailureModeItem] = Field(description="A list containing exactly 3 distinct failure failure_modes, one for each archetype.")

PREMORTEM_SYSTEM_PROMPT = """
Persona: You are a senior project analyst. Your primary goal is to write compelling, detailed, and distinct failure stories that are also operationally actionable.

Objective: Imagine the user's project has failed completely. Generate a comprehensive premortem analysis as a single JSON object.

Instructions:
1.  Generate a top-level `assumptions_to_kill` array containing exactly 3 critical assumptions to test, each with an `id`, `statement`, `test_now`, and `falsifier`. An assumption is a belief held without proof (e.g., "The supply chain is stable"), not a project goal.
2.  Generate a top-level `failure_modes` array containing exactly 3 detailed, story-like failure failure_modes, one for each archetype: Process/Financial, Technical/Logistical, and Market/Human.
3.  **CRITICAL LINKING STEP: For each `failure_mode`, you MUST identify its root cause by setting the `root_cause_assumption_id` field to the `assumption_id` of one of the assumptions you created in step 1.** Each assumption ("A1", "A2", "A3") must be used as a root cause exactly once.
4.  Each story in the `failure_modes` array must be a detailed, multi-paragraph story with a clear causal chain. Do not write short summaries.
5.  For each of the 3 failure_modes, you MUST populate all the following fields: `failure_mode_index`, `failure_mode_archetype`, `failure_mode_title`, `risk_analysis`, `early_warning_signs`, `owner`, `likelihood_5`, `impact_5`, `tripwires`, `playbook`, and `stop_rule`.
6.  **CRITICAL:** Each of the 3 failure_modes must be distinct and unique. Do not repeat the same story, phrasing, or playbook actions. Tailor each one specifically to its archetype (e.g., the financial failure should be about money and process, the technical failure about engineering and materials, the market failure about public perception and competition).
7.  Tripwires MUST be objectively measurable (use operators like <=, >=, =, %, days, counts); avoid vague terms like “significant” or “many”.
8.  The `playbook` array MUST contain exactly 3 actions as follows:
    1.  An immediate containment/control action, e.g., 'Contain: Stop the bleeding.'
    2.  An assessment/triage action, e.g., 'Assess: Figure out how bad the damage is.'
    3.  A strategic response action, e.g., 'Respond: Take strategic action based on the assessment.'
9.  The `stop_rule` MUST be a hard, non-negotiable condition for project cancellation or a major pivot.
10.  Your entire output must be a single, valid JSON object. Do not add any text or explanation outside of the JSON structure.
"""

@dataclass
class Premortem:
    system_prompt: str
    user_prompt: str
    response: dict
    metadata: dict
    markdown: str
    
    @classmethod
    def execute(cls, llm: LLM, user_prompt: str) -> 'Premortem':
        if not isinstance(llm, LLM):
            raise ValueError("Invalid LLM instance.")
        if not isinstance(user_prompt, str):
            raise ValueError("Invalid user_prompt.")
        
        logger.debug(f"User Prompt:\n{user_prompt}")
        system_prompt = PREMORTEM_SYSTEM_PROMPT.strip()

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

        sllm = llm.as_structured_llm(PremortemAnalysis)
        start_time = time.perf_counter()
        
        try:
            chat_response = sllm.chat(chat_message_list)
            pydantic_response = chat_response.raw 
        except Exception as e:
            logger.debug(f"LLM chat interaction failed: {e}")
            logger.error("LLM chat interaction failed.", exc_info=True)
            raise ValueError("LLM chat interaction failed.") from e

        end_time = time.perf_counter()
        
        duration = int(ceil(end_time - start_time))
        json_response = pydantic_response.model_dump()
        response_byte_count = len(json.dumps(json_response).encode('utf-8'))
        
        logger.info(f"LLM chat interaction completed in {duration} seconds. Response byte count: {response_byte_count}")
        
        metadata = dict(llm.metadata)
        metadata["llm_classname"] = llm.class_name()
        metadata["duration"] = duration
        metadata["response_byte_count"] = response_byte_count

        markdown = cls.convert_to_markdown(pydantic_response)

        return Premortem(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response=json_response,
            metadata=metadata,
            markdown=markdown
        )
    
    def to_dict(self, include_metadata=True, include_system_prompt=True, include_user_prompt=True, include_markdown=True) -> dict:
        d = self.response.copy()
        if include_metadata:
            d['metadata'] = self.metadata
        if include_system_prompt:
            d['system_prompt'] = self.system_prompt
        if include_user_prompt:
            d['user_prompt'] = self.user_prompt
        if include_markdown:
            d['markdown'] = self.markdown
        return d

    def save_raw(self, file_path: str) -> None:
        with open(file_path, 'w') as f:
            f.write(json.dumps(self.to_dict(), indent=2))

    def save_markdown(self, output_file_path: str):
        """Save the markdown output to a file."""
        with open(output_file_path, 'w', encoding='utf-8') as out_f:
            out_f.write(self.markdown)

    @staticmethod
    def _format_bullet_list(items: list[str]) -> str:
        """
        Format a list of strings into a markdown bullet list.
        
        Args:
            items: List of strings to format as bullet points
            
        Returns:
            Formatted markdown bullet list
        """
        return "\n".join(f"- {item}" for item in items)

    @staticmethod
    def _calculate_risk_level_brief(likelihood: Optional[int], impact: Optional[int]) -> str:
        """Calculates a qualitative risk level from likelihood and impact scores."""
        if likelihood is None or impact is None:
            return "Not Scored"
        
        score = likelihood * impact
        if score >= 15:
            classification = "CRITICAL"
        elif score >= 9:
            classification = "HIGH"
        elif score >= 4:
            classification = "MEDIUM"
        else:
            classification = "LOW"
        
        return f"{classification} ({score}/25)"

    @staticmethod
    def _calculate_risk_level_verbose(likelihood: Optional[int], impact: Optional[int]) -> str:
        """Calculates a qualitative risk level from likelihood and impact scores."""
        if likelihood is None or impact is None:
            return f"Likelihood {likelihood}/5, Impact {impact}/5"
        
        score = likelihood * impact
        if score >= 15:
            classification = "CRITICAL"
        elif score >= 9:
            classification = "HIGH"
        elif score >= 4:
            classification = "MEDIUM"
        else:
            classification = "LOW"
        
        return f"{classification} {score}/25 (Likelihood {likelihood}/5 × Impact {impact}/5)"

    @staticmethod
    def convert_to_markdown(premortem_analysis: PremortemAnalysis) -> str:
        """
        Convert the premortem analysis to markdown format.
        """
        rows = []
        
        # Header
        rows.append("A premortem assumes the project has failed and works backward to identify the most likely causes.\n")

        # Assumptions to Kill
        rows.append("## Assumptions to Kill\n")
        rows.append("These foundational assumptions represent the project's key uncertainties. If proven false, they could lead to failure. Validate them immediately using the specified methods.\n")

        rows.append("| ID | Assumption | Validation Method | Failure Trigger |")
        rows.append("|----|------------|-------------------|-----------------|")
        for assumption in premortem_analysis.assumptions_to_kill:
            rows.append(f"| {assumption.assumption_id} | {assumption.statement} | {assumption.test_now} | {assumption.falsifier} |")
        rows.append("\n")
        
        # Failure Modes
        rows.append("## Failure Scenarios and Mitigation Plans\n")
        rows.append("Each scenario below links to a root-cause assumption and includes a detailed failure story, early warning signs, measurable tripwires, a response playbook, and a stop rule to guide decision-making.\n")
        
        # Summary Table for Failure Modes
        rows.append("### Summary of Failure Modes\n")
        rows.append("| ID | Title | Archetype | Root Cause | Owner | Risk Level |")
        rows.append("|----|-------|-----------|------------|-------|------------|")
        for index, failure_mode in enumerate(premortem_analysis.failure_modes, start=1):
            risk_level_str = Premortem._calculate_risk_level_brief(failure_mode.likelihood_5, failure_mode.impact_5)
            owner_str = failure_mode.owner or 'Unassigned'
            rows.append(f"| {index} | {failure_mode.failure_mode_title} | {failure_mode.failure_mode_archetype} | {failure_mode.root_cause_assumption_id} | {owner_str} | {risk_level_str} |")
        rows.append("\n")

        # Detailed Failure Modes
        rows.append("### Detailed Failure Scenarios\n")
        for index, failure_mode in enumerate(premortem_analysis.failure_modes, start=1):
            if index > 1:
                rows.append("---\n")
            rows.append(f"#### {index}. {failure_mode.failure_mode_title}\n")
            rows.append(f"- **Archetype**: {failure_mode.failure_mode_archetype}")
            rows.append(f"- **Root Cause**: Assumption {failure_mode.root_cause_assumption_id}")
            rows.append(f"- **Owner**: {failure_mode.owner or 'Unassigned'}")
            risk_level_str = Premortem._calculate_risk_level_verbose(failure_mode.likelihood_5, failure_mode.impact_5)
            rows.append(f"- **Risk Level:** {risk_level_str}\n")
            
            rows.append("##### Failure Story")
            rows.append(f"{failure_mode.risk_analysis}\n")
            
            rows.append("##### Early Warning Signs")
            rows.append(Premortem._format_bullet_list(failure_mode.early_warning_signs))
            
            rows.append("\n##### Tripwires")
            rows.append(Premortem._format_bullet_list(failure_mode.tripwires or ["No tripwires defined"]))
            
            rows.append("\n##### Response Playbook")
            rows.append(Premortem._format_bullet_list(failure_mode.playbook or ["No response actions defined"]))
            rows.append("\n")

            stop_rule_text = failure_mode.stop_rule or 'Not specified'
            rows.append(f"**STOP RULE:** {stop_rule_text}\n")

        return "\n".join(rows)
    
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    from planexe.llm_factory import get_llm
    from planexe.plan.find_plan_prompt import find_plan_prompt

    llm = get_llm("ollama-llama3.1")
    # llm = get_llm("openrouter-paid-openai-gpt-oss-20b")
    # prompt_id = "4dc34d55-0d0d-4e9d-92f4-23765f49dd29"
    prompt_id = "ab700769-c3ba-4f8a-913d-8589fea4624e"
    plan_prompt = find_plan_prompt(prompt_id)

    print(f"Query:\n{plan_prompt}\n\n")
    result = Premortem.execute(llm, plan_prompt)
    
    response_data = result.to_dict(include_metadata=True, include_system_prompt=False, include_user_prompt=False, include_markdown=False)
    
    print("\n\nResponse:")
    print(json.dumps(response_data, indent=2))
    
    print(f"\n\nMarkdown Output:")
    print(result.markdown)
    