"""
This was generated with Kimi K2.

Lever-interaction analyser.

Usage
-----
python -m planexe.strategic_variant_analysis.analyze_interactions2 \
    --plan_file planexe/strategic_variant_analysis/test_data/plan_19dc0718-3df7-48e3-b06d-e2c664ecc07d.txt \
    --vital_levers_file vital_levers_from_test_data.json \
    --out_file interactions_v2.json
"""
from __future__ import annotations

import json
import logging
import os
from enum import Enum
from typing import List
from dataclasses import dataclass

from pydantic import BaseModel, Field
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.llms.llm import LLM

from planexe.llm_util.llm_executor import LLMExecutor, LLMModelFromName


# ------------------------------------------------------------------------------
# Pydantic data-model
# ------------------------------------------------------------------------------

class EdgeType(str, Enum):
    SYNERGY = "synergy"
    CONFLICT = "conflict"
    NEUTRAL = "neutral"


class InteractionEffect(BaseModel):
    """
    A directed, causal edge between two levers.
    """
    source: str = Field(..., description="Name of the upstream lever")
    target: str = Field(..., description="Name of the downstream lever")
    edge_type: EdgeType
    magnitude: int = Field(..., ge=-5, le=5,
                           description="-5 strong conflict … +5 strong synergy")
    mechanism: str = Field(..., max_length=120,
                           description="One-sentence causal explanation, citing explicit options")


class InteractionGraph(BaseModel):
    """
    The LLM’s mini causal graph plus a plain-English summary.
    """
    edges: List[InteractionEffect] = Field(...,
                                           description="≤6 edges (2-3 lever pairs / triplets)")
    summary: str = Field(..., max_length=180,
                         description="One-sentence synthesis of the core strategic tension")


# ------------------------------------------------------------------------------
# LLM prompt
# ------------------------------------------------------------------------------

SYSTEM_PROMPT = """
You are a systems-thinking strategist. Your task is to build a **small causal graph** that exposes the strongest cross-lever effects among the provided vital levers.

RULES
1. Nodes: only the vital levers supplied by the user.
2. Edges:
   • Produce **no more than 6 edges** (≈2–3 lever pairs/triplets).  
   • Each edge must reference the **exact lever options** that create the effect.  
   • Magnitude: integer from -5 (strong conflict) to +5 (strong synergy).  
3. Mechanism: one sentence explaining *how* the source option influences the target option.  
4. Summary: one sentence capturing the **single most important tension or opportunity** revealed by the graph.  
5. Output only valid JSON matching the schema.
"""

# ------------------------------------------------------------------------------
# Runner
# ------------------------------------------------------------------------------
@dataclass
class InteractionAnalysisResult:
    interaction_graph: InteractionGraph
    metadata: dict

    def save(self, file_path: str) -> None:
        with open(file_path, "w") as f:
            json.dump(
                {
                    "interaction_graph": self.interaction_graph.model_dump(),
                    "metadata": self.metadata,
                },
                f,
                indent=2,
            )

def run_interaction_analysis(
    llm_executor: LLMExecutor,
    project_plan: str,
    vital_levers: list[dict],
) -> InteractionAnalysisResult:
    """
    vital_levers: list of dicts with keys: name, options (list[str])
    """
    # Build prompt
    lever_text = "\n\n".join(
        f"**{lever['name']}**\nOptions: {lever['options']}" for lever in vital_levers
    )
    user_prompt = f"Project Plan:\n{project_plan}\n\nVital Levers:\n{lever_text}"

    messages = [
        ChatMessage(role=MessageRole.SYSTEM, content=SYSTEM_PROMPT.strip()),
        ChatMessage(role=MessageRole.USER, content=user_prompt),
    ]

    def execute_function(llm) -> dict:
        sllm = llm.as_structured_llm(InteractionGraph)
        response = sllm.chat(messages)
        metadata = dict(llm.metadata)
        metadata["llm_classname"] = llm.class_name()
        return {"graph": response.raw, "metadata": metadata}        

    result = llm_executor.run(execute_function)
    return InteractionAnalysisResult(
        interaction_graph=result["graph"],
        metadata=result["metadata"],
    )


# ------------------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------------------
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
    vital_levers = vital_levers_raw['levers']

    model_names = ["ollama-llama3.1"]
    llm_models = LLMModelFromName.from_names(model_names)
    llm_executor = LLMExecutor(llm_models=llm_models)

    result = run_interaction_analysis(llm_executor, project_plan, vital_levers)
    result.save(args.out_file)
    logging.info("Interactions saved to %s", args.out_file)