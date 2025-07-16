"""
This was generated with o4-mini-high.

PROMPT> python -m planexe.strategic_variant_analysis.analyze_interactions3 \
    --plan_file planexe/strategic_variant_analysis/test_data/plan_19dc0718-3df7-48e3-b06d-e2c664ecc07d.txt \
    --vital_levers_file planexe/strategic_variant_analysis/test_data/identify_potential_levers_19dc0718-3df7-48e3-b06d-e2c664ecc07d.json \
    --out_file interactions_v3.json
"""
import json
import logging
from pathlib import Path
from typing import List, Tuple, Dict

from pydantic import BaseModel, Field
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.llms.llm import LLM
from planexe.llm_util.llm_executor import LLMExecutor, LLMModelFromName

# System prompt guiding the LLM
SYSTEM_PROMPT = (
    "You are a strategic analysis assistant. "
    "Given an idea description and a set of vital levers, analyze each pairwise interaction. "
    "For each pair, identify whether they exhibit 'synergy', 'antagonism', or 'neutral' interaction, "
    "and provide a brief rationale. Output only valid JSON matching the schema."
)


class InteractionEffect(BaseModel):
    """
    Structured representation of the interaction effect between a pair of levers.
    """
    lever_ids: Tuple[str, str] = Field(
        ..., description="Pair of lever IDs involved in the interaction"
    )
    interaction_type: str = Field(
        ..., description="Type of interaction: 'synergy', 'antagonism', or 'neutral'"
    )
    description: str = Field(
        ..., description="Brief explanation of the interaction"
    )


def analyze_interactions(executor: LLMExecutor, idea: str, levers: List[Dict]) -> List[InteractionEffect]:
    """
    Analyze interaction effects between each unique pair of levers using in-context learning.
    """
    effects: List[InteractionEffect] = []

    for i in range(len(levers)):
        for j in range(i + 1, len(levers)):
            if len(effects) > 5:
                break
            a = levers[i]
            b = levers[j]
            user_prompt = (
                f"Idea: {idea}\n\n"
                f"Lever A (ID: {a['id']}, Name: {a['name']})\n"
                f"- Options: {a.get('options')}\n"
                f"- Consequences: {a.get('consequences')}\n\n"
                f"Lever B (ID: {b['id']}, Name: {b['name']})\n"
                f"- Options: {b.get('options')}\n"
                f"- Consequences: {b.get('consequences')}\n\n"
                "Respond with only a JSON object matching InteractionEffect schema."
            )

            messages = [
                ChatMessage(role=MessageRole.SYSTEM, content=SYSTEM_PROMPT.strip()),
                ChatMessage(role=MessageRole.USER, content=user_prompt),
            ]

            def execute_function(llm: LLM) -> dict:
                sllm = llm.as_structured_llm(InteractionEffect)
                response = sllm.chat(messages)
                return {"effect": response.raw}

            result = executor.run(execute_function)
            effect = result["effect"]

            effects.append(effect)
    return effects


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Identify lever interactions v2")
    parser.add_argument("--plan_file", required=True)
    parser.add_argument("--vital_levers_file", required=True)
    parser.add_argument("--out_file", default="interactions_v2.json")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    # Load project plan
    with open(args.plan_file, encoding="utf-8") as f:
        project_plan = f.read().strip()

    # Load vital levers (expecting JSON: [ {"name": ..., "options": [...]}, ... ])
    with open(args.vital_levers_file, encoding="utf-8") as f:
        vital_levers_raw = json.load(f)
    vital_levers = vital_levers_raw #['levers']

    model_names = ["ollama-llama3.1"]
    llm_models = LLMModelFromName.from_names(model_names)
    llm_executor = LLMExecutor(llm_models=llm_models)

    # Read JSON from stdin, execute, and print results
    result = analyze_interactions(llm_executor, project_plan, vital_levers)
    # Convert Pydantic models to dictionaries for JSON serialization
    result_dicts = [effect.model_dump() for effect in result]
    print(json.dumps(result_dicts, ensure_ascii=False, indent=2))