"""
Ask a specific expert about estimating cost.
"""
import json
import time
from math import ceil
from typing import Optional
from enum import Enum
from dataclasses import dataclass
from pydantic import BaseModel, Field
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.llms.llm import LLM
from planexe.format_json_for_use_in_query import format_json_for_use_in_query

class CostUnit(str, Enum):
    # An hour is 60 minutes.
    hour = 'hour'

    # A day is 24 hours.
    day = 'day'

    # A single upfront fee that covers the entire cost of a project.
    lumpsum = 'lumpsum'

    # A single discrete unit or piece of equipment.
    item = 'item'

    # When no other enum value is applicable.
    other = 'other'

class CostComponent(BaseModel):
    name: str = Field(description="Human-readable name of the cost component.")
    unit: CostUnit = Field(description="Indicates how costs are measured.")
    quantity: float = Field(description="Number of units, if applicable.")
    currency: str = Field(description="What currency used in this cost component, such as: USD, EUR.")
    unit_cost: float = Field(description="Cost per unit, if applicable.")
    labor_cost: float = Field(description="Cost related to labor.")
    material_cost: float = Field(description="Cost related to materials.")
    equipment_cost: float = Field(description="Cost related to equipment.")
    overhead_cost: float = Field(description="Indirect or overhead costs.")
    contingency_rate: float = Field(description="Higher contingency rates for riskier tasks.")

class CostEstimateItem(BaseModel):
    task_id: str = Field(description="Unique identifier for the task.")
    task_name: str = Field(description="Name of the task.")
    cost_component_list: list[CostComponent] = Field(description="Multiple cost components.")
    min_cost: int = Field(description="Minimum estimated cost.")
    max_cost: int = Field(description="Maximum estimated cost.")
    realistic_cost: int = Field(description="Most likely cost estimate.")
    assumptions: list[str] = Field(description="Assumptions made during estimation.")
    high_risks: list[str] = Field(description="Potential risks affecting cost. High risk level.")
    medium_risks: list[str] = Field(description="Potential risks affecting cost. Medium risk level.")
    low_risks: list[str] = Field(description="Potential risks affecting cost. Low risk level.")
    dependencies_impact: str = Field(description="Impact of task dependencies on cost.")

class ExpertCostEstimationResponse(BaseModel):
    cost_estimates: list[CostEstimateItem] = Field(description="List of cost estimates for tasks.")
    primary_actions: list[str] = Field(description="Actionable steps to refine cost estimates.")
    secondary_actions: list[str] = Field(description="Additional suggestions for cost management.")
    follow_up_consultation: str = Field(description="Topics for the next consultation.")

@dataclass
class Document:
    name: str
    content: str

QUERY_PREAMBLE = f"""
Provide detailed and accurate cost estimates for the provided tasks.

Use the following guidelines:
- Provide minimum, maximum, and realistic cost estimates.
- Break down costs into components such as labor, materials, equipment, subcontractors, overhead, and miscellaneous.
- State any assumptions made during estimation.
- Highlight potential risks that could affect costs.
- Explain how task dependencies impact the cost.

Ensure that your estimates are actionable and based on best practices in cost estimation.

Please provide a detailed cost estimate for each task, including minimum, maximum, and realistic costs, 
along with a breakdown of cost components and any relevant assumptions or risks.

Cost components with smaller quantities
Round up the partial-hour rates to the nearest whole hour. 
If a meeting is 15 minutes, the bill might be 1-hour. Better to overestimate than underestimate.

Here are the details of the project tasks for cost estimation:

"""

@dataclass
class ExpertCost:
    """
    Ask an expert advise about estimating cost.
    """
    query: str
    response: dict
    metadata: dict

    @classmethod
    def format_system(cls, expert: dict) -> str:
        if not isinstance(expert, dict):
            raise ValueError("Invalid expert.")

        role = expert.get('title', 'Cost Estimation Expert')
        knowledge = expert.get('knowledge', 'Cost estimation methodologies, project budgeting, financial analysis.')
        skills = expert.get('skills', 'Analytical skills, attention to detail, proficiency in budgeting tools.')

        query = f"""
You are acting as a highly experienced {role}.

Your areas of deep knowledge include:
{knowledge}

You possess the following key skills:
{skills}

"""
        return query

    @classmethod
    def format_query(cls, currency: str, location: str, task_ids_to_process: list[str], documents: list[Document]) -> str:
        if not isinstance(currency, str):
            raise ValueError("Invalid currency.")
        if not isinstance(location, str):
            raise ValueError("Invalid location.")
        if not isinstance(task_ids_to_process, list):
            raise ValueError("Invalid task_ids_to_process.")
        if not isinstance(documents, list):
            raise ValueError("Invalid documents.")

        task_ids_in_quotes = [f'"{task_id}"' for task_id in task_ids_to_process]
        task_id_strings = "\n".join(task_ids_in_quotes)
        task_id_count = len(task_ids_to_process)

        document_items = []
        for document_index, document in enumerate(documents, start=1):
            document_items.append(f"File {document_index}, {document.name}:\n{document.content}")

        document_content = "\n\n".join(document_items)
        query = f"""
{document_content}

Extra information:
- All cost estimates should be in {currency}.
- The project is located in {location}; consider local market rates and economic factors.

Please provide exactly one cost estimate for each of the following {task_id_count} tasks and no others:
{task_id_strings}
**Do not** include cost estimates for tasks not in this list.
"""
        return query

    @classmethod
    def execute(cls, llm: LLM, query: str, system_prompt: Optional[str]) -> 'ExpertCost':
        """
        Invoke LLM to get cost estimation advice from the expert.
        """
        if not isinstance(llm, LLM):
            raise ValueError("Invalid LLM instance.")
        if not isinstance(query, str):
            raise ValueError("Invalid query.")

        chat_message_list = []
        if system_prompt:
            chat_message_list.append(
                ChatMessage(
                    role=MessageRole.SYSTEM,
                    content=system_prompt,
                )
            )
        
        chat_message_user = ChatMessage(
            role=MessageRole.USER,
            content=query,
        )
        chat_message_list.append(chat_message_user)

        start_time = time.perf_counter()

        sllm = llm.as_structured_llm(ExpertCostEstimationResponse)
        chat_response = sllm.chat(chat_message_list)
        json_response = json.loads(chat_response.message.content)

        end_time = time.perf_counter()
        duration = int(ceil(end_time - start_time))

        metadata = dict(llm.metadata)
        metadata["llm_classname"] = llm.class_name()
        metadata["duration"] = duration

        result = ExpertCost(
            query=query,
            response=json_response,
            metadata=metadata,
        )
        return result    

    def raw_response_dict(self, include_metadata=True, include_query=True) -> dict:
        d = self.response.copy()
        if include_metadata:
            d['metadata'] = self.metadata
        if include_query:
            d['query'] = self.query
        return d

if __name__ == "__main__":
    from llama_index.llms.ollama import Ollama
    from llama_index.llms.openai_like import OpenAILike
    from dotenv import dotenv_values
    import os
    from wbs_table_for_cost_estimation.wbs_table_for_cost_estimation import WBSTableForCostEstimation
    from chunk_dataframe_with_context.chunk_dataframe_with_context import chunk_dataframe_with_context
    import pandas as pd
    from pandas import DataFrame

    dotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.env'))
    dotenv_dict = dotenv_values(dotenv_path=dotenv_path)

    if True:
        model_name = "llama3.1:latest"
        # model_name = "qwen2.5-coder:latest"
        # model_name = "phi4:latest"
        llm = Ollama(model=model_name, request_timeout=120.0, temperature=0.5, is_function_calling_model=False)
    else:
        llm = OpenAILike(
            api_base="https://api.deepseek.com/v1",
            api_key=dotenv_dict['DEEPSEEK_API_KEY'],
            model="deepseek-chat",
            is_chat_model=True,
            is_function_calling_model=True,
            max_retries=1,
        )
    

    # TODO: Eliminate hardcoded paths
    basepath = '/Users/neoneye/Desktop/planexe_data'

    def load_json(relative_path: str) -> dict:
        path = os.path.join(basepath, relative_path)
        print(f"loading file: {path}")
        with open(path, 'r', encoding='utf-8') as f:
            the_json = json.load(f)
        return the_json

    def load_text(relative_path: str) -> dict:
        path = os.path.join(basepath, relative_path)
        print(f"loading file: {path}")
        with open(path, 'r', encoding='utf-8') as f:
            the_text = f.read()
        return the_text

    plan_txt = load_text('001-plan.txt')
    document_plan = Document(name="vague_plan_description.txt", content=plan_txt)

    project_plan_json = load_json('002-project_plan.json')
    project_plan = format_json_for_use_in_query(project_plan_json)
    document_project_plan = Document(name="project_plan.json", content=project_plan)

    swot_analysis_md = load_text('004-swot_analysis.md')
    document_swot_analysis = Document(name="swot_analysis.md", content=swot_analysis_md)

    expert_list_json = load_json('006-experts.json')

    path_wbs_table_csv = os.path.join(basepath, '016-wbs_table.csv')
    path_wbs_project_json = os.path.join(basepath, '016-wbs_project.json')
    wbs_table = WBSTableForCostEstimation.create(path_wbs_table_csv, path_wbs_project_json)
    wbs_df = wbs_table.wbs_table_df.copy()

    expert = expert_list_json[5]
    expert.pop('id')
    system_prompt = ExpertCost.format_system(expert)
    print(f"System: {system_prompt}")

    currency = "DKK"
    location = "Kolonihave at Kongelundsvej, Copenhagen, Denmark"

    # The LLM cannot handle the entire WBS hierarchy at once, usually more than 100 rows.
    # Instead process the CSV in chunks of N rows.
    chunk_size=3
    overlap=4

    # Collect all chunks in a list to know how many there are
    all_chunks = list(chunk_dataframe_with_context(wbs_df, chunk_size, overlap))
    # truncate to 5 chunks
    all_chunks = all_chunks[:5]

    # Print out the total number of chunks (iterations) that will be processed
    number_of_chunks = len(all_chunks)
    print(f"There will be {number_of_chunks} iterations.")

    documents_static = [document_plan, document_project_plan, document_swot_analysis]

    # Then iterate over them as usual
    for chunk_index, (core_df, extended_df) in enumerate(all_chunks, start=1):
        print(f"Processing chunk {chunk_index} of {number_of_chunks} ...")

        # Convert extended_df to CSV for the LLM prompt
        extended_csv = extended_df.to_csv(sep=';', index=False)
        document_wbs_chunk = Document(name="work_breakdown_structure.csv", content=extended_csv)
        
        # The tasks we want cost-estimated in this chunk (core tasks only)
        task_ids_to_process = core_df['Task ID'].tolist()
        
        # Format the query with extended context as the content,
        # but instruct the LLM to only produce estimates for the 
        # `task_ids_to_process`.
        query = ExpertCost.format_query(
            currency=currency,
            location=location,
            task_ids_to_process=task_ids_to_process,
            documents=documents_static + [document_wbs_chunk],
        )
        
        # Make the LLM call
        print(f"\n\nChunk {chunk_index} Query (len={len(query)}): {query}")
        # print(f"\n\nChunk {chunk_index} Execute. len(query)={len(query)}")
        result = ExpertCost.execute(llm, query, system_prompt)

        print(f"\n\nChunk {chunk_index} Response:")
        print(json.dumps(result.raw_response_dict(include_query=False), indent=2))
