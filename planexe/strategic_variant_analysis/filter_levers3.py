"""
This was generated with DeepSeek R1.

PROMPT> python -m planexe.strategic_variant_analysis.filter_levers3
"""
import json
import os
import logging
from typing import List
from dataclasses import dataclass
from pydantic import BaseModel, Field, model_validator
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
        description="Reason for selection linking to strategic impact and criteria."
    )
    impact_score: int = Field(
        description="Strategic impact score (1-5) based on criteria.",
        ge=1,
        le=5
    )
    controllability_score: int = Field(
        description="Controllability score (1-5) based on criteria.",
        ge=1,
        le=5
    )

class NarrowedLevers(BaseModel):
    selected_levers: List[SelectedLever] = Field(
        description="4-5 vital levers selected using 80/20 principle."
    )
    summary: str = Field(
        description="Strategic justification for selection and expected impact."
    )
    
    @model_validator(mode='after')
    def validate_lever_count(self) -> 'NarrowedLevers':
        """Ensure exactly 4-5 levers are selected"""
        lever_count = len(self.selected_levers)
        if lever_count < 4 or lever_count > 5:
            raise ValueError(f"Must select 4-5 levers, got {lever_count}")
        return self

NARROW_DOWN_LEVERS_SYSTEM_PROMPT = """
You are an expert strategic analyst applying the 80/20 Pareto principle. Identify the vital 4-5 levers that will drive 80% of strategic impact.

**CRITICAL: You MUST select EXACTLY 4 or 5 levers.**
- Selecting fewer than 4 or more than 5 will cause system failure
- System will reject any response with incorrect lever count

**Selection Criteria (Score 1-5 for each):**
1. 🎯 Strategic Impact: Effect on core outcomes
2. 🕹️ Controllability: Our ability to influence
3. 🚀 Differentiation: Unique competitive advantage
4. 🔄 Leverage: Value relative to effort
5. ⚠️ Risk Exposure: Effect on key risks

**Output Requirements:**
- For each selected lever:
  • Preserve original fields
  • Add `selection_reason` linking to specific criteria and project context
  • Add impact_score (1-5) and controllability_score (1-5)
- Write 100-word summary explaining:
  • Why these represent the vital 20%
  • How they address core tensions
  • Expected strategic benefits

**Prohibitions:**
- NO selection without explicit scoring against all 5 criteria
- NO generic reasons - must reference project specifics
- NO exceeding 5 levers under any circumstances
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
        # Input validation
        if not isinstance(llm_executor, LLMExecutor):
            raise ValueError("Invalid LLMExecutor instance.")
        if not user_prompt or not isinstance(user_prompt, str):
            raise ValueError("Invalid user_prompt.")
        
        # Aggregate levers
        all_levers = []
        for response in lever_responses:
            if "levers" in response:
                all_levers.extend(response["levers"])
        
        if len(all_levers) < 5:
            logger.warning(f"Only {len(all_levers)} levers found for narrowing")
        
        # Prepare prompts
        system_prompt = NARROW_DOWN_LEVERS_SYSTEM_PROMPT.strip()
        
        lever_context = "\n\n".join(
            f"Lever {idx}: {json.dumps(lever)}" 
            for idx, lever in enumerate(all_levers, 1)
        )
        
        user_message = (
            f"## Project Context\n{user_prompt}\n\n"
            f"## {len(all_levers)} Potential Levers\n{lever_context}\n\n"
            "## Instructions\n"
            "1. Select EXACTLY 4-5 vital levers using 80/20 principle\n"
            "2. For each: Add selection_reason, impact_score, controllability_score\n"
            "3. Write strategic summary\n"
            "4. CRITICAL: Select EXACTLY 4-5 levers - system will fail otherwise"
        )
        
        # Prepare messages
        chat_messages = [
            ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
            ChatMessage(role=MessageRole.USER, content=user_message)
        ]
        
        # Execute with retries for lever count validation
        max_retries = 3
        for attempt in range(max_retries):
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
                return NarrowDownLevers(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    aggregated_levers=all_levers,
                    response=result["chat_response"].raw.model_dump(),
                    metadata=result["metadata"]
                )
            except ValueError as ve:
                if "Must select 4-5 levers" in str(ve):
                    logger.warning(f"Lever count violation (attempt {attempt+1}/{max_retries}): {ve}")
                    if attempt == max_retries - 1:
                        raise
                    # Add warning to prompt for next attempt
                    chat_messages.append(ChatMessage(
                        role=MessageRole.SYSTEM,
                        content=f"CRITICAL ERROR: Previous response had incorrect lever count. You MUST select EXACTLY 4 or 5 levers. Failure to comply will terminate the process."
                    ))
                else:
                    raise
            except PipelineStopRequested:
                raise
            except Exception as e:
                logger.error("LLM narrowing failed", exc_info=True)
                raise ValueError("Lever narrowing failed") from e
        
        # Should never reach here due to retry logic
        raise RuntimeError("Unexpected state after retry loop")

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

    def print_results(self) -> None:
        """Print formatted results with strategic scoring"""
        narrowed = self.response
        
        print("\n🔥 Selected Vital Levers (4-5) 🔥")
        print(f"Strategic Impact Summary: {narrowed['summary']}\n")
        
        print("┌───────────────────────────────┬───────┬───────┐")
        print("│ Lever                         │ Impact│ Control│")
        print("├───────────────────────────────┼───────┼───────┤")
        for lever in narrowed["selected_levers"]:
            name = lever['name'][:25] + '...' if len(lever['name']) > 28 else lever['name']
            print(f"│ {name.ljust(30)}│   {lever['impact_score']}   │   {lever['controllability_score']}   │")
            print(f"├───────────────────────────────┼───────┼───────┤")
        print("└───────────────────────────────┴───────┴───────┘\n")
        
        print("🧠 Selection Reasoning:")
        for lever in narrowed["selected_levers"]:
            print(f"\n🔹 {lever['name']}")
            print(f"   Reason: {lever['selection_reason']}")
            print(f"   Options: {', '.join(lever['options'][:3])}")

def parse_test_data(file_content: str) -> tuple[str, list]:
    """Extract user prompt and lever list from test data file"""
    plan_marker = "file: 'plan.txt':\n"
    levers_marker = "file: 'potential_levers.json':\n"
    
    plan_start = file_content.find(plan_marker) + len(plan_marker)
    plan_end = file_content.find(levers_marker)
    user_prompt = file_content[plan_start:plan_end].strip()
    
    levers_start = file_content.find(levers_marker) + len(levers_marker)
    levers_json = file_content[levers_start:].strip()
    
    lever_list = json.loads(levers_json)
    lever_responses = [{"levers": lever_list}]
    
    return user_prompt, lever_responses

if __name__ == "__main__":
    from planexe.llm_util.llm_executor import LLMModelFromName
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Load test data
    test_data_file = "planexe/strategic_variant_analysis/test_data/identify_potential_levers_19dc0718-3df7-48e3-b06d-e2c664ecc07d.txt"
    if not os.path.exists(test_data_file):
        logger.error(f"Test data not found: {test_data_file}")
        exit(1)

    with open(test_data_file, 'r', encoding='utf-8') as f:
        test_data_content = f.read()
    
    # Parse test data
    user_prompt, lever_responses = parse_test_data(test_data_content)
    logger.info(f"Loaded project with {len(lever_responses[0]['levers'])} potential levers")
    
    # Configure LLM
    model_names = ["ollama-llama3.1"]
    llm_models = LLMModelFromName.from_names(model_names)
    llm_executor = LLMExecutor(llm_models=llm_models)
    
    # Execute narrowing
    logger.info("Narrowing levers to 4-5 vital ones with 80/20 principle...")
    try:
        result = NarrowDownLevers.execute(
            llm_executor=llm_executor,
            user_prompt=user_prompt,
            lever_responses=lever_responses
        )
    except ValueError as e:
        logger.error(f"Failed to narrow levers after retries: {e}")
        exit(1)
    
    # Save and display results
    output_file = "narrowed_levers.json"
    result.save(output_file)
    logger.info(f"Saved narrowed levers to {output_file}")
    
    # Print formatted results
    result.print_results()