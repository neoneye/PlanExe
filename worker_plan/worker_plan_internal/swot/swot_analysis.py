"""
Perform a full SWOT analysis

Phase 1 - IdentifyPurpose, classify if this is this going to be a business/personal/other SWOT analysis
Phase 2 - Conduct the SWOT Analysis

PROMPT> python -m worker_plan_internal.swot.swot_analysis
"""
import json
import time
import logging
from math import ceil
from dataclasses import dataclass, asdict
from typing import Optional
from worker_plan_internal.assume.identify_purpose import IdentifyPurpose, PlanPurposeInfo, PlanPurpose
from worker_plan_internal.swot.swot_phase2_conduct_analysis import (
    swot_phase2_conduct_analysis, 
    CONDUCT_SWOT_ANALYSIS_BUSINESS_SYSTEM_PROMPT, 
    CONDUCT_SWOT_ANALYSIS_PERSONAL_SYSTEM_PROMPT,
    CONDUCT_SWOT_ANALYSIS_OTHER_SYSTEM_PROMPT,
)
from llama_index.core.llms.llm import LLM

logger = logging.getLogger(__name__)

@dataclass
class SWOTAnalysis:
    query: str
    topic: str
    purpose: str
    purpose_detailed: str
    response_purpose: dict
    response_conduct: dict
    metadata: dict

    @classmethod
    def execute(cls, llm: LLM, query: str, identify_purpose_dict: Optional[dict]) -> 'SWOTAnalysis':
        """
        Invoke LLM to a full SWOT analysis of the provided query.

        Allow identify_purpose_dict to be None, and we will use IdentifyPurpose to get it
        """
        if not isinstance(llm, LLM):
            raise ValueError("Invalid llm instance.")
        if not isinstance(query, str):
            raise ValueError("Invalid query.")
        if identify_purpose_dict is not None and not isinstance(identify_purpose_dict, dict):
            raise ValueError("Invalid identify_purpose_dict.")

        start_time = time.perf_counter()

        logging.debug("Determining SWOT analysis type...")

        if identify_purpose_dict is None:
            logging.info("No identify_purpose_dict provided, identifying purpose.")
            identify_purpose = IdentifyPurpose.execute(llm, query)
            identify_purpose_dict = identify_purpose.to_dict()
        else:
            logging.info("identify_purpose_dict provided, using it.")

        # Parse the identify_purpose_dict
        logging.debug(f"IdentifyPurpose json {json.dumps(identify_purpose_dict, indent=2)}")
        try:
            purpose_info = PlanPurposeInfo(**identify_purpose_dict)
        except Exception as e:
            logging.error(f"Error parsing identify_purpose_dict: {e}")
            raise ValueError("Error parsing identify_purpose_dict.") from e

        # Select the appropriate system prompt based on the purpose
        logging.info(f"SWOTAnalysis.execute: purpose: {purpose_info.purpose}")
        if purpose_info.purpose == PlanPurpose.business:
            system_prompt = CONDUCT_SWOT_ANALYSIS_BUSINESS_SYSTEM_PROMPT
        elif purpose_info.purpose == PlanPurpose.personal:
            system_prompt = CONDUCT_SWOT_ANALYSIS_PERSONAL_SYSTEM_PROMPT
        elif purpose_info.purpose == PlanPurpose.other:
            system_prompt = CONDUCT_SWOT_ANALYSIS_OTHER_SYSTEM_PROMPT
            system_prompt = system_prompt.replace("INSERT_USER_TOPIC_HERE", purpose_info.topic)
            system_prompt = system_prompt.replace("INSERT_USER_SWOTTYPEDETAILED_HERE", purpose_info.purpose_detailed)
        else:
            raise ValueError(f"Invalid purpose: {purpose_info.purpose}, must be one of 'business', 'personal', or 'other'. Cannot perform SWOT analysis.")

        system_prompt = system_prompt.strip()
        
        json_response_conduct = swot_phase2_conduct_analysis(llm, query, system_prompt)

        end_time = time.perf_counter()
        logging.debug("swot_phase2_conduct_analysis json " + json.dumps(json_response_conduct, indent=2))

        duration = int(ceil(end_time - start_time))
        metadata = dict(llm.metadata)
        metadata["llm_classname"] = llm.class_name()
        metadata["duration"] = duration
        metadata["query"] = query

        result = SWOTAnalysis(
            query=query,
            topic=purpose_info.topic,
            purpose=purpose_info.purpose,
            purpose_detailed=purpose_info.purpose_detailed,
            response_purpose=identify_purpose_dict,
            response_conduct=json_response_conduct,
            metadata=metadata,
        )
        logger.debug("SWOTAnalysis instance created successfully.")
        return result
    
    def to_dict(self) -> dict:
        return asdict(self)

    def to_markdown(self, include_metadata=True, include_purpose=True) -> str:
        rows = []
        if include_purpose:
            rows.append(f"\n## Topic\n{self.topic}")
            rows.append(f"\n## Purpose\n{self.purpose}")
            rows.append(f"\n## Purpose detailed\n{self.purpose_detailed}")

        rows.append("\n## Strengths 👍💪🦾")
        for item in self.response_conduct.get('strengths', []):
            rows.append(f"- {item}")

        rows.append("\n## Weaknesses 👎😱🪫⚠️")
        for item in self.response_conduct.get('weaknesses', []):
            rows.append(f"- {item}")

        rows.append("\n## Opportunities 🌈🌐")
        for item in self.response_conduct.get('opportunities', []):
            rows.append(f"- {item}")

        rows.append("\n## Threats ☠️🛑🚨☢︎💩☣︎")
        for item in self.response_conduct.get('threats', []):
            rows.append(f"- {item}")

        rows.append("\n## Recommendations 💡✅")
        for item in self.response_conduct.get('recommendations', []):
            rows.append(f"- {item}")

        rows.append("\n## Strategic Objectives 🎯🔭⛳🏅")
        for item in self.response_conduct.get('strategic_objectives', []):
            rows.append(f"- {item}")

        rows.append("\n## Assumptions 🤔🧠🔍")
        for item in self.response_conduct.get('assumptions', []):
            rows.append(f"- {item}")

        rows.append("\n## Missing Information 🧩🤷‍♂️🤷‍♀️")
        for item in self.response_conduct.get('missing_information', []):
            rows.append(f"- {item}")

        rows.append("\n## Questions 🙋❓💬📌")
        for item in self.response_conduct.get('user_questions', []):
            rows.append(f"- {item}")

        if include_metadata:
            rows.append("\n## Metadata 📊🔧💾")
            rows.append("```json")
            json_dict = self.metadata.copy()
            json_dict['duration_response_type'] = self.response_purpose['metadata']['duration']
            json_dict['duration_response_conduct'] = self.response_conduct['metadata']['duration']
            rows.append(json.dumps(json_dict, indent=2))
            rows.append("```")

        return "\n".join(rows)

if __name__ == "__main__":
    import logging
    from worker_plan_internal.prompt.prompt_catalog import PromptCatalog
    from worker_plan_internal.llm_factory import get_llm

    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler()
        ]
    )

    prompt_catalog = PromptCatalog()
    prompt_catalog.load_example_swot_prompts()
    prompt_item = prompt_catalog.find("427e5163-cefa-46e8-b1d0-eb12be270e19")
    if not prompt_item:
        raise ValueError("Prompt item not found.")
    query = prompt_item.prompt

    llm = get_llm("ollama-llama3.1")

    print(f"Query: {query}")
    result = SWOTAnalysis.execute(llm=llm, query=query, identify_purpose_dict=None)

    print("\nJSON:")
    print(json.dumps(asdict(result), indent=2))

    print("\n\nMarkdown:")
    print(result.to_markdown(include_metadata=False))
