"""
PROMPT> python -m src.expert.expert_orchestrator
"""
import logging
from llama_index.core.llms.llm import LLM
from src.expert.expert_finder import ExpertFinder
from src.expert.expert_criticism import ExpertCriticism
from src.expert.markdown_with_criticism_from_experts import markdown_rows_with_info_about_one_expert, markdown_rows_with_criticism_from_one_expert

logger = logging.getLogger(__name__)

class ExpertOrchestrator:
    def __init__(self):
        self.phase1_post_callback = None
        self.phase2_post_callback = None
        self.expert_finder: ExpertFinder = None
        self.expert_criticism_list: list[ExpertCriticism] = []
        self.max_expert_count = 2

    def execute(self, llm: LLM, query: str) -> None:
        logger.info("Finding experts that can provide criticism...")

        self.expert_finder = ExpertFinder.execute(llm, query)
        if self.phase1_post_callback:
            self.phase1_post_callback(self.expert_finder)

        expert_finder = self.expert_finder
        all_expert_list = expert_finder.expert_list
        all_expert_count = len(all_expert_list)

        expert_list_truncated = all_expert_list[:self.max_expert_count]
        expert_list_truncated_count = len(expert_list_truncated)

        if all_expert_count != expert_list_truncated_count:
            logger.info(f"Truncated expert list from {all_expert_count} to {expert_list_truncated_count} experts.")

        logger.info(f"Asking {expert_list_truncated_count} experts for criticism...")

        for expert_index, expert_dict in enumerate(expert_list_truncated):
            expert_copy = expert_dict.copy()
            expert_copy.pop('id')
            expert_title = expert_copy.get('title', 'Missing title')
            logger.info(f"Getting criticism from expert {expert_index + 1} of {expert_list_truncated_count}. expert_title: {expert_title}")
            system_prompt = ExpertCriticism.format_system(expert_dict)

            # IDEA: Cycle through the available LLM models, if the first one fails, try the next one. Currently it's done by the run_plan_pipeline.py, but it should be done here.
            # Doing it in the run_plan_pipeline. There are several llm invocations here, in case the LLM fails, then it quickly exhausts the available LLM models. Fragile approach.
            # Doing it here, and it will start out with the preferred LLM model, move on to the next one if it fails. 
            # For next expert, it will again start out with the preferred LLM model.
            # Thus doing it here, is more likely to succeed.

            # IDEA: If the expert file for expert_index already exist, then there is no need to run the LLM again.
            expert_criticism = ExpertCriticism.execute(llm, query, system_prompt)
            if self.phase2_post_callback:
                self.phase2_post_callback(expert_criticism, expert_index)
            self.expert_criticism_list.append(expert_criticism)

        logger.info(f"Finished collecting criticism from {expert_list_truncated_count} experts.")
    
    def to_markdown(self) -> str:
        rows = []
        rows.append("# Project Expert Review & Recommendations\n")
        rows.append("## A Compilation of Professional Feedback for Project Planning and Execution\n\n")

        number_of_experts_with_criticism = len(self.expert_criticism_list)
        for expert_index, expert_criticism in enumerate(self.expert_criticism_list):
            section_index = expert_index + 1
            if expert_index > 0:
                rows.append("\n---\n")
            expert_details = self.expert_finder.expert_list[expert_index]
            rows.extend(markdown_rows_with_info_about_one_expert(section_index, expert_details))
            rows.extend(markdown_rows_with_criticism_from_one_expert(section_index, expert_criticism.to_dict()))

        if number_of_experts_with_criticism != len(self.expert_finder.expert_list):
            rows.append("\n---\n")
            rows.append("# The following experts did not provide feedback:")
            for expert_index, expert_details in enumerate(self.expert_finder.expert_list):
                if expert_index < number_of_experts_with_criticism:
                    continue
                section_index = expert_index + 1
                rows.append("")
                rows.extend(markdown_rows_with_info_about_one_expert(section_index, expert_details))
        
        return "\n".join(rows)

if __name__ == "__main__":
    import logging
    from src.llm_factory import get_llm
    from src.plan.find_plan_prompt import find_plan_prompt
    import json

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler()
        ]
    )

    plan_prompt = find_plan_prompt("4dc34d55-0d0d-4e9d-92f4-23765f49dd29")

    llm = get_llm("ollama-llama3.1")
    # llm = get_llm("openrouter-paid-gemini-2.0-flash-001")
    # llm = get_llm("deepseek-chat")

    def phase1_post_callback(expert_finder: ExpertFinder) -> None:
        count = len(expert_finder.expert_list)
        d = expert_finder.to_dict(include_system_prompt=False, include_user_prompt=False)
        pretty = json.dumps(d, indent=2)
        print(f"Found {count} expert:\n{pretty}")

    def phase2_post_callback(expert_criticism: ExpertCriticism, expert_index: int) -> None:
        d = expert_criticism.to_dict(include_query=False)
        pretty = json.dumps(d, indent=2)
        print(f"Expert {expert_index + 1} criticism:\n{pretty}")

    orchestrator = ExpertOrchestrator()
    orchestrator.phase1_post_callback = phase1_post_callback
    orchestrator.phase2_post_callback = phase2_post_callback
    orchestrator.execute(llm, plan_prompt)
    print("\n\nMarkdown:")
    print(orchestrator.to_markdown())
