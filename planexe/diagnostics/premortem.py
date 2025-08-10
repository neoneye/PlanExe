"""
Imagine that the project has failed, and work backwards to identify plausible reasons why.

PROMPT> python -m planexe.diagnostics.premortem
"""
import json
import time
import logging
from math import ceil
from dataclasses import dataclass
from pydantic import BaseModel, Field
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.llms.llm import LLM

logger = logging.getLogger(__name__)

class NarrativeItem(BaseModel):
    narrative_index: int = Field(
        description="Enumerate the narrative items starting from 1"
    )
    narrative_archetype: str = Field(
        description="The archetype of failure: 'Process/Financial', 'Technical/Logistical', or 'Market/Human'."
    )
    narrative_title: str = Field(
        description="A compelling, human-readable title for the story (e.g., 'The Gridlock Gamble', 'The Corrosion Cascade')."
    )
    detailed_story_markdown: str = Field(
        description="The detailed story of the failure. Explain the causal chain — how smaller risks combined and escalated. Use markdown formatting and write it as a compelling story, not a dry report."
    )
    early_warning_signs_markdown: str = Field(
        description="A markdown list of specific, observable events or metrics that would have preceded this specific failure."
    )

class PremortemAnalysis(BaseModel):
    narratives: list[NarrativeItem] = Field(
        description="A list containing exactly 3 distinct failure narratives, one for each archetype."
    )

PREMORTEM_SYSTEM_PROMPT = """
Persona: Assume the role of a senior project analyst conducting a high-stakes premortem exercise.

Objective: Generate a “Premortem” section by imagining that the project has completely failed after execution. Your task is to work backward and create compelling, plausible stories explaining why.

Instructions:
1.  Establish a future date (e.g., 18-24 months from now) and state clearly that the project has failed, resulting in significant, specified losses.
2.  You MUST generate 3 distinct failure narratives, one for each of the following archetypes:
    *   **Process/Financial Failure:** Collapse from mismanagement, budget overruns, crippling debt, or bureaucratic gridlock.
    *   **Technical/Logistical Failure:** Failure from a critical design flaw, engineering error, catastrophic supply chain breakdown, or unforeseen environmental interaction.
    *   **Market/Human Failure:** The project is a technical success but a market failure due to rejection, competitor outmaneuvering, negative public perception, or a fundamental misreading of human behavior.
3.  **Write each narrative as a compelling story, not a report summary.** Include specific, fictional-but-plausible details (e.g., names of stakeholders, specific regulations, concrete technical failures, news headlines) to make the narrative feel real and impactful. Explain the causal chain in each story—how small issues cascaded into total failure.
4.  **For each narrative, identify specific, observable early warning signs.** These must be concrete events or metrics (e.g., "a key engineer's sudden resignation," "a 15% drop in positive social media sentiment," "a competitor's surprise patent filing"), not generic advice ("poor communication").
"""

@dataclass
class Premortem:
    """
    Imagine that the project has failed, and work backwards to identify plausible reasons why.
    """
    system_prompt: str
    user_prompt: str
    response: dict
    metadata: dict

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
        except Exception as e:
            logger.debug(f"LLM chat interaction failed: {e}")
            logger.error("LLM chat interaction failed.", exc_info=True)
            raise ValueError("LLM chat interaction failed.") from e

        end_time = time.perf_counter()
        duration = int(ceil(end_time - start_time))
        
        pydantic_response = chat_response
        json_response = pydantic_response.model_dump()
        response_byte_count = len(json.dumps(json_response).encode('utf-8'))

        logger.info(f"LLM chat interaction completed in {duration} seconds. Response byte count: {response_byte_count}")

        metadata = dict(llm.metadata)
        metadata["llm_classname"] = llm.class_name()
        metadata["duration"] = duration
        metadata["response_byte_count"] = response_byte_count

        result = Premortem(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response=json_response,
            metadata=metadata,
        )
        return result
    
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
    from planexe.llm_factory import get_llm
    from planexe.plan.find_plan_prompt import find_plan_prompt

    llm = get_llm("ollama-llama3.1")
    plan_prompt = find_plan_prompt("4dc34d55-0d0d-4e9d-92f4-23765f49dd29")

    print(f"Query:\n{plan_prompt}\n\n")
    result = Premortem.execute(llm, plan_prompt)
    
    json_response = result.to_dict(include_metadata=False, include_system_prompt=False, include_user_prompt=False)

    print("\n\n--- PREMORTEM ANALYSIS ---\n")
    if 'narratives' in json_response:
        for narrative in json_response['narratives']:
            print(f"## {narrative.get('narrative_index')}. {narrative.get('narrative_title')} ({narrative.get('narrative_archetype')})")
            print("\n### The Story of Failure\n")
            print(narrative.get('detailed_story_markdown'))
            print("\n### Early Warning Signs\n")
            print(narrative.get('early_warning_signs_markdown'))
            print("\n" + "="*80 + "\n")
    else:
        # Fallback for old format or errors
        print(json.dumps(json_response, indent=2))