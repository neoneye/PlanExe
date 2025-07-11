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
    id: str = Field(description="Unique identifier for the lever.")
    name: str = Field(description="Name of this lever.")
    consequences: str = Field(description="Likely second-order effects of pulling this lever.")
    options: List[str] = Field(description="Options for this lever.")
    review: str = Field(description="Critique of this lever.")

class LeverAssessment(BaseModel):
    lever_id: str = Field(description="ID of the lever being assessed.")
    impact_score: int = Field(
        description="Strategic impact score (1-5)",
        ge=1,
        le=5
    )
    controllability_score: int = Field(
        description="Controllability score (1-5)",
        ge=1,
        le=5
    )
    differentiation_score: int = Field(
        description="Differentiation score (1-5)",
        ge=1,
        le=5
    )
    leverage_score: int = Field(
        description="Leverage score (1-5)",
        ge=1,
        le=5
    )
    risk_score: int = Field(
        description="Risk exposure score (1-5)",
        ge=1,
        le=5
    )
    assessment_note: str = Field(
        description="Brief justification for scores (20 words)."
    )

class NarrowedLevers(BaseModel):
    all_assessments: List[LeverAssessment] = Field(
        description="Assessment of all levers against the 5 criteria."
    )
    selected_lever_ids: List[str] = Field(
        description="4-5 lever IDs selected as vital using 80/20 principle."
    )
    summary: str = Field(
        description="Strategic justification for selection and expected impact."
    )
    
    @model_validator(mode='after')
    def validate_lever_count(self) -> 'NarrowedLevers':
        """Ensure exactly 4-5 levers are selected"""
        lever_count = len(self.selected_lever_ids)
        if lever_count < 4 or lever_count > 5:
            raise ValueError(f"Must select 4-5 levers, got {lever_count}")
        return self

NARROW_DOWN_LEVERS_SYSTEM_PROMPT = """
You are an expert strategic analyst applying the 80/20 Pareto principle. Follow this 3-step process:

### STEP 1: ASSESS ALL LEVERS
For each lever, score against these criteria (1-5):
1. 🎯 Strategic Impact: Effect on core space manufacturing outcomes
2. 🕹️ Controllability: Our ability to influence within 20-year timeline
3. 🚀 Differentiation: Unique advantage for space-based manufacturing
4. 🔄 Leverage: Value relative to EUR 200B budget
5. ⚠️ Risk Exposure: Effect on key technical/schedule risks

### STEP 2: SELECT VITAL LEVERS
- Apply 80/20 principle to select EXACTLY 4-5 most promising lever IDs
- Include brief justification for each selection
- MUST NOT select more than 5 levers

### STEP 3: STRATEGIC SUMMARY
Write 100-word summary explaining:
- Why these levers represent the vital 20%
- How they address core tensions in space-based manufacturing
- Expected benefits for the EUR 200B initiative

### OUTPUT FORMAT
{
  "all_assessments": [
    {
      "lever_id": "Lever-1",
      "impact_score": 5,
      "controllability_score": 4,
      "differentiation_score": 5,
      "leverage_score": 4,
      "risk_score": 3,
      "assessment_note": "Brief justification..."
    },
    ... (all levers)
  ],
  "selected_lever_ids": ["Lever-1", "Lever-3", ...],
  "summary": "Strategic justification..."
}
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
        
        # Aggregate levers and ensure IDs
        all_levers = []
        for response in lever_responses:
            if "levers" in response:
                for i, lever in enumerate(response["levers"]):
                    # Ensure every lever has an ID
                    if "id" not in lever:
                        lever["id"] = f"Lever-{i+1}"
                    all_levers.append(lever)
        
        if len(all_levers) < 5:
            logger.warning(f"Only {len(all_levers)} levers found for narrowing")
        
        # Prepare prompts
        system_prompt = NARROW_DOWN_LEVERS_SYSTEM_PROMPT.strip()
        
        lever_context = "\n\n".join(
            f"Lever ID: {lever['id']}\nName: {lever['name']}\n"
            f"Consequences: {lever['consequences']}\n"
            f"Options: {', '.join(lever['options'])}\n"
            f"Review: {lever['review']}"
            for lever in all_levers
        )
        
        user_message = (
            f"## SPACE MANUFACTURING INITIATIVE CONTEXT\n{user_prompt}\n\n"
            f"## {len(all_levers)} POTENTIAL LEVERS\n{lever_context}\n\n"
            "## EXECUTION INSTRUCTIONS\n"
            "1. FIRST: Score ALL levers against all 5 criteria\n"
            "2. SECOND: Select EXACTLY 4-5 lever IDs using 80/20 principle\n"
            "3. THIRD: Write strategic summary\n"
            "4. OUTPUT: Use required JSON format with all 3 components"
        )
        
        # Prepare messages
        chat_messages = [
            ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
            ChatMessage(role=MessageRole.USER, content=user_message)
        ]
        
        # Execute with retries for validation
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
                        content=f"CRITICAL: Previous response had incorrect lever count. You MUST select EXACTLY 4 or 5 levers."
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
        response = self.response
        
        print("\n📊 COMPLETE LEVER ASSESSMENTS")
        print("┌─────────────┬───────────────┬───────┬───────┬───────┬───────┬───────┐")
        print("│ Lever ID    │ Name          │ Imp.  │ Ctrl. │ Diff. │ Lev.  │ Risk  │")
        print("├─────────────┼───────────────┼───────┼───────┼───────┼───────┼───────┤")
        
        # Create lookup for lever details
        lever_map = {lever['id']: lever for lever in self.aggregated_levers}
        
        for assessment in response["all_assessments"]:
            lever_id = assessment["lever_id"]
            lever = lever_map.get(lever_id, {"name": "Unknown"})
            name = lever["name"][:12] + '...' if len(lever["name"]) > 15 else lever["name"]
            
            print(f"│ {lever_id.ljust(12)}│ {name.ljust(14)}│   {assessment['impact_score']}   │"
                  f"   {assessment['controllability_score']}   │   {assessment['differentiation_score']}   │"
                  f"   {assessment['leverage_score']}   │   {assessment['risk_score']}   │")
            print("├─────────────┼───────────────┼───────┼───────┼───────┼───────┼───────┤")
        print("└─────────────┴───────────────┴───────┴───────┴───────┴───────┴───────┘")
        
        # Print selected levers
        print("\n🔝 SELECTED VITAL LEVERS (4-5)")
        print("┌─────────────┬───────────────────────────────────────┐")
        print("│ Lever ID    │ Name                                  │")
        print("├─────────────┼───────────────────────────────────────┤")
        for lever_id in response["selected_lever_ids"]:
            lever = lever_map.get(lever_id, {"name": "Unknown"})
            name = lever["name"][:35] + '...' if len(lever["name"]) > 38 else lever["name"]
            print(f"│ {lever_id.ljust(12)}│ {name.ljust(37)} │")
            print("├─────────────┼───────────────────────────────────────┤")
        print("└─────────────┴───────────────────────────────────────┘")
        
        # Print summary
        print(f"\n📝 STRATEGIC SUMMARY:\n{response['summary']}")

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