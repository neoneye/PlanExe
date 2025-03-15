"""
Suggest similar past or existing projects that can be used as a reference for the current project.

PROMPT> python -m src.plan.similar_projects
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

logger = logging.getLogger(__name__)

class SuggestionItem(BaseModel):
    item_index: int = Field(
        description="Enumeration, starting from 1."
    )
    project_name: str = Field(
        description="The name of the project."
    )
    project_description: str = Field(
        description="A description of the project."
    )
    success_metrics: list[str] = Field(
        description="Indicators of success, challenges encountered, and project outcomes."
    )
    risks_and_challenges_faced: list[str] = Field(
        description="Explain how each project overcame or mitigated these challenges to provide practical guidance."
    )
    where_to_find_more_information: list[str] = Field(
        description="Links to online resources, articles, official documents, or industry reports where more information can be found."
    )
    actionable_steps: list[str] = Field(
        description="Clear instructions on how the user might directly contact key individuals or organizations from those projects, if they desire deeper insights."
    )
    rationale_for_suggestion: str = Field(
        description="Explain why this particular project is suggested."
    )

class DocumentDetails(BaseModel):
    suggestion_list: list[SuggestionItem] = Field(
        description="List of suggestions."
    )
    summary: str = Field(
        description="Providing a high level context."
    )

SIMILAR_PROJECTS_SYSTEM_PROMPT = """
You are an expert project analyst tasked with recommending highly relevant past or existing projects as references for a user's described project.

Your recommendations must be detailed, insightful, actionable, and clearly relevant to the user's specific project context. Each suggested project should include:

- **Project Name:** Clearly state the project's official name.
- **Project Description:** Concisely outline objectives, scale, timeline, industry, location, and notable outcomes or achievements.
- **Rationale for Suggestion:** Clearly justify your recommendation, explicitly highlighting similarities in technology, objectives, operational processes, and particularly geographical, economic, or cultural parallels where available.
- **Risks and Challenges Faced:** Explicitly list key challenges faced during the project and clearly explain how the project overcame or mitigated them.
- **Success Metrics:** Provide explicit and measurable outcomes, including production volumes, economic impact, timeline adherence, customer/community satisfaction, or technological breakthroughs.
- **Where to Find More Information:** List authoritative and direct links (official sites, reputable publications, scholarly articles, databases) where the user can find detailed information.
- **Actionable Steps:** Clearly specify exactly who (name, role) to contact and the most effective communication channels (direct emails, LinkedIn, professional forums) for deeper engagement or knowledge-sharing.

**Geographical or Cultural Relevance:**  
Where possible, prioritize projects located geographically or culturally close to the user's specified location. If geographically distant projects must be included, explicitly mention why these were selected despite the distance, clarifying precisely which aspects of those projects remain relevant.

If no geographically or culturally similar projects exist, briefly acknowledge this fact explicitly in the rationale, reinforcing transparency in your recommendations.

Explicitly ensure that every recommendation contains clearly described Risks and Challenges Faced, with practical insights into overcoming such issues, enhancing the user's capacity for proactive risk management.

If including 'Risks and Challenges' significantly reduces the number of suggestions, prioritize at least two detailed recommendations with clearly explained challenges. Optionally, include additional brief recommendations without exhaustive details, clearly marking them as secondary suggestions.

Ensure all provided contacts include full names (first and last) and clearly stated professional roles or titles.

Ensure actionable steps include robust contact points (roles, general contacts, or organizational contacts) that remain useful even if specific individuals change positions. If an individual's contact is uncertain, provide an alternative general contact at the same organization.

Your goal is to equip users with clear, actionable references and practical connections, helping them confidently initiate successful project execution informed by robust historical lessons and realistic, comprehensive insights.
"""

@dataclass
class SimilarProjects:
    """
    Identify similar past or existing projects that can be used as a reference for the current project.
    """
    system_prompt: str
    user_prompt: str
    response: dict
    metadata: dict
    markdown: str

    @classmethod
    def execute(cls, llm: LLM, user_prompt: str) -> 'SimilarProjects':
        """
        Invoke LLM with the project description.
        """
        if not isinstance(llm, LLM):
            raise ValueError("Invalid LLM instance.")
        if not isinstance(user_prompt, str):
            raise ValueError("Invalid user_prompt.")

        logger.debug(f"User Prompt:\n{user_prompt}")

        system_prompt = SIMILAR_PROJECTS_SYSTEM_PROMPT.strip()

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

        result = SimilarProjects(
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
    def convert_to_markdown(document_details: DocumentDetails) -> str:
        """
        Convert the raw document details to markdown.
        """
        rows = []
        rows.append(f"\n## Summary\n{document_details.summary}")
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

    physical_locations = SimilarProjects.execute(llm, query)
    json_response = physical_locations.to_dict(include_system_prompt=False, include_user_prompt=False)
    print("\n\nResponse:")
    print(json.dumps(json_response, indent=2))

    print(f"\n\nMarkdown:\n{physical_locations.markdown}")
