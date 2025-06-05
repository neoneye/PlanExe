"""
PROMPT> python -m planexe.swot.app_swot_analysis
"""
import gradio as gr
import os
import json
import logging
from typing import List, Optional
from planexe.swot.swot_analysis import SWOTAnalysis
from planexe.llm_factory import LLMInfo, get_llm
from planexe.prompt.prompt_catalog import PromptCatalog

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

DEFAULT_PROMPT_UUID = "427e5163-cefa-46e8-b1d0-eb12be270e19"

prompt_catalog = PromptCatalog()
prompt_catalog.load_example_swot_prompts()

# Show all prompts in the catalog as examples
all_prompts = prompt_catalog.all()
gradio_examples = []
for prompt_item in all_prompts:
    gradio_examples.append([prompt_item.prompt])

llm_info = LLMInfo.obtain_info()
logger.info(f"LLMInfo.ollama_status: {llm_info.ollama_status.value}")
logger.info(f"LLMInfo.error_message_list: {llm_info.error_message_list}")

# Create tupples for the Gradio Radio buttons.
available_model_names = []
default_model_value = None
for config_index, config_item in enumerate(llm_info.llm_config_items):
    if config_index == 0:
        default_model_value = config_item.id
    tuple_item = (config_item.label, config_item.id)
    available_model_names.append(tuple_item)

# Prefill the input box with the default prompt
default_prompt_item = prompt_catalog.find(DEFAULT_PROMPT_UUID)
if default_prompt_item:
    gradio_default_example = default_prompt_item.prompt
else:
    raise ValueError("DEFAULT_PROMPT_UUID prompt not found.")

def make_swot(prompt_description, model_id, model_temperature):
    temperature_float = float(model_temperature) / 100.0

    llm = get_llm(model_id, temperature=temperature_float)
    
    result = SWOTAnalysis.execute(llm=llm, query=prompt_description, identify_purpose_dict=None)
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
            value=default_model_value,
            label="Model",
            interactive=True 
        )
        model_temperature = gr.Slider(0, 100, value=12, label="Temperature", info="Choose between 1 and 100")
    run_button.click(make_swot, [inp, model_radio, model_temperature], out)
print("Press Ctrl+C to exit.")
demo.launch(
    # server_name="0.0.0.0"
)
