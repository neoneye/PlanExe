"""
Imagine that the project has failed, and work backwards to identify plausible reasons why.

https://en.wikipedia.org/wiki/Pre-mortem

PROMPT> python -m planexe.diagnostics.premortem
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

class NarrativeItem(BaseModel):
    narrative_index: int = Field(description="Enumerate the narrative items starting from 1")
    narrative_archetype: str = Field(description="The archetype of failure: 'Process/Financial', 'Technical/Logistical', or 'Market/Human'.")
    narrative_title: str = Field(description="A compelling, story-like title (e.g., 'The Gridlock Gamble').")
    detailed_story_markdown: str = Field(description="A detailed, multi-paragraph story of the failure. Explain the causal chain. Write a full story.")
    early_warning_signs_markdown: str = Field(description="A markdown list of 2-3 specific, observable events or metrics that preceded this failure.")
    owner: Optional[str] = Field(None, description="The single role who owns this risk (e.g., 'Permitting Lead', 'Head of Engineering').")
    likelihood_5: Optional[int] = Field(None, description="Integer from 1 (rare) to 5 (almost certain) of this failure occurring.")
    impact_5: Optional[int] = Field(None, description="Integer from 1 (minor) to 5 (catastrophic) if this failure occurs.")
    tripwires: Optional[List[str]] = Field(None, description="Array of 2-3 short, specific strings with NUMERIC thresholds that signal this failure is imminent (e.g., 'Permit delays exceed 90 days').")
    playbook: Optional[List[str]] = Field(None, description="Array of exactly 3 brief, imperative action steps for the owner to take if a tripwire is hit.")
    stop_rule: Optional[str] = Field(None, description="A single, short, hard stop condition that would trigger project cancellation or a major pivot.")

class Assumption(BaseModel):
    id: str = Field(description="A unique ID for the assumption, e.g., 'A1', 'A2'.")
    statement: str = Field(description="The core assumption we are making that, if false, would kill the project.")
    test_now: str = Field(description="A concrete, immediate action to test if this assumption is true.")
    falsifier: str = Field(description="The specific result from the test that would prove the assumption false.")

class PremortemAnalysis(BaseModel):
    narratives: List[NarrativeItem] = Field(description="A list containing exactly 3 distinct failure narratives, one for each archetype.")
    assumptions_to_kill: Optional[List[Assumption]] = Field(None, description="A list of 3 critical, underlying assumptions to test immediately.")

PREMORTEM_SYSTEM_PROMPT = """
Persona: You are a senior project analyst. Your primary goal is to write compelling, detailed, and distinct failure stories that are also operationally actionable.

Objective: Imagine the user's project has failed completely. Generate a comprehensive premortem analysis as a single JSON object.

Instructions:
1.  Generate a top-level `narratives` array containing exactly 3 detailed, story-like failure narratives, one for each archetype: Process/Financial, Technical/Logistical, and Market/Human.
2.  Each story in the `narratives` array must be a detailed, multi-paragraph story with a clear causal chain. Do not write short summaries.
3.  For each of the 3 narratives, you MUST populate all the following fields: `narrative_index`, `narrative_archetype`, `narrative_title`, `detailed_story_markdown`, `early_warning_signs_markdown`, `owner`, `likelihood_5`, `impact_5`, `tripwires`, `playbook`, and `stop_rule`.
4.  Generate a top-level `assumptions_to_kill` array containing exactly 3 critical assumptions to test, each with an `id`, `statement`, `test_now`, and `falsifier`.
5.  **CRITICAL:** Each of the 3 narratives must be distinct and unique. Do not repeat the same story, phrasing, or playbook actions. Tailor each one specifically to its archetype (e.g., the financial failure should be about money and process, the technical failure about engineering and materials, the market failure about public perception and competition).
6.  Your entire output must be a single, valid JSON object. Do not add any text or explanation outside of the JSON structure.
"""

@dataclass
class Premortem:
    system_prompt: str
    user_prompt: str
    response: dict
    metadata: dict
    
    @classmethod
    def execute(cls, llm: LLM, user_prompt: str) -> 'Premortem':
        if not isinstance(llm, LLM): raise ValueError("Invalid LLM instance.")
        if not isinstance(user_prompt, str): raise ValueError("Invalid user_prompt.")
        
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

        return Premortem(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response=json_response,
            metadata=metadata
        )
    
    def to_dict(self, include_metadata=True, include_system_prompt=True, include_user_prompt=True) -> dict:
        d = self.response.copy()
        if include_metadata:
            d['metadata'] = self.metadata
        if include_system_prompt:
            d['system_prompt'] = self.system_prompt
        if include_user_prompt:
            d['user_prompt'] = self.user_prompt
        return d
    
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    from planexe.llm_factory import get_llm
    from planexe.plan.find_plan_prompt import find_plan_prompt

    llm = get_llm("ollama-llama3.1")
    plan_prompt = find_plan_prompt("4dc34d55-0d0d-4e9d-92f4-23765f49dd29")

    print(f"Query:\n{plan_prompt}\n\n")
    result = Premortem.execute(llm, plan_prompt)
    
    response_data = result.to_dict(include_metadata=True, include_system_prompt=False, include_user_prompt=False)
    
    print("\n\nResponse:\n")
    print(json.dumps(response_data, indent=2))
    