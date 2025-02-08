"""
WBS Level 1: Create a Work Breakdown Structure (WBS) from a project plan.

https://en.wikipedia.org/wiki/Work_breakdown_structure
"""
import os
import json
import time
from math import ceil
from typing import List, Optional
from uuid import uuid4
from dataclasses import dataclass
from pydantic import BaseModel, Field
from llama_index.core.llms.llm import LLM

class WBSLevel1(BaseModel):
    """
    Represents the top-level details of a Work Breakdown Structure (WBS)
    """
    project_title: str = Field(
        description="A clear, overarching title that conveys the primary objective of the project. Serves as the projects strategic anchor, guiding all subsequent tasks and deliverables."
    )
    final_deliverable: str = Field(
        description="A detailed description of the projects ultimate outcome or product upon completion. Clearly states the final state or result that the team aims to achieve."
    )

QUERY_PREAMBLE = f"""
The task here:
Create a work breakdown structure level 1 for this project.

Focus on providing the following:
- 'project_title': A 1- to 3-word name, extremely concise.
- 'final_deliverable': A 1- to 3-word result, extremely concise.

The project plan:
"""


@dataclass
class CreateWBSLevel1:
    """
    WBS Level 1: Creating a Work Breakdown Structure (WBS) from a project plan.
    """
    query: str
    response: dict
    metadata: dict
    id: str
    project_title: str
    final_deliverable: str

    @classmethod
    def execute(cls, llm: LLM, query: str) -> 'CreateWBSLevel1':
        """
        Invoke LLM to create a Work Breakdown Structure (WBS) from a json representation of a project plan.
        """
        if not isinstance(llm, LLM):
            raise ValueError("Invalid LLM instance.")
        if not isinstance(query, str):
            raise ValueError("Invalid query.")

        start_time = time.perf_counter()

        sllm = llm.as_structured_llm(WBSLevel1)
        response = sllm.complete(QUERY_PREAMBLE + query)
        json_response = json.loads(response.text)

        end_time = time.perf_counter()
        duration = int(ceil(end_time - start_time))

        metadata = dict(llm.metadata)
        metadata["llm_classname"] = llm.class_name()
        metadata["duration"] = duration
        metadata["query"] = query

        project_id = str(uuid4())
        result = CreateWBSLevel1(
            query=query,
            response=json_response,
            metadata=metadata,
            id=project_id,
            project_title=json_response['project_title'],
            final_deliverable=json_response['final_deliverable']
        )
        return result
    
    def raw_response_dict(self, include_metadata=True) -> dict:
        d = self.response.copy()
        if include_metadata:
            d['metadata'] = self.metadata
        return d
    
    def cleanedup_dict(self) -> dict:
        return {
            "id": self.id,
            "project_title": self.project_title,
            "final_deliverable": self.final_deliverable
        }

if __name__ == "__main__":
    from llama_index.llms.ollama import Ollama
    # TODO: Eliminate hardcoded paths
    path = '/Users/neoneye/Desktop/planexe_data/plan.json'

    print(f"file: {path}")
    with open(path, 'r', encoding='utf-8') as f:
        plan_json = json.load(f)

    if 'metadata' in plan_json:
        del plan_json['metadata']

    model_name = "llama3.1:latest"
    # model_name = "qwen2.5-coder:latest"
    # model_name = "phi4:latest"
    llm = Ollama(model=model_name, request_timeout=120.0, temperature=0.5, is_function_calling_model=False)

    query = json.dumps(plan_json, indent=2)
    print(f"\nQuery: {query}")
    result = CreateWBSLevel1.execute(llm, query)
    print("\n\nResult:")
    print(json.dumps(result.raw_response_dict(), indent=2))
