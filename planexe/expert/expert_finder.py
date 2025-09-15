"""
PROMPT> python -m planexe.expert.expert_finder

Find experts that can take a look at the a document, such as a 'SWOT analysis' and provide feedback.

IDEA: Specify a number of experts to be obtained. Currently it's hardcoded 8.
When it's 4 or less, then there is no need to make a second call to the LLM model.
When it's 9 or more, then make multiple calls to the LLM model to get more experts.
"""
import json
import time
import logging
from math import ceil
from uuid import uuid4
from dataclasses import dataclass
from pydantic import BaseModel, Field
from llama_index.core.llms.llm import LLM
from llama_index.core.llms import ChatMessage, MessageRole
from planexe.llm_util.llm_executor import LLMExecutor, PipelineStopRequested

logger = logging.getLogger(__name__)

class Expert(BaseModel):
    expert_title: str = Field(description="Job title of the expert.")
    expert_knowledge: str = Field(description="Industry Knowledge/Specialization, specific industries or subfields where they have focused their career, such as: tech industry for an IT consultant, healthcare sector for a medical expert. **Must be a brief comma separated list**.")
    expert_why: str = Field(description="Why can this expert be of help. Area of expertise.")
    expert_what: str = Field(description="Describe what area of this document the role should advise about.")
    expert_relevant_skills: str = Field(description="Skills that are relevant to the document.")
    expert_search_query: str = Field(description="What query to use when searching for this expert.")

class ExpertDetails(BaseModel):
    experts: list[Expert] = Field(description="List of experts.")

EXPERT_FINDER_SYSTEM_PROMPT = """
Professionals who can offer specialized perspectives and recommendations based on the document.

Ensure that each expert role directly aligns with specific sections or themes within the document.
This could involve linking particular strengths, weaknesses, opportunities, threats, extra sections, to the expertise required.

Diversity in the types of experts suggested by considering interdisciplinary insights that might not be 
immediately obvious but could offer unique perspectives on the document.

Account for geographical and contextual relevance, variations in terminology or regional differences that may affect the search outcome.

The "expert_search_query" field is a human readable text for searching in Google/DuckDuckGo/LinkedIn.

Find exactly 4 experts.
"""

@dataclass
class ExpertFinder:
    """
    Find experts that can advise about the particular domain.
    """
    system_prompt: str
    user_prompt: str
    response: dict
    metadata: dict
    expert_list: list[dict]

    @classmethod
    def execute(cls, llm_executor: LLMExecutor, user_prompt: str) -> 'ExpertFinder':
        """
        Invoke LLM to find the best suited experts that can advise about attached file.
        """
        if not isinstance(llm_executor, LLMExecutor):
            raise ValueError("Invalid LLMExecutor instance.")
        if not isinstance(user_prompt, str):
            raise ValueError("Invalid query.")

        system_prompt = EXPERT_FINDER_SYSTEM_PROMPT.strip()

        chat_message_list1 = [
            ChatMessage(
                role=MessageRole.SYSTEM,
                content=system_prompt,
            ),
            ChatMessage(
                role=MessageRole.USER,
                content=user_prompt,
            )
        ]

        def execute_function1(llm: LLM) -> dict:
            sllm = llm.as_structured_llm(ExpertDetails)
            logger.debug("Starting LLM chat interaction 1.")
            start_time = time.perf_counter()
            chat_response = sllm.chat(chat_message_list1)
            end_time = time.perf_counter()
            duration = int(ceil(end_time - start_time))
            response_byte_count = len(chat_response.message.content.encode('utf-8'))
            logger.info(f"LLM chat interaction completed in {duration} seconds. Response byte count: {response_byte_count}")
            
            metadata = dict(llm.metadata)
            metadata["llm_classname"] = llm.class_name()
            metadata["duration"] = duration
            metadata["response_byte_count"] = response_byte_count
            
            return {
                "chat_response": chat_response,
                "metadata": metadata,
            }

        try:
            result1 = llm_executor.run(execute_function1)
        except PipelineStopRequested:
            raise
        except Exception as e:
            logger.error("LLM chat interaction 1 failed.", exc_info=True)
            raise ValueError("LLM chat interaction 1 failed.") from e

        chat_response1 = result1["chat_response"]

        # Do a follow up question, for obtaining more experts.
        chat_message_assistant2 = ChatMessage(
            role=MessageRole.ASSISTANT,
            content=chat_response1.message.content,
        )
        chat_message_user2 = ChatMessage(
            role=MessageRole.USER,
            content="4 more please",
        )
        chat_message_list2 = chat_message_list1.copy()
        chat_message_list2.append(chat_message_assistant2)
        chat_message_list2.append(chat_message_user2)

        def execute_function2(llm: LLM) -> dict:
            sllm = llm.as_structured_llm(ExpertDetails)
            logger.debug("Starting LLM chat interaction 2.")
            start_time = time.perf_counter()
            chat_response = sllm.chat(chat_message_list2)
            end_time = time.perf_counter()
            duration = int(ceil(end_time - start_time))
            response_byte_count = len(chat_response.message.content.encode('utf-8'))
            logger.info(f"LLM chat interaction completed in {duration} seconds. Response byte count: {response_byte_count}")
            
            metadata = dict(llm.metadata)
            metadata["llm_classname"] = llm.class_name()
            metadata["duration"] = duration
            metadata["response_byte_count"] = response_byte_count
            
            return {
                "chat_response": chat_response,
                "metadata": metadata,
            }

        try:
            result2 = llm_executor.run(execute_function2)
        except PipelineStopRequested:
            raise
        except Exception as e:
            logger.error("LLM chat interaction 2 failed.", exc_info=True)
            raise ValueError("LLM chat interaction 2 failed.") from e

        chat_response2 = result2["chat_response"]

        metadata = {
            "result1": result1["metadata"],
            "result2": result2["metadata"]
        }

        json_response1 = json.loads(chat_response1.message.content)
        json_response2 = json.loads(chat_response2.message.content)

        json_response_merged = {}
        experts1 = json_response1.get('experts', [])
        experts2 = json_response2.get('experts', [])
        json_response_merged['experts'] = experts1 + experts2

        # Cleanup the json response from the LLM model, extract the experts.
        expert_list = []
        for expert in json_response_merged['experts']:
            uuid = str(uuid4())
            expert_dict = {
                "id": uuid,
                "title": expert['expert_title'],
                "knowledge": expert['expert_knowledge'],
                "why": expert['expert_why'],
                "what": expert['expert_what'],
                "skills": expert['expert_relevant_skills'],
                "search_query": expert['expert_search_query'],
            }
            expert_list.append(expert_dict)

        logger.info(f"Found {len(expert_list)} experts.")

        return ExpertFinder(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response=json_response_merged,
            metadata=metadata,
            expert_list=expert_list,
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

    def save_raw(self, file_path: str) -> None:
        with open(file_path, 'w') as f:
            f.write(json.dumps(self.to_dict(), indent=2))

    def save_cleanedup(self, file_path: str) -> None:
        with open(file_path, 'w') as f:
            f.write(json.dumps(self.expert_list, indent=2))
        

if __name__ == "__main__":
    import logging
    from planexe.llm_util.llm_executor import LLMExecutor, LLMModelFromName
    import os

    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler()
        ]
    )

    path = os.path.join(os.path.dirname(__file__), 'test_data', 'expert_finder_user_prompt1.txt')
    with open(path, 'r', encoding='utf-8') as f:
        user_prompt = f.read()

    # Create LLMExecutor with fallback models
    llm_models = LLMModelFromName.from_names([
        # "openrouter-paid-gemini-2.0-flash-001",
        # "openrouter-paid-openai-gpt-4o-mini",
        "ollama-llama3.1", 
        "deepseek-chat"
    ])
    llm_executor = LLMExecutor(llm_models=llm_models)

    # print(f"User prompt: {user_prompt}")
    result = ExpertFinder.execute(llm_executor, user_prompt)

    print("\n\nResponse:")
    print(json.dumps(result.to_dict(include_system_prompt=False, include_user_prompt=False), indent=2))

    print("\n\nExperts:")
    print(json.dumps(result.expert_list, indent=2))
