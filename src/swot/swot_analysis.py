"""
Perform a full SWOT analysis

Phase 1 - IdentifyPurpose, classify if this is this going to be a business/personal/other SWOT analysis
Phase 2 - Conduct the SWOT Analysis

PROMPT> python -m src.swot.swot_analysis
"""
import json
import time
import logging
from math import ceil
from dataclasses import dataclass, asdict
from src.assume.identify_purpose import IdentifyPurpose
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
    purpose: str
    purpose_detailed: str
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

        identify_purpose = IdentifyPurpose.execute(llm, query)
        json_response_type = identify_purpose.to_dict()
        logging.debug("IdentifyPurpose json " + json.dumps(json_response_type, indent=2))

        purpose = json_response_type['purpose']
        purpose_detailed = json_response_type['purpose_detailed']
        topic = json_response_type['topic']

        if purpose == 'business':
            system_prompt = CONDUCT_SWOT_ANALYSIS_BUSINESS_SYSTEM_PROMPT
        elif purpose == 'personal':
            system_prompt = CONDUCT_SWOT_ANALYSIS_PERSONAL_SYSTEM_PROMPT
        elif purpose == 'other':
            system_prompt = CONDUCT_SWOT_ANALYSIS_OTHER_SYSTEM_PROMPT
            system_prompt = system_prompt.replace("INSERT_USER_TOPIC_HERE", topic)
            system_prompt = system_prompt.replace("INSERT_USER_SWOTTYPEDETAILED_HERE", purpose_detailed)
        else:
            raise ValueError(f"Invalid purpose: {purpose}")
        
        logging.debug(f"Conducting SWOT analysis... purpose: {purpose}")
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
            topic=topic,
            purpose=purpose,
            purpose_detailed=purpose_detailed,
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

        rows.append(f"\n## Purpose")
        rows.append(f"{self.purpose}")

        rows.append(f"\n## Purpose detailed")
        rows.append(f"{self.purpose_detailed}")

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
    result = SWOTAnalysis.execute(llm, query)

    print("\nJSON:")
    print(json.dumps(asdict(result), indent=2))

    print("\n\nMarkdown:")
    print(result.to_markdown(include_metadata=False))
