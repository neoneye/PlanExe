"""
For a reader of the plan that is unfamiliar with the domain, provide a list of Q&A pairs that are relevant to the plan.

PROMPT> python -m src.questions_answers.question_answers
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

class QuestionAnswerPair(BaseModel):
    item_index: int = Field(
        description="Enumeration of the question answer pairs, starting from 1."
    )
    question: str = Field(
        description="The question."
    )
    answer: str = Field(
        description="The answer to the question."
    )
    rationale_for_question_answer_pair: str = Field(
        description="Explain why this particular question answer pair is suggested."
    )

class DocumentDetails(BaseModel):
    question_answer_pairs: list[QuestionAnswerPair] = Field(
        description="List of question answer pairs."
    )
    summary: str = Field(
        description="Providing a high level context."
    )

QUESTION_ANSWER_SYSTEM_PROMPT = """
You are a world-class expert in analyzing project documentation and generating insightful Questions and Answers (Q&A) for a reader who needs clarification on key aspects of the project's domain or methodology as presented in the document. Your goal is to analyze the user's provided project description (the plan document itself), identify key concepts, terms, and approaches, and generate a JSON response that strictly follows the `DocumentDetails` and `QuestionAnswerPair` models provided below.

Analyze the provided project description thoroughly. Identify the core subject area (the domain) and the significant terms, concepts, strategies, or methodologies used *within the document*. Your task is to generate relevant Q&A that clarify these key aspects for a reader who may have some general business or project knowledge but is not necessarily an expert in *this specific domain* or *this specific methodology*.

For each Question and Answer pair:
1.  Generate a clear `question` about a key concept, term, approach, or aspect **presented in the provided document**, especially those related to the project's domain or methodology. Frame the question as something a reader of *this report* might ask for better understanding.
2.  Provide a concise, accurate, and relevant `answer` to the question. The answer should explain the concept or term **as it applies within the context of the project described in the document**, using appropriate language (not overly simplified, but defining necessary terms). Base the answer on the information available in the document or general knowledge required to understand the document's terminology. Strictly avoid unrelated, sensitive, or non-project-relevant information.
3.  Provide a `rationale_for_question_answer_pair` that explains **why this specific Q&A is relevant and useful for a reader trying to understand the content of this project document**. Link the Q&A to the project's specific domain, goals, challenges, or methodologies as described in the text.

Generate between 5 and 10 relevant Q&A pairs. Ensure `item_index` starts at 1 and increments for each pair.

Use the following JSON models:

### DocumentDetails
-   **question_answer_pairs** (list of QuestionAnswerPair): A list of Question and Answer pairs generated based on the key concepts and terms presented in the project document.
-   **summary** (string): A brief, high-level summary of the generated Q&A section, explaining that it covers key concepts and terms from the project document to aid understanding.

### QuestionAnswerPair
-   **item_index** (integer): Enumeration of the question answer pairs, starting from 1.
-   **question** (string): A question about a key concept or term from the project document.
-   **answer** (string): A clear explanation of the concept or term as it relates to the project, based on the document or relevant general knowledge.
-   **rationale_for_question_answer_pair** (string): An explanation of *why* this Q&A helps a reader understand the document's content.

## Additional Instructions

1.  **Analyze the Document's Content:** Use the provided text to identify the project's domain, key terms, concepts, strategies, and approaches *as described in the document*.
2.  **Generate Q&A from Document Concepts:** Generate Q&A that explain these specific concepts and terms *from the document's perspective*.
3.  **Target Project-Relevant Level:** Assume the reader can handle some project or business terminology but needs clarification on domain-specific or methodology-specific terms used in the document. Do not oversimplify to an absolute beginner level, but define terms where necessary for context.
4.  **Base Answers on Document/Relevant Knowledge:** Provide answers consistent with the document's content or general knowledge directly relevant to understanding the terms/concepts *in that project context*.
5.  **Rationale Focus:** The `rationale_for_question_answer_pair` must explain the *value of the Q&A for understanding *this specific document's content*.
6.  **Strict JSON Format:** The final output MUST be a JSON object strictly conforming to the `DocumentDetails` model. Do not include any conversational text or explanations outside the JSON object.
7.  **Language:** Generate the Q&A in the language of the user's text.
8.  **Avoid Unrelated Content:** Explicitly avoid generating Q&A about topics unrelated to the project's domain and concepts as presented, and strictly adhere to safety guidelines.
"""

@dataclass
class QuestionAnswers:
    """
    Identify what questions and answers are relevant to the plan.
    """
    system_prompt: str
    user_prompt: str
    response: dict
    metadata: dict
    markdown: str

    @classmethod
    def execute(cls, llm: LLM, user_prompt: str) -> 'QuestionAnswers':
        """
        Invoke LLM with the project description.
        """
        if not isinstance(llm, LLM):
            raise ValueError("Invalid LLM instance.")
        if not isinstance(user_prompt, str):
            raise ValueError("Invalid user_prompt.")

        logger.debug(f"User Prompt:\n{user_prompt}")

        system_prompt = QUESTION_ANSWER_SYSTEM_PROMPT.strip()

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

        result = QuestionAnswers(
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

        for index, qapair in enumerate(document_details.question_answer_pairs, start=1):
            rows.append(f"\n## Question Answer Pair {index}")
            rows.append(f"**Question**: {qapair.question}")
            rows.append(f"**Answer**: {qapair.answer}")
            rows.append(f"**Rationale**: {qapair.rationale_for_question_answer_pair}")
        
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

    physical_locations = QuestionAnswers.execute(llm, query)
    json_response = physical_locations.to_dict(include_system_prompt=False, include_user_prompt=False)
    print("\n\nResponse:")
    print(json.dumps(json_response, indent=2))

    print(f"\n\nMarkdown:\n{physical_locations.markdown}")
