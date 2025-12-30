"""
Present the scenarios in a human readable format.
Where the selected scenario is presented first, and the rejected scenarios at the end.

Input files:
- candidate_scenarios_4dc34d55-0d0d-4e9d-92f4-23765f49dd29.json
- selected_scenario_4dc34d55-0d0d-4e9d-92f4-23765f49dd29.json

Output file:
- scenarios_markdown_4dc34d55-0d0d-4e9d-92f4-23765f49dd29.md

PROMPT> python -m worker_plan_internal.lever.scenarios_markdown
"""
import logging
from pydantic import BaseModel
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class Scenario(BaseModel):
    """Represents a single scenario from the candidate_scenarios.py module."""
    scenario_name: str
    strategic_logic: str
    lever_settings: Dict[str, str]

class ScenarioAssessment(BaseModel):
    """Represents the assessment of a single scenario from the select_scenario.py module."""
    scenario_name: str
    fit_score: int
    fit_assessment: str

class PlanCharacteristics(BaseModel):
    """Represents the plan characteristics from the select_scenario.py module."""
    ambition_and_scale: str
    risk_and_novelty: str
    complexity_and_constraints: str
    domain_and_tone: str
    holistic_profile_of_the_plan: str

class FinalChoice(BaseModel):
    """Represents the final scenario choice from the select_scenario.py module."""
    chosen_scenario_name: str
    justification: str

class ScenariosMarkdown:
    def __init__(self, scenarios: List[Dict[str, Any]], plan_characteristics: Dict[str, Any], scenario_assessments: List[Dict[str, Any]], final_choice: Dict[str, Any]):
        # Convert dictionaries to Pydantic models
        self.scenarios = [Scenario(**scenario) for scenario in scenarios]
        self.plan_characteristics = PlanCharacteristics(**plan_characteristics)
        self.scenario_assessments = [ScenarioAssessment(**assessment) for assessment in scenario_assessments]
        self.final_choice = FinalChoice(**final_choice)
        
        # Create lookup for assessments
        self.assessment_lookup = {assessment.scenario_name: assessment for assessment in self.scenario_assessments}
    
    def to_markdown(self) -> str:
        """Generate markdown content with selected scenario first, then rejected scenarios."""
        rows = []
        
        # Add title
        rows.append("# Choosing Our Strategic Path")

        # Add plan characteristics section
        rows.append("## The Strategic Context")
        rows.append("Understanding the core ambitions and constraints that guide our decision.\n")
        
        rows.append(f"**Ambition and Scale:** {self.plan_characteristics.ambition_and_scale}\n")
        rows.append(f"**Risk and Novelty:** {self.plan_characteristics.risk_and_novelty}\n")
        rows.append(f"**Complexity and Constraints:** {self.plan_characteristics.complexity_and_constraints}\n")
        rows.append(f"**Domain and Tone:** {self.plan_characteristics.domain_and_tone}\n")
        rows.append(f"**Holistic Profile:** {self.plan_characteristics.holistic_profile_of_the_plan}\n")
        
        # Add selected scenario section
        rows.append("---")
        rows.append("## The Path Forward")
        rows.append("This scenario aligns best with the project's characteristics and goals.\n")
        
        selected_scenario = next((s for s in self.scenarios if s.scenario_name == self.final_choice.chosen_scenario_name), None)
        if selected_scenario:
            rows.append(f"### {selected_scenario.scenario_name}")
            rows.append(f"**Strategic Logic:** {selected_scenario.strategic_logic}\n")
            
            # Add assessment if available
            if selected_scenario.scenario_name in self.assessment_lookup:
                assessment = self.assessment_lookup[selected_scenario.scenario_name]
                rows.append(f"**Fit Score:** {assessment.fit_score}/10\n")
                rows.append(f"**Why This Path Was Chosen:** {assessment.fit_assessment}\n")
            
            rows.append("**Key Strategic Decisions:**\n")
            for lever_name, lever_setting in selected_scenario.lever_settings.items():
                rows.append(f"- **{lever_name}:** {lever_setting}")
            rows.append("")
            
            rows.append("**The Decisive Factors:**\n")
            rows.append(self.final_choice.justification)
            rows.append("")
        
        # Add rejected scenarios section
        rows.append("---")
        rows.append("## Alternative Paths")
        
        for scenario in self.scenarios:
            if scenario.scenario_name != self.final_choice.chosen_scenario_name:
                rows.append(f"### {scenario.scenario_name}")
                rows.append(f"**Strategic Logic:** {scenario.strategic_logic}\n")
                
                # Add assessment if available
                if scenario.scenario_name in self.assessment_lookup:
                    assessment = self.assessment_lookup[scenario.scenario_name]
                    rows.append(f"**Fit Score:** {assessment.fit_score}/10\n")
                    rows.append(f"**Assessment of this Path:** {assessment.fit_assessment}\n")
                
                rows.append("**Key Strategic Decisions:**\n")
                for lever_name, lever_setting in scenario.lever_settings.items():
                    rows.append(f"- **{lever_name}:** {lever_setting}")
                rows.append("")
        
        return "\n".join(rows)
    
    def save_markdown(self, filename: str):
        """Save the markdown content to a file."""
        markdown_content = self.to_markdown()
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(markdown_content)

if __name__ == "__main__":
    from worker_plan_internal.prompt.prompt_catalog import PromptCatalog
    import os
    import json

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    prompt_catalog = PromptCatalog()
    prompt_catalog.load_simple_plan_prompts()

    prompt_id = "4dc34d55-0d0d-4e9d-92f4-23765f49dd29"
    prompt_item = prompt_catalog.find(prompt_id)
    if not prompt_item:
        raise ValueError("Prompt item not found.")
    project_plan = prompt_item.prompt

    candidate_scenarios_filename = f"candidate_scenarios_{prompt_id}.json"
    selected_scenario_filename = f"selected_scenario_{prompt_id}.json"

    # Load the candidate scenarios
    candidate_scenarios_file = os.path.join(os.path.dirname(__file__), 'test_data', candidate_scenarios_filename)
    if not os.path.exists(candidate_scenarios_file):
        logger.error(f"Candidate scenarios file not found at: {candidate_scenarios_file!r}. Please run candidate_scenarios.py first.")
        exit(1)
    with open(candidate_scenarios_file, 'r', encoding='utf-8') as f:
        candidate_data = json.load(f)
    scenarios_list = candidate_data.get('response', {}).get('scenarios', [])
    logger.info(f"Loaded {len(scenarios_list)} candidate scenarios.")

    # Load the selected scenario and assessments
    selected_scenario_file = os.path.join(os.path.dirname(__file__), 'test_data', selected_scenario_filename)
    if not os.path.exists(selected_scenario_file):
        logger.error(f"Selected scenario file not found at: {selected_scenario_file!r}. Please run select_scenario.py first.")
        exit(1)
    with open(selected_scenario_file, 'r', encoding='utf-8') as f:
        selected_data = json.load(f)
    plan_characteristics = selected_data.get('response', {}).get('plan_characteristics', {})
    scenario_assessments_list = selected_data.get('response', {}).get('scenario_assessments', [])
    final_choice = selected_data.get('response', {}).get('final_choice', {})
    logger.info(f"Loaded plan characteristics, {len(scenario_assessments_list)} scenario assessments, and final choice.")

    markdown_with_scenarios = ScenariosMarkdown(scenarios_list, plan_characteristics, scenario_assessments_list, final_choice)
    markdown_content = markdown_with_scenarios.to_markdown()

    # Save the markdown file
    output_filename = f"scenarios_markdown_{prompt_id}.md"
    markdown_with_scenarios.save_markdown(output_filename)
    logger.info(f"Saved markdown file to {output_filename!r}")