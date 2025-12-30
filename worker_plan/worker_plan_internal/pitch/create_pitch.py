"""
Create a pitch for this project.

PROMPT> python -m worker_plan_internal.pitch.create_pitch
"""
import os
import json
import time
from math import ceil
from dataclasses import dataclass
from pydantic import BaseModel, Field
from llama_index.core.llms.llm import LLM
from worker_plan_internal.format_json_for_use_in_query import format_json_for_use_in_query

class ProjectPitch(BaseModel):
    pitch: str = Field(
        description="A compelling pitch for this project."
    )
    why_this_pitch_works: str = Field(
        description="Explanation why this pitch works."
    )
    target_audience: str = Field(
        description="Who this pitch is aimed at, such as investors, stakeholders, or the general public."
    )
    call_to_action: str = Field(
        description="A clear next step for the audience to engage with the project."
    )
    risks_and_mitigation: str = Field(
        description="Address potential challenges and demonstrate readiness to handle them."
    )
    metrics_for_success: str = Field(
        description="Define how the success of the project will be measured beyond its goals."
    )
    stakeholder_benefits: str = Field(
        description="Explicitly state what stakeholders gain from supporting or being involved in the project."
    )
    ethical_considerations: str = Field(
        description="Build trust by showing a commitment to ethical practices."
    )
    collaboration_opportunities: str = Field(
        description="Highlight ways other organizations or individuals can partner with the project."
    )
    long_term_vision: str = Field(
        description="Show the broader impact and sustainability of the project."
    )

QUERY_PREAMBLE = """
Craft a compelling pitch for this project that starts with an attention-grabbing hook, 
presents its purpose clearly, and highlights the benefits or value it brings. Use a tone 
that conveys enthusiasm and aligns with the goals and values of the intended audience, 
emphasizing why this project matters and how it stands out.

"""

@dataclass
class CreatePitch:
    query: str
    response: dict
    metadata: dict

    @classmethod
    def format_query(cls, plan_json: dict, wbs_level1_json: dict, wbs_level2_json: list) -> str:
        """
        Format the query for creating project pitch.
        """
        if not isinstance(plan_json, dict):
            raise ValueError("Invalid plan_json.")
        if not isinstance(wbs_level1_json, dict):
            raise ValueError("Invalid wbs_level1_json.")
        if not isinstance(wbs_level2_json, list):
            raise ValueError("Invalid wbs_level2_json.")

        query = f"""
The project plan:
{format_json_for_use_in_query(plan_json)}

WBS Level 1:
{format_json_for_use_in_query(wbs_level1_json)}

WBS Level 2:
{format_json_for_use_in_query(wbs_level2_json)}
"""
        return query
    
    @classmethod
    def execute(cls, llm: LLM, query: str) -> 'CreatePitch':
        """
        Invoke LLM to create a project pitch.
        """
        if not isinstance(llm, LLM):
            raise ValueError("Invalid LLM instance.")
        if not isinstance(query, str):
            raise ValueError("Invalid query.")

        start_time = time.perf_counter()

        sllm = llm.as_structured_llm(ProjectPitch)
        response = sllm.complete(QUERY_PREAMBLE + query)
        json_response = json.loads(response.text)

        end_time = time.perf_counter()
        duration = int(ceil(end_time - start_time))

        metadata = dict(llm.metadata)
        metadata["llm_classname"] = llm.class_name()
        metadata["duration"] = duration

        result = CreatePitch(
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

    basepath = os.path.join(os.path.dirname(__file__), 'test_data')

    def load_json(relative_path: str) -> dict:
        path = os.path.join(basepath, relative_path)
        print(f"loading file: {path}")
        with open(path, 'r', encoding='utf-8') as f:
            the_json = json.load(f)
        return the_json

    plan_json = load_json('lunar_base-project_plan.json')
    wbs_level1_json = load_json('lunar_base-wbs_level1.json')
    wbs_level2_json = load_json('lunar_base-wbs_level2.json')

    model_name = "llama3.1:latest"
    # model_name = "qwen2.5-coder:latest"
    # model_name = "phi4:latest"
    llm = Ollama(model=model_name, request_timeout=120.0, temperature=0.5, is_function_calling_model=False)

    query = CreatePitch.format_query(plan_json, wbs_level1_json, wbs_level2_json)
    print(f"Query: {query}")
    result = CreatePitch.execute(llm, query)

    print("\nResponse:")
    json_response = result.raw_response_dict(include_query=False)
    print(json.dumps(json_response, indent=2))
