"""
Perform a full SWOT analysis

Phase 1 - Determining what kind of SWOT analysis to perform
Phase 2 - Conduct the SWOT Analysis

PROMPT> python -m src.swot.swot_analysis
"""
import json
import time
import logging
from math import ceil
from dataclasses import dataclass, asdict
from src.swot.swot_phase1_determine_type import swot_phase1_determine_type
from src.swot.swot_phase2_conduct_analysis import (
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
    swot_type_id: str
    swot_type_verbose: str
    response_type: dict
    response_conduct: dict
    metadata: dict

    @classmethod
    def execute(cls, llm: LLM, query: str) -> 'SWOTAnalysis':
        """
        Invoke LLM to a full SWOT analysis of the provided query.
        """
        if not isinstance(llm, LLM):
            raise ValueError("Invalid llm instance.")
        if not isinstance(query, str):
            raise ValueError("Invalid query.")

        start_time = time.perf_counter()

        logging.debug("Determining SWOT analysis type...")

        json_response_type = swot_phase1_determine_type(llm, query)
        logging.debug("swot_phase1_determine_type json " + json.dumps(json_response_type, indent=2))

        type_id = json_response_type['swot_analysis_type']
        type_detailed = json_response_type['swot_analysis_type_detailed']
        topic = json_response_type['topic']

        if type_id == 'business':
            system_prompt = CONDUCT_SWOT_ANALYSIS_BUSINESS_SYSTEM_PROMPT
        elif type_id == 'personal':
            system_prompt = CONDUCT_SWOT_ANALYSIS_PERSONAL_SYSTEM_PROMPT
        elif type_id == 'other':
            system_prompt = CONDUCT_SWOT_ANALYSIS_OTHER_SYSTEM_PROMPT
            system_prompt = system_prompt.replace("INSERT_USER_TOPIC_HERE", topic)
            system_prompt = system_prompt.replace("INSERT_USER_SWOTTYPEDETAILED_HERE", type_detailed)
        else:
            raise ValueError(f"Invalid SWOT analysis type_id: {type_id}")
        
        logging.debug(f"Conducting SWOT analysis... type_id: {type_id}")
        json_response_conduct = swot_phase2_conduct_analysis(llm, query, system_prompt.strip())

        end_time = time.perf_counter()
        logging.debug("swot_phase2_conduct_analysis json " + json.dumps(json_response_conduct, indent=2))

        duration = int(ceil(end_time - start_time))
        metadata = dict(llm.metadata)
        metadata["llm_classname"] = llm.class_name()
        metadata["duration"] = duration
        metadata["query"] = query

        result = SWOTAnalysis(
            query=query,
            topic=json_response_type.get('topic', ''),
            swot_type_id=type_id,
            swot_type_verbose=json_response_type.get('swot_analysis_type_detailed', ''),
            response_type=json_response_type,
            response_conduct=json_response_conduct,
            metadata=metadata,
        )
        logger.debug("SWOTAnalysis instance created successfully.")
        return result
    
    def to_dict(self) -> dict:
        return asdict(self)

    def to_markdown(self, include_metadata=True) -> str:
        rows = []
        rows.append(f"\n## Topic")
        rows.append(f"{self.topic}")

        rows.append(f"\n## Type")
        rows.append(f"{self.swot_type_id}")

        rows.append(f"\n## Type detailed")
        rows.append(f"{self.swot_type_verbose}")

        rows.append(f"\n## Strengths 👍💪🦾")
        for item in self.response_conduct.get('strengths', []):
            rows.append(f"- {item}")

        rows.append(f"\n## Weaknesses 👎😱🪫⚠️")
        for item in self.response_conduct.get('weaknesses', []):
            rows.append(f"- {item}")

        rows.append(f"\n## Opportunities 🌈🌐")
        for item in self.response_conduct.get('opportunities', []):
            rows.append(f"- {item}")

        rows.append(f"\n## Threats ☠️🛑🚨☢︎💩☣︎")
        for item in self.response_conduct.get('threats', []):
            rows.append(f"- {item}")

        rows.append(f"\n## Recommendations 💡✅")
        for item in self.response_conduct.get('recommendations', []):
            rows.append(f"- {item}")

        rows.append(f"\n## Strategic Objectives 🎯🔭⛳🏅")
        for item in self.response_conduct.get('strategic_objectives', []):
            rows.append(f"- {item}")

        rows.append(f"\n## Assumptions 🤔🧠🔍")
        for item in self.response_conduct.get('assumptions', []):
            rows.append(f"- {item}")

        rows.append(f"\n## Missing Information 🧩🤷‍♂️🤷‍♀️")
        for item in self.response_conduct.get('missing_information', []):
            rows.append(f"- {item}")

        rows.append(f"\n## Questions 🙋❓💬📌")
        for item in self.response_conduct.get('user_questions', []):
            rows.append(f"- {item}")

        if include_metadata:
            rows.append(f"\n## Metadata 📊🔧💾")
            rows.append("```json")
            json_dict = self.metadata.copy()
            json_dict['duration_response_type'] = self.response_type['metadata']['duration']
            json_dict['duration_response_conduct'] = self.response_conduct['metadata']['duration']
            rows.append(json.dumps(json_dict, indent=2))
            rows.append("```")

        return "\n".join(rows)

if __name__ == "__main__":
    import logging
    from src.prompt.prompt_catalog import PromptCatalog
    from src.llm_factory import get_llm
    import os

    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler()
        ]
    )

    prompt_catalog = PromptCatalog()
    prompt_catalog.load(os.path.join(os.path.dirname(__file__), 'data', 'example_swot_prompt.jsonl'))
    prompt_item = prompt_catalog.find("427e5163-cefa-46e8-b1d0-eb12be270e19")
    if not prompt_item:
        raise ValueError("Prompt item not found.")
    query = prompt_item.prompt

    llm = get_llm("ollama-llama3.1")

    print(f"Query: {query}")
    result = SWOTAnalysis.execute(llm, query)

    print("\nJSON:")
    print(json.dumps(asdict(result), indent=2))

    print("\n\nMarkdown:")
    print(result.to_markdown(include_metadata=False))
