from src.prompt.prompt_catalog import PromptCatalog
import os

def find_plan_prompt(prompt_id: str) -> str:
    prompt_catalog = PromptCatalog()
    prompt_catalog.load(os.path.join(os.path.dirname(__file__), 'data', 'simple_plan_prompts.jsonl'))
    prompt_item = prompt_catalog.find(prompt_id)
    if not prompt_item:
        raise ValueError(f"Prompt ID '{prompt_id}' not found.")
    return prompt_item.prompt
