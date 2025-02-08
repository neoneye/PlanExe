"""
PROMPT> python -m src.assume.assumption_orchestrator
"""
import logging
from llama_index.core.llms.llm import LLM
from src.assume.make_assumptions import MakeAssumptions
from src.assume.distill_assumptions import DistillAssumptions
from src.format_json_for_use_in_query import format_json_for_use_in_query

logger = logging.getLogger(__name__)

class AssumptionOrchestrator:
    def __init__(self):
        self.phase1_post_callback = None
        self.phase2_post_callback = None
        self.make_assumptions: MakeAssumptions = None
        self.distill_assumptions: DistillAssumptions = None

    def execute(self, llm: LLM, query: str) -> None:
        logger.info("Making assumptions...")

        self.make_assumptions = MakeAssumptions.execute(llm, query)
        if self.phase1_post_callback:
            self.phase1_post_callback(self.make_assumptions)

        logger.info(f"Distilling assumptions...")

        assumptions_json_string = format_json_for_use_in_query(self.make_assumptions.assumptions)

        query2 = (
            f"{query}\n\n"
            f"assumption.json:\n{assumptions_json_string}"
        )
        self.distill_assumptions = DistillAssumptions.execute(llm, query2)
        if self.phase2_post_callback:
            self.phase2_post_callback(self.distill_assumptions)
    
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

    def phase1_post_callback(make_assumptions: MakeAssumptions) -> None:
        count = len(make_assumptions.assumptions)
        d = make_assumptions.to_dict(include_system_prompt=False, include_user_prompt=False)
        pretty = json.dumps(d, indent=2)
        print(f"MakeAssumptions: Made {count} assumptions:\n{pretty}")

    def phase2_post_callback(distill_assumptions: DistillAssumptions) -> None:
        d = distill_assumptions.to_dict(include_system_prompt=False, include_user_prompt=False)
        pretty = json.dumps(d, indent=2)
        print(f"DistillAssumptions:\n{pretty}")

    orchestrator = AssumptionOrchestrator()
    orchestrator.phase1_post_callback = phase1_post_callback
    orchestrator.phase2_post_callback = phase2_post_callback
    orchestrator.execute(llm, plan_prompt)
