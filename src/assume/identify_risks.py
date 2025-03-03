"""
Identify risks in the project plan.

PROMPT> python -m src.assume.identify_risks
"""
import os
import json
import time
import logging
from math import ceil
from dataclasses import dataclass
from pydantic import BaseModel, Field
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.llms.llm import LLM
from src.format_json_for_use_in_query import format_json_for_use_in_query

logger = logging.getLogger(__name__)

class RiskItem(BaseModel):
    risk_area: str = Field(
        description="The category or domain of the risk, e.g., Regulatory, Financial, Technical."
    )
    risk_description: str = Field(
        description="A detailed explanation outlining the specific nature of the risk."
    )
    potential_impact: str = Field(
        description="Possible consequences or adverse effects on the project if the risk materializes."
    )
    likelihood: str = Field(
        description="A qualitative measure (e.g., Low, Medium, High) indicating the probability that the risk will occur."
    )
    severity: str = Field(
        description="A qualitative measure (e.g., Low, Medium, High) describing the extent of the potential negative impact if the risk occurs."
    )
    action: str = Field(
        description="Recommended mitigation strategies or steps to reduce the likelihood or impact of the risk."
    )

class DocumentDetails(BaseModel):
    risks: list[RiskItem] = Field(
        description="A list of identified project risks."
    )
    risk_assessment_summary: str = Field(
        description="Providing a high level context."
    )

IDENTIFY_RISKS_SYSTEM_PROMPT = """
You are a world-class planning expert specializing in the success of projects. Your task is to identify potential risks that are of key importance to create a good plan.

For each potential risk, follow these directions:

1.  **Identify Risks:** Analyze the provided project plan and identify potential risks that are relevant to the project. Consider factors such as regulatory hurdles, technological challenges, financial constraints, environmental concerns, and social impacts. Be thorough and creative in your risk identification.
2.  **Categorize the Risk:** Assign each risk to a relevant category (e.g., "Regulatory & Permitting," "Financial," "Technical," "Environmental," "Social," "Operational," "Supply Chain").
3.  **Describe the Risk:** Provide a detailed explanation of the specific nature of the risk. What could go wrong? Why is it a concern?
4.  **Explain the Potential Impact:** Describe the potential consequences or adverse effects on the project if the risk materializes. Be as specific as possible and quantify the impact whenever feasible, including ranges (e.g., "a delay of 2-4 weeks", "a cost overrun of 5,000-10,000 in the project's local currency"). When providing cost estimates, use the appropriate currency based on the project context.
5.  **Assess Likelihood:** Provide a qualitative assessment of the risk's probability using one of the following categories: "Low," "Medium," or "High."
6.  **Assess Severity:** Provide a qualitative assessment of the risk's potential negative impact using one of the following categories: "Low," "Medium," or "High." Remember that a "Low" likelihood does not necessarily mean "Low" severity.
7.  **Recommend Actionable Mitigation Strategies:** Suggest specific mitigation strategies or steps that can be taken to reduce the likelihood or impact of the risk. These actions should be practical and directly address the identified risk.

After identifying and describing each risk, provide a concise *strategic summary* of the most critical risks that require immediate attention. Do not list each risk again. What are the 2-3 most important factors that, if handled poorly, could jeopardize the project? Highlight any trade-offs or overlapping mitigation opportunities where possible.

**Output Format:**

Your output MUST be a JSON object with the following structure:

{
  "risks": [
    {
      "risk_area": "The category or domain of the risk (e.g., Regulatory)",
      "risk_description": "A detailed explanation outlining the specific nature of the risk.",
      "potential_impact": "Possible consequences or adverse effects on the project if the risk materializes. Quantify the impact whenever feasible.",
      "likelihood": "A qualitative measure (Low, Medium, or High) indicating the probability that the risk will occur.",
      "severity": "A qualitative measure (Low, Medium, or High) describing the extent of the potential negative impact if the risk occurs.",
      "action": "Recommended mitigation strategies or steps to reduce the likelihood or impact of the risk."
    },
    ...
  ],
  "risk_assessment_summary": "A concise summary of the overall risk landscape and the most critical risks."
}
"""

@dataclass
class IdentifyRisks:
    """
    Take a look at the vague plan description and identify risks.
    """
    system_prompt: str
    user_prompt: str
    response: dict
    metadata: dict

    @classmethod
    def execute(cls, llm: LLM, user_prompt: str) -> 'IdentifyRisks':
        """
        Invoke LLM with the project description.
        """
        if not isinstance(llm, LLM):
            raise ValueError("Invalid LLM instance.")
        if not isinstance(user_prompt, str):
            raise ValueError("Invalid user_prompt.")

        logger.debug(f"User Prompt:\n{user_prompt}")

        system_prompt = IDENTIFY_RISKS_SYSTEM_PROMPT.strip()

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

        sllm = llm.as_structured_llm(DocumentDetails)
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

        result = IdentifyRisks(
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

    def save_raw(self, file_path: str) -> None:
        with open(file_path, 'w') as f:
            f.write(json.dumps(self.to_dict(), indent=2))

if __name__ == "__main__":
    from src.llm_factory import get_llm
    from src.plan.find_plan_prompt import find_plan_prompt

    llm = get_llm("ollama-llama3.1")

    plan_prompt = find_plan_prompt("4dc34d55-0d0d-4e9d-92f4-23765f49dd29")
    query = (
        f"{plan_prompt}\n\n"
        "Today's date:\n2025-Feb-27\n\n"
        "Project start ASAP"
    )
    print(f"Query: {query}")

    identify_risks = IdentifyRisks.execute(llm, query)
    json_response = identify_risks.to_dict(include_system_prompt=False, include_user_prompt=False)
    print("\n\nResponse:")
    print(json.dumps(json_response, indent=2))
