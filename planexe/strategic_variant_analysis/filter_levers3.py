"""
This was generated with DeepSeek R1.

PROMPT> python -m planexe.strategic_variant_analysis.filter_levers3
"""
import json
import os
import logging
from typing import List
from dataclasses import dataclass
from pydantic import BaseModel, Field
from llama_index.core.llms import LLM, ChatMessage, MessageRole
from planexe.llm_util.llm_executor import LLMExecutor, PipelineStopRequested

logger = logging.getLogger(__name__)

class Lever(BaseModel):
    lever_index: int = Field(description="Index of this lever.")
    name: str = Field(description="Name of this lever.")
    consequences: str = Field(description="Likely second-order effects of pulling this lever.")
    options: List[str] = Field(description="Options for this lever.")
    review_lever: str = Field(description="Critique of this lever.")

class SelectedLever(Lever):
    selection_reason: str = Field(
        description="Reason for selecting this lever as vital, linking to strategic impact."
    )

class NarrowedLevers(BaseModel):
    selected_levers: List[SelectedLever] = Field(
        description="4-5 vital levers selected using 80/20 principle."
    )
    summary: str = Field(
        description="Strategic justification for lever selection and expected impact."
    )

NARROW_DOWN_LEVERS_SYSTEM_PROMPT = """
You are an expert strategic analyst applying the 80/20 Pareto principle. Your task is to identify the vital few levers (4-5) that will drive ~80% of strategic impact from a larger set of potential levers.

**Selection Criteria:**
1. **Strategic Impact**: How significantly does this lever affect core project outcomes?
2. **Controllability**: Can we realistically influence this lever?
3. **Differentiation**: Does it create unique competitive advantage?
4. **Leverage**: Does it unlock disproportionate value relative to effort?
5. **Risk Exposure**: How does it affect key project risks?

**Output Requirements:**
- Select EXACTLY 4-5 levers (no more, no less)
- For each selected lever:
  • Preserve original fields (name, consequences, options, review_lever)
  • Add `selection_reason` justifying its strategic importance
- Write a 100-word summary explaining:
  • Why these levers represent the vital 20%
  • How they address core project tensions
  • Expected strategic benefits

**Prohibitions:**
- NO selection based on alphabetical order
- NO arbitrary preference for first/last items
- NO selection without explicit strategic justification
"""

@dataclass
class NarrowDownLevers:
    system_prompt: str
    user_prompt: str
    aggregated_levers: List[dict]
    response: dict
    metadata: dict

    @classmethod
    def execute(
        cls,
        llm_executor: LLMExecutor,
        user_prompt: str,
        lever_responses: List[dict]
    ) -> 'NarrowDownLevers':
        # Validate inputs
        if not isinstance(llm_executor, LLMExecutor):
            raise ValueError("Invalid LLMExecutor instance.")
        if not isinstance(user_prompt, str):
            raise ValueError("Invalid user_prompt.")
        
        # Aggregate all levers from multiple responses
        all_levers = []
        for response in lever_responses:
            if "levers" in response:
                all_levers.extend(response["levers"])
        
        if len(all_levers) < 5:
            logger.warning(f"Only {len(all_levers)} levers found for narrowing")
        
        # Prepare system prompt
        system_prompt = NARROW_DOWN_LEVERS_SYSTEM_PROMPT.strip()
        
        # Build user message with context
        lever_context = "\n\n".join(
            f"Lever {idx}: {json.dumps(lever)}" 
            for idx, lever in enumerate(all_levers, 1)
        )
        
        user_message = (
            f"Project Context:\n{user_prompt}\n\n"
            f"Potential Levers ({len(all_levers)} total):\n{lever_context}\n\n"
            "INSTRUCTIONS:\n"
            "1. Select 4-5 vital levers using 80/20 principle\n"
            "2. For each selected lever, add 'selection_reason'\n"
            "3. Write strategic summary"
        )
        
        # Prepare chat messages
        chat_messages = [
            ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
            ChatMessage(role=MessageRole.USER, content=user_message)
        ]
        
        # Execute LLM call
        try:
            def execute_function(llm: LLM) -> dict:
                sllm = llm.as_structured_llm(NarrowedLevers)
                chat_response = sllm.chat(chat_messages)
                metadata = dict(llm.metadata)
                metadata["llm_classname"] = llm.class_name()

                return {
                    "chat_response": chat_response,
                    "metadata": metadata
                }
            
            result = llm_executor.run(execute_function)
        except PipelineStopRequested:
            raise
        except Exception as e:
            logger.error("LLM narrowing failed", exc_info=True)
            raise ValueError("Lever narrowing failed") from e
        
        # Prepare result
        return NarrowDownLevers(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            aggregated_levers=all_levers,
            response=result["chat_response"].raw.model_dump(),
            metadata=result["metadata"]
        )
    
    def to_dict(self) -> dict:
        return {
            "system_prompt": self.system_prompt,
            "user_prompt": self.user_prompt,
            "aggregated_levers": self.aggregated_levers,
            "narrowed_response": self.response,
            "metadata": self.metadata
        }
    
    def save(self, file_path: str) -> None:
        with open(file_path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)

def parse_test_data(file_content: str) -> tuple[str, list]:
    """Extract user prompt and lever list from test data file"""
    # Split content into plan and levers sections
    plan_marker = "file: 'plan.txt':\n"
    levers_marker = "file: 'potential_levers.json':\n"
    
    plan_start = file_content.find(plan_marker) + len(plan_marker)
    plan_end = file_content.find(levers_marker)
    user_prompt = file_content[plan_start:plan_end].strip()
    
    levers_start = file_content.find(levers_marker) + len(levers_marker)
    levers_json = file_content[levers_start:].strip()
    
    # Parse JSON and structure as lever_responses
    lever_list = json.loads(levers_json)
    lever_responses = [{"levers": lever_list}]
    
    return user_prompt, lever_responses

if __name__ == "__main__":
    from planexe.llm_util.llm_executor import LLMModelFromName
    
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Load test data
    test_data_file = "planexe/strategic_variant_analysis/test_data/identify_potential_levers_19dc0718-3df7-48e3-b06d-e2c664ecc07d.txt"
    if not os.path.exists(test_data_file):
        logger.error(f"Test data file not found at: {test_data_file}")
        exit(1)

    with open(test_data_file, 'r', encoding='utf-8') as f:
        test_data_content = f.read()
    
    # Parse test data
    user_prompt, lever_responses = parse_test_data(test_data_content)
    logger.info(f"Loaded project plan with {len(lever_responses[0]['levers'])} potential levers")
    
    # Set up LLM
    model_names = ["ollama-llama3.1"]
    llm_models = LLMModelFromName.from_names(model_names)
    llm_executor = LLMExecutor(llm_models=llm_models)
    
    # Run narrowing process
    logger.info("Narrowing levers to vital few using 80/20 principle...")
    result = NarrowDownLevers.execute(
        llm_executor=llm_executor,
        user_prompt=user_prompt,
        lever_responses=lever_responses
    )
    
    # Save results
    output_file = "narrowed_levers.json"
    result.save(output_file)
    logger.info(f"Saved narrowed levers to {output_file}")
    
    # Print results
    print("\nSelected Vital Levers:")
    for lever in result.response["selected_levers"]:
        print(f"\n- {lever['name']}")
        print(f"  Reason: {lever['selection_reason']}")
    
    print(f"\nSummary: {result.response['summary']}")