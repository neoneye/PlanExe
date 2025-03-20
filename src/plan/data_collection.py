"""
Identify what data is needed for the plan. Such as for validating demand, the plan needs data from audience research or simulations.

For the initial plan, focus on planned simulations that runs automated.
For the 2nd plan, gather real world data from humans.

Data Areas to Cover:
- Market Research and Participant Feedback
- Financial Estimates and Revenue Streams
- Resource and Staffing Needs
- Operational Logistics Simulations
- Regulatory Requirements & Ethical Considerations

PROMPT> python -m src.plan.data_collection
"""
import json
import time
import logging
from math import ceil
from enum import Enum
from dataclasses import dataclass
from pydantic import BaseModel, Field
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.llms.llm import LLM

logger = logging.getLogger(__name__)

class SensitivityScore(str, Enum):
    low = 'low'
    medium = 'medium'
    high = 'high'

    def human_readable(self) -> str:
        return self.value.capitalize()

class PlannedDataCollectionItem(BaseModel):
    item_index: int = Field(
        description="Enumeration, starting from 1."
    )
    title: str = Field(
        description="Brief title, such as 'Venue Cost Estimates', 'Sponsorship & Revenue Streams'."
    )
    data_to_collect: list[str] = Field(
        description="What data to collect"
    )
    simulation_steps: list[str] = Field(
        description="How to simulate the data and what tools to use."
    )
    expert_validation_steps: list[str] = Field(
        description="Human expert validation steps."
    )
    rationale: str = Field(
        description="Explain why this particular data is to be collected."
    )
    sensitivity_score: SensitivityScore = Field(
        description="So it's possible to focus resources on the most impactful areas."
    )
    responsible_parties: list[str] = Field(
        description="Who specifically should be involved or responsible."
    )
    assumptions: list[str] = Field(
        description="What assumptions are made about data, validation, collection, etc."
    )
    notes: list[str] = Field(
        description="Insights and notes."
    )

class DocumentDetails(BaseModel):
    data_collection_list: list[PlannedDataCollectionItem] = Field(
        description="List of data to be collected."
    )
    summary: str = Field(
        description="Providing a high level context."
    )

DATA_COLLECTION_SYSTEM_PROMPT = """
You are an automated project planning assistant generating structured project plans.

Your response must strictly adhere to this structured format:

For each "data collection item", explicitly list:
  - data_to_collect: Specific data points required for informed decisions.
  - simulation_steps: Clearly specify simulation actions involving software, analytical models, or digital tools (e.g., QGIS, ArcGIS, Autodesk Fusion 360, SolidWorks, SAP SCM, Arena Simulation, local databases). Do not include human consultations here.
  - expert_validation_steps: Explicitly state the experts, stakeholders, or authorities to consult to verify and validate the simulated data.
  - rationale: Concisely explain why collecting this data directly impacts project success.
  - assumptions: Clearly state specific assumptions underlying simulation steps.
  - notes: Clearly highlight uncertainties, data gaps, or potential risks.
  - responsible_parties: Suggest specific roles or stakeholders recommended for task execution.
  - sensitivity_score: Assign a "sensitivity score" to each assumption. This score reflects the potential impact on the project's objectives if the assumption proves to be false.

Ensure every "data collection item" explicitly includes BOTH simulation_steps and expert_validation_steps. Simulation_steps must always specify tools or software. Expert_validation_steps must clearly define human experts or authorities for verification. Never leave these steps empty.

Provide a concise and meaningful summary outlining critical next steps and immediately actionable tasks, guiding stakeholders clearly on what must be done next.
"""

@dataclass
class DataCollection:
    """
    Identify what data is needed for the plan.
    """
    system_prompt: str
    user_prompt: str
    response: dict
    metadata: dict
    markdown: str

    @classmethod
    def execute(cls, llm: LLM, user_prompt: str) -> 'DataCollection':
        """
        Invoke LLM with the project details.
        """
        if not isinstance(llm, LLM):
            raise ValueError("Invalid LLM instance.")
        if not isinstance(user_prompt, str):
            raise ValueError("Invalid user_prompt.")

        logger.debug(f"User Prompt:\n{user_prompt}")

        system_prompt = DATA_COLLECTION_SYSTEM_PROMPT.strip()

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

        markdown = cls.convert_to_markdown(chat_response.raw)

        result = DataCollection(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response=json_response,
            metadata=metadata,
            markdown=markdown
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
    def convert_to_markdown(document_details: DocumentDetails) -> str:
        """
        Convert the raw document details to markdown.
        """
        rows = []

        for item_index, data_collection_item in enumerate(document_details.data_collection_list, start=1):
            if item_index > 1:
                rows.append("\n")
            rows.append(f"## Item {item_index} - {data_collection_item.title}\n")
            rows.append(data_collection_item.rationale)

            rows.append(f"\n**Sensitivity:** {data_collection_item.sensitivity_score.human_readable()}")

            data_to_collect = DataCollection._format_bullet_list(data_collection_item.data_to_collect)
            rows.append(f"\n### Data to Collect\n\n{data_to_collect}")

            simulation_steps = DataCollection._format_bullet_list(data_collection_item.simulation_steps)
            rows.append(f"\n### Simulation Steps\n\n{simulation_steps}")

            expert_validation_steps = DataCollection._format_bullet_list(data_collection_item.expert_validation_steps)
            rows.append(f"\n### Expert Validation Steps\n\n{expert_validation_steps}")

            responsible_parties = DataCollection._format_bullet_list(data_collection_item.responsible_parties)
            rows.append(f"\n### Responsible Parties\n\n{responsible_parties}")

            assumptions = DataCollection._format_bullet_list(data_collection_item.assumptions)
            rows.append(f"\n### Assumptions\n\n{assumptions}")

            notes = DataCollection._format_bullet_list(data_collection_item.notes)
            rows.append(f"\n### Notes\n\n{notes}")

        rows.append(f"\n## Summary\n\n{document_details.summary}")
        return "\n".join(rows)

    def save_markdown(self, output_file_path: str):
        with open(output_file_path, 'w', encoding='utf-8') as out_f:
            out_f.write(self.markdown)

if __name__ == "__main__":
    from src.llm_factory import get_llm
    from src.plan.find_plan_prompt import find_plan_prompt

    llm = get_llm("ollama-llama3.1")

    plan_prompt = find_plan_prompt("de626417-4871-4acc-899d-2c41fd148807")
    query = (
        f"{plan_prompt}\n\n"
        "Today's date:\n2025-Feb-27\n\n"
        "Project start ASAP"
    )
    print(f"Query: {query}")

    result = DataCollection.execute(llm, query)
    json_response = result.to_dict(include_system_prompt=False, include_user_prompt=False)
    print("\n\nResponse:")
    print(json.dumps(json_response, indent=2))

    print(f"\n\nMarkdown:\n{result.markdown}")
