"""
Review the plan.

PROMPT> python -m src.plan.review_plan
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

class DocumentDetails(BaseModel):
    bullet_points: list[str] = Field(
        description="Answers to the questions in bullet points."
    )

REVIEW_PLAN_SYSTEM_PROMPT = """
You are an expert in reviewing plans for projects of all scales. For each question, you MUST provide exactly three concise and distinct bullet points as your answer. Each bullet point must combine all required details for that question into one sentence or clause.

For example:
- If a question asks for key dependencies along with their likelihood (e.g., Medium, High, Low) and control (internal or external), then each bullet point must include the dependency name, its likelihood, and whether it is controlled internally or externally—all combined into one sentence.
- If a question asks for regulatory requirements, each bullet point must state the requirement and briefly explain how it will be met. Do not include any extra header lines or additional bullet points.

If additional details are needed, merge or summarize them so that your final answer always consists of exactly three bullet points.

Your final output must be a JSON object in the following format:
{
  "bullet_points": [
    "Bullet point 1 (including all required details)",
    "Bullet point 2 (including all required details)",
    "Bullet point 3 (including all required details)"
  ]
}

Do not include any extra bullet points, header lines, or any additional text outside of this JSON structure.
"""

@dataclass
class ReviewPlan:
    """
    Take a look at the proposed plan and provide feedback.
    """
    system_prompt: str
    question_answers_list: list[dict]
    metadata: dict

    @classmethod
    def execute(cls, llm: LLM, document: str) -> 'ReviewPlan':
        """
        Invoke LLM with the data to be reviewed.
        """
        if not isinstance(llm, LLM):
            raise ValueError("Invalid LLM instance.")
        if not isinstance(document, str):
            raise ValueError("Invalid document.")

        logger.debug(f"Document:\n{document}")

        system_prompt = REVIEW_PLAN_SYSTEM_PROMPT.strip()
        system_prompt += "\n\nDocument for review:\n"
        system_prompt += document

        questions = [
            "Identify exactly three significant consequences—both positive and negative—that may result from implementing the plan. For each consequence, provide a brief explanation of its impact on the plan’s overall feasibility, outcomes, or long-term success. Please present your answer in exactly three bullet points.",
            # "What are the three most critical, actionable adjustments required in version 2 of the plan based on newly discovered insights or overlooked assumptions? For each, provide a specific action step, identify the responsible party, and outline a measurable outcome. Please answer in exactly three bullet points, combining related details as needed.",
            # "List three factors that determine whether the plan is realistic, considering time, budget, resources, and the environment.",
            # "Summarize the key aspects of the assumptions, their justification, and supporting evidence in exactly three bullet points.",
            # "List exactly three key dependencies for the project. For each dependency, provide one bullet point that combines the dependency, its likelihood (e.g., Medium, High, Low), and whether it is controlled internally or externally.",
            # "Summarize the key ‘showstopper’ risks and their mitigation strategies in exactly three bullet points. Combine multiple related risks into one bullet if needed.",
            # "List exactly three key gaps in the plan’s scope or approach. If there are more, combine related points so that your final answer consists of exactly three bullet points.",
            # "List exactly three key regulatory and compliance requirements for the project and explain briefly how each will be met, all in one bullet point per requirement.",
        ]

        chat_message_list = [
            ChatMessage(
                role=MessageRole.SYSTEM,
                content=system_prompt,
            )
        ]

        question_answers_list = []

        durations = []
        response_byte_counts = []

        for index, question in enumerate(questions, start=1):
            print(f"Question {index}: {question}")
            chat_message_list.append(ChatMessage(
                role=MessageRole.USER,
                content=question,
            ))

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
            durations.append(duration)
            response_byte_count = len(chat_response.message.content.encode('utf-8'))
            response_byte_counts.append(response_byte_count)
            logger.info(f"LLM chat interaction completed in {duration} seconds. Response byte count: {response_byte_count}")

            json_response = chat_response.raw.model_dump()
            print(json.dumps(json_response, indent=2))

            question_answers_list.append({
                "question": question,
                "answers": chat_response.raw.bullet_points,
            })

            chat_message_list.append(ChatMessage(
                role=MessageRole.ASSISTANT,
                content=chat_response.message.content,
            ))

        response_byte_count_total = sum(response_byte_counts)
        response_byte_count_average = response_byte_count_total / len(questions)
        duration_total = sum(durations)
        duration_average = duration_total / len(questions)

        metadata = dict(llm.metadata)
        metadata["llm_classname"] = llm.class_name()
        metadata["duration_total"] = duration_total
        metadata["duration_average"] = duration_average
        metadata["response_byte_count_total"] = response_byte_count_total
        metadata["response_byte_count_average"] = response_byte_count_average

        result = ReviewPlan(
            system_prompt=system_prompt,
            question_answers_list=question_answers_list,
            metadata=metadata,
        )
        return result
    
    def to_dict(self, include_metadata=True, include_system_prompt=True) -> dict:
        d = {}
        d['question_answers_list'] = self.question_answers_list
        if include_metadata:
            d['metadata'] = self.metadata
        if include_system_prompt:
            d['system_prompt'] = self.system_prompt
        return d

if __name__ == "__main__":
    from src.llm_factory import get_llm

    llm = get_llm("ollama-llama3.1")

    path = os.path.join(os.path.dirname(__file__), 'test_data', "deadfish_assumptions.md")
    with open(path, 'r', encoding='utf-8') as f:
        assumptions_markdown = f.read()

    query = (
        f"File 'assumptions.md':\n{assumptions_markdown}"
    )
    print(f"Query:\n{query}\n\n")

    result = ReviewPlan.execute(llm, query)
    json_response = result.to_dict(include_system_prompt=False)
    print(json.dumps(json_response, indent=2))
