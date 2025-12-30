"""
WBS Level 2: Create a Work Breakdown Structure (WBS) from a project plan.

https://en.wikipedia.org/wiki/Work_breakdown_structure

Focus is on the "Process style". 
Focus is not on the "product style".
"""
import json
import time
from math import ceil
from uuid import uuid4
from dataclasses import dataclass
from pydantic import BaseModel, Field
from llama_index.core.llms.llm import LLM
from worker_plan_internal.format_json_for_use_in_query import format_json_for_use_in_query

class SubtaskDetails(BaseModel):
    subtask_wbs_number: str = Field(
        description="The unique identifier assigned to each subtask. Example: ['1.', '2.', '3.', '6.2.2', '6.2.3', '6.2.4', 'Subtask 5:', 'Subtask 6:', 'S3.', 'S4.']."
    )
    subtask_title: str = Field(
        description="Start with a verb to clearly indicate the action required. Example: ['Secure funding', 'Obtain construction permits', 'Electrical installation', 'Commissioning and handover']."
    )

class MajorPhaseDetails(BaseModel):
    """
    A major phase in the project decomposed into smaller tasks.
    """
    major_phase_wbs_number: str = Field(
        description="The unique identifier assigned to each major phase. Example: ['1.', '2.', '3.', 'Phase 1:', 'Phase 2:', 'P1.', 'P2.']."
    )
    major_phase_title: str = Field(
        description="Action-oriented title of this primary phase of the project. Example: ['Project Initiation', 'Procurement', 'Construction', 'Operation and Maintenance']."
    )
    subtasks: list[SubtaskDetails] = Field(
        description="List of the subtasks or activities."
    )

class WorkBreakdownStructure(BaseModel):
    """
    The Work Breakdown Structure (WBS) is a hierarchical decomposition of the total scope of work to accomplish project objectives.
    It organizes the project into smaller, more manageable components.
    """
    major_phase_details: list[MajorPhaseDetails] = Field(
        description="List with each major phase broken down into subtasks or activities."
    )

QUERY_PREAMBLE = """
Create a work breakdown structure level 2 for this project.

A task can always be broken down into smaller, more manageable subtasks.

"""

@dataclass
class CreateWBSLevel2:
    """
    WBS Level 2: Creating a Work Breakdown Structure (WBS) from a project plan.
    """
    query: str
    response: dict
    metadata: dict
    major_phases_with_subtasks: list[dict]
    major_phases_uuids: list[str]
    task_uuids: list[str]

    @classmethod
    def format_query(cls, plan_json: dict, wbs_level1_json: dict) -> str:
        """
        Format the query for creating a Work Breakdown Structure (WBS) level 2.
        """
        if not isinstance(plan_json, dict):
            raise ValueError("Invalid plan_json.")
        if not isinstance(wbs_level1_json, dict):
            raise ValueError("Invalid wbs_level1_json.")
        
        # Having a uuid in the WBS Level 1 data trend to confuse the LLM, causing the LLM to attempt to insert all kinds of ids in the response.
        # Removing the id from the WBS Level 1 data, and there is less confusion about what the LLM should do.
        wbs_level1_json_without_id = wbs_level1_json.copy()
        wbs_level1_json_without_id.pop("id", None)

        query = f"""
The project plan:
{format_json_for_use_in_query(plan_json)}

WBS Level 1:
{format_json_for_use_in_query(wbs_level1_json_without_id)}
"""
        return query
    
    @classmethod
    def execute(cls, llm: LLM, query: str) -> 'CreateWBSLevel2':
        """
        Invoke LLM to create a Work Breakdown Structure (WBS) from a json representation of a project plan.
        """
        if not isinstance(llm, LLM):
            raise ValueError("Invalid LLM instance.")
        if not isinstance(query, str):
            raise ValueError("Invalid query.")

        start_time = time.perf_counter()

        sllm = llm.as_structured_llm(WorkBreakdownStructure)
        response = sllm.complete(QUERY_PREAMBLE + query)
        json_response = json.loads(response.text)

        end_time = time.perf_counter()
        duration = int(ceil(end_time - start_time))

        metadata = dict(llm.metadata)
        metadata["llm_classname"] = llm.class_name()
        metadata["duration"] = duration

        # Cleanup the json response from the LLM model, assign unique ids to each activity.
        result_major_phases_with_subtasks = []
        result_major_phases_uuids = []
        result_task_uuids = []
        for major_phase_detail in json_response['major_phase_details']:
            subtask_list = []
            for subtask in major_phase_detail['subtasks']:
                subtask_title = subtask['subtask_title']
                uuid = str(uuid4())
                subtask_item = {
                    "id": uuid,
                    "description": subtask_title,
                }
                subtask_list.append(subtask_item)
                result_task_uuids.append(uuid)

            uuid = str(uuid4())
            major_phase_item = {
                "id": uuid,
                "major_phase_title": major_phase_detail['major_phase_title'],
                "subtasks": subtask_list,
            }
            result_major_phases_with_subtasks.append(major_phase_item)
            result_major_phases_uuids.append(uuid)

        result = CreateWBSLevel2(
            query=query,
            response=json_response,
            metadata=metadata,
            major_phases_with_subtasks=result_major_phases_with_subtasks,
            major_phases_uuids=result_major_phases_uuids,
            task_uuids=result_task_uuids
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

    # TODO: Eliminate hardcoded paths
    path = '/Users/neoneye/Desktop/planexe_data/plan.json'

    wbs_level1_json = {
        "id": "d0169227-bf29-4a54-a898-67d6ff4d1193",
        "project_title": "Establish a solar farm in Denmark",
        "final_deliverable": "Solar farm operational",
    }

    print(f"file: {path}")
    with open(path, 'r', encoding='utf-8') as f:
        plan_json = json.load(f)

    query = CreateWBSLevel2.format_query(plan_json, wbs_level1_json)

    model_name = "llama3.1:latest"
    # model_name = "qwen2.5-coder:latest"
    # model_name = "phi4:latest"
    llm = Ollama(model=model_name, request_timeout=120.0, temperature=0.5, is_function_calling_model=False)

    print(f"Query: {query}")
    result = CreateWBSLevel2.execute(llm, query)

    print("Response:")
    response_dict = result.raw_response_dict(include_query=False)
    print(json.dumps(response_dict, indent=2))

    print("\n\nExtracted result:")
    print(json.dumps(result.major_phases_with_subtasks, indent=2))

