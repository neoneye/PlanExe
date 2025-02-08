"""
PROMPT> python -m src.swot.app_swot_analysis
"""
import gradio as gr
import os
import json
from typing import List, Optional
from src.swot.swot_analysis import SWOTAnalysis
from src.llm_factory import get_llm, get_available_llms
from src.prompt.prompt_catalog import PromptCatalog

DEFAULT_PROMPT_UUID = "427e5163-cefa-46e8-b1d0-eb12be270e19"

prompt_catalog = PromptCatalog()
prompt_catalog.load(os.path.join(os.path.dirname(__file__), 'data', 'example_swot_prompt.jsonl'))

# Prefill the input box with the default prompt
default_prompt_item = prompt_catalog.find(DEFAULT_PROMPT_UUID)
if default_prompt_item:
    gradio_default_example = default_prompt_item.prompt
else:
    raise ValueError("DEFAULT_PROMPT_UUID prompt not found.")

# Show all prompts in the catalog as examples
all_prompts = prompt_catalog.all()
gradio_examples = []
for prompt_item in all_prompts:
    gradio_examples.append([prompt_item.prompt])

available_models = get_available_llms()
available_model_names = [model for model in available_models]

def make_swot(prompt_description, model_id, model_temperature):
    temperature_float = float(model_temperature) / 100.0

    llm = get_llm(model_id, temperature=temperature_float)
    
    result = SWOTAnalysis.execute(llm, prompt_description)
    markdown = result.to_markdown()
    return markdown

EMPTY_SWOT_ANALYSIS = """
# SWOT Analysis
```txt


   ▄████████  ▄█     █▄   ▄██████▄      ███    
  ███    ███ ███     ███ ███    ███ ▀█████████▄
  ███    █▀  ███     ███ ███    ███    ▀███▀▀██
  ███        ███     ███ ███    ███     ███   ▀
▀███████████ ███     ███ ███    ███     ███    
         ███ ███     ███ ███    ███     ███    
   ▄█    ███ ███ ▄█▄ ███ ███    ███     ███    
 ▄████████▀   ▀███▀███▀   ▀██████▀     ▄████▀  


```
"""

with gr.Blocks(title="SWOT") as demo:
    with gr.Tab("Main"):
        with gr.Row():
            with gr.Column(scale=2, min_width=300):
                inp = gr.Textbox(label="Input", placeholder="Describe your project here", autofocus=True, value=gradio_default_example)
                run_button = gr.Button("Run")
                out = gr.Markdown(value=EMPTY_SWOT_ANALYSIS, label="Output", show_copy_button=True)
            with gr.Column(scale=1, min_width=300):
                examples = gr.Examples(
                    examples=gradio_examples,
                    inputs=[inp],
                )
    with gr.Tab("Settings"):
        model_radio = gr.Radio(
            available_model_names,
            value=available_model_names[0],
            label="Model",
            interactive=True 
        )
        model_temperature = gr.Slider(0, 100, value=12, label="Temperature", info="Choose between 1 and 100")
    run_button.click(make_swot, [inp, model_radio, model_temperature], out)
print("Press Ctrl+C to exit.")
demo.launch(
    # server_name="0.0.0.0"
)
