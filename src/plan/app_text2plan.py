"""
PROMPT> python -m src.plan.app_text2plan
"""
import gradio as gr
import os
import subprocess
import time
import sys
import threading
from datetime import datetime
from math import ceil
from src.llm_factory import get_available_llms
from src.plan.filenames import FilenameEnum
from src.plan.plan_file import PlanFile
from src.plan.speedvsdetail import SpeedVsDetailEnum
from src.prompt.prompt_catalog import PromptCatalog
    
# Global variables
active_proc = None
stop_event = threading.Event()
latest_run_id = None
latest_run_dir = None

MODULE_PATH_PIPELINE = "src.plan.run_plan_pipeline"
DEFAULT_PROMPT_UUID = "4dc34d55-0d0d-4e9d-92f4-23765f49dd29"

# The pipeline outputs are stored in a log.txt file in the run directory.
# So we don't need to relay the process output to the console.
# Except for debugging purposes, you can set this to True.
RELAY_PROCESS_OUTPUT = False

prompt_catalog = PromptCatalog()
prompt_catalog.load(os.path.join(os.path.dirname(__file__), 'data', 'simple_plan_prompts.jsonl'))

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

def log_process_output(pipe, label):
    """
    Reads lines from the given pipe and prints them to the console with a label.
    """
    for line in iter(pipe.readline, b''):
        if line:
            print(f"[{label}] {line.decode().rstrip()}")

def has_pipeline_complete_file(path_dir: str):
    """
    Checks if the pipeline has completed by looking for the completion file.
    """
    files = os.listdir(path_dir)
    return FilenameEnum.PIPELINE_COMPLETE.value in files

class MarkdownBuilder:
    """
    Helper class to build Markdown-formatted strings.
    """
    def __init__(self):
        self.rows = []

    def add_line(self, line: str):
        self.rows.append(line)

    def add_code_block(self, code: str):
        self.rows.append("```\n" + code + "\n```")

    def status(self, status_message: str):
        self.add_line(f"### Status")
        self.add_line(status_message)

    def path_to_run_dir(self, absolute_path_to_run_dir: str):
        self.add_line(f"### Output dir")
        self.add_code_block(absolute_path_to_run_dir)

    def list_files(self, path_dir: str):
        self.add_line(f"### Output files")
        files = os.listdir(path_dir)
        files.sort()
        filenames = "\n".join(files)
        self.add_code_block(filenames)

    def to_markdown(self):
        return "\n".join(self.rows)
    
def run_planner(submit_or_retry_button: str, plan_prompt: str, llm_model: str, speedvsdetail: str):
    """
    This generator function:
    
    1. Prepare the run directory.
    2. Updates environment with RUN_ID and LLM_MODEL.
    3. Launches the Python pipeline script.
    5. Polls the output dir (every second) to yield a Markdown-formatted file listing.
       If a stop is requested or if the pipeline-complete file is detected, it exits.
    """
    global active_proc, stop_event, latest_run_dir, latest_run_id

    # Clear any previous stop signal.
    stop_event.clear()

    submit_or_retry = submit_or_retry_button.lower()

    if submit_or_retry == "retry":
        if latest_run_id is None:
            raise ValueError("No previous run to retry. Please submit a plan first.")

        run_id = latest_run_id
        run_path = os.path.join("run", run_id)
        absolute_path_to_run_dir = latest_run_dir

        print(f"Retrying the run with ID: {run_id}")

        if not os.path.exists(run_path):
            raise Exception(f"The run path is supposed to exist from an earlier run. However the no run path exists: {run_path}")
        
    elif submit_or_retry == "submit":
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_path = os.path.join("run", run_id)
        absolute_path_to_run_dir = os.path.abspath(run_path)

        print(f"Submitting a new run with ID: {run_id}")

        # Update the global variables.
        latest_run_id = run_id
        latest_run_dir = absolute_path_to_run_dir

        # Prepare a new run directory.
        if os.path.exists(run_path):
            raise Exception(f"The run path is not supposed to exist at this point. However the run path already exists: {run_path}")
        os.makedirs(run_path)

        # Create the initial plan file.
        plan_file = PlanFile.create(plan_prompt)
        plan_file.save(os.path.join(run_path, FilenameEnum.INITIAL_PLAN.value))

    # Set the prompt in the environment so the pipeline can use it.
    env = os.environ.copy()
    env["RUN_ID"] = run_id
    env["LLM_MODEL"] = llm_model
    env["SPEED_VS_DETAIL"] = speedvsdetail

    start_time = time.perf_counter()

    # Launch the pipeline as a separate Python process.
    command = [sys.executable, "-m", MODULE_PATH_PIPELINE]
    print(f"Executing command: {' '.join(command)}")
    active_proc = subprocess.Popen(
        command,
        cwd=".",
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=False
    )
    # Spawn threads to print process output to the console.
    if RELAY_PROCESS_OUTPUT:
        threading.Thread(target=log_process_output, args=(active_proc.stdout, "stdout"), daemon=True).start()
        threading.Thread(target=log_process_output, args=(active_proc.stderr, "stderr"), daemon=True).start()

    # Obtain process id
    child_process_id = active_proc.pid
    print(f"Process started. Process ID: {child_process_id}")

    # Poll the output directory every second.
    while True:
        # Check if the process has ended.
        if active_proc.poll() is not None:
            break

        # print("running...")
        end_time = time.perf_counter()
        duration = int(ceil(end_time - start_time))

        # Check if a stop was requested.
        if stop_event.is_set():
            try:
                active_proc.terminate()
            except Exception as e:
                print("Error terminating process:", e)

            markdown_builder = MarkdownBuilder()
            markdown_builder.status("Process terminated by user.")
            markdown_builder.path_to_run_dir(absolute_path_to_run_dir)
            markdown_builder.list_files(run_path)
            yield markdown_builder.to_markdown()
            break

        markdown_builder = MarkdownBuilder()
        markdown_builder.status(f"Working. {duration} seconds elapsed.")
        markdown_builder.path_to_run_dir(absolute_path_to_run_dir)
        markdown_builder.list_files(run_path)
        yield markdown_builder.to_markdown()

        # If the pipeline complete file is found, finish streaming.
        if has_pipeline_complete_file(run_path):
            break

        time.sleep(1)

    # Wait for the process to end (if it hasn't already) and clear our global.
    returncode = 'NOT SET'
    if active_proc is not None:
        active_proc.wait()
        returncode = active_proc.returncode
        active_proc = None

    # Process has completed.
    end_time = time.perf_counter()
    duration = int(ceil(end_time - start_time))
    print(f"Process ended. returncode: {returncode}. Process ID: {child_process_id}. Duration: {duration} seconds.")

    if has_pipeline_complete_file(run_path):
        status_message = "Completed."
    else:
        status_message = "Stopped prematurely, the output may be incomplete."

    # Final file listing update.
    markdown_builder = MarkdownBuilder()
    markdown_builder.status(f"{status_message} {duration} seconds elapsed.")
    markdown_builder.path_to_run_dir(absolute_path_to_run_dir)
    markdown_builder.list_files(run_path)
    yield markdown_builder.to_markdown()

def stop_planner():
    """
    Sets a global stop flag and, if there is an active process, attempts to terminate it.
    Returns a status message.
    """
    global active_proc, stop_event
    stop_event.set()
    if active_proc is not None:
        try:
            if active_proc.poll() is None:  # Process is still running.
                active_proc.terminate()
            return "Stop signal sent. Process termination requested."
        except Exception as e:
            return f"Error terminating process: {e}"
    else:
        return "No active process to stop."

def open_output_dir():
    """
    Opens the latest output directory in the native file explorer.
    """
    if not latest_run_dir or not os.path.exists(latest_run_dir):
        return "No output directory available."
    
    try:
        if sys.platform == "darwin":  # macOS
            subprocess.Popen(["open", latest_run_dir])
        elif sys.platform == "win32":  # Windows
            subprocess.Popen(["explorer", latest_run_dir])
        else:  # Assume Linux or other unix-like OS
            subprocess.Popen(["xdg-open", latest_run_dir])
        return f"Opened the directory: {latest_run_dir}"
    except Exception as e:
        return f"Failed to open directory: {e}"

# Build the Gradio UI using Blocks.
with gr.Blocks(title="PlanExe") as demo:
    gr.Markdown("# PlanExe: crack open pandora’s box of ideas")
    with gr.Tab("Main"):
        with gr.Row():
            with gr.Column(scale=2, min_width=300):
                prompt_input = gr.Textbox(
                    label="Plan Description",
                    lines=5,
                    placeholder="Enter a description of your plan...",
                    value=gradio_default_example
                )
                with gr.Row():
                    submit_btn = gr.Button("Submit", variant='primary')
                    stop_btn = gr.Button("Stop")
                    retry_btn = gr.Button("Retry")
                    open_dir_btn = gr.Button("Open Output Dir")

                output_markdown = gr.Markdown("Output will appear here...")
                status_markdown = gr.Markdown("Status messages will appear here...")

            with gr.Column(scale=1, min_width=300):
                examples = gr.Examples(
                    examples=gradio_examples,
                    inputs=[prompt_input],
                )

    with gr.Tab("Settings"):
        model_radio = gr.Radio(
            available_model_names,
            value=available_model_names[0],
            label="Model",
            interactive=True 
        )

        speedvsdetail_items = [
            ("All details, but slow", SpeedVsDetailEnum.ALL_DETAILS_BUT_SLOW),
            ("Fast, but few details", SpeedVsDetailEnum.FAST_BUT_SKIP_DETAILS),
        ]
        speedvsdetail_radio = gr.Radio(
            speedvsdetail_items,
            value=SpeedVsDetailEnum.ALL_DETAILS_BUT_SLOW,
            label="Speed vs Detail",
            interactive=True 
        )

    with gr.Tab("Join the community"):
        gr.Markdown("""
            # PlanExe
                    
            https://github.com/neoneye/PlanExe

            [PlanExe Discord](https://neoneye.github.io/PlanExe-web/discord)

            """)

    # Start the planning assistant with streaming updates.
    submit_btn.click(fn=run_planner, inputs=[submit_btn, prompt_input, model_radio, speedvsdetail_radio], outputs=output_markdown)
    # The stop button simply calls stop_planner and displays its status message.
    stop_btn.click(fn=stop_planner, outputs=status_markdown)
    retry_btn.click(fn=run_planner, inputs=[retry_btn, prompt_input, model_radio, speedvsdetail_radio], outputs=output_markdown)
    open_dir_btn.click(fn=open_output_dir, outputs=status_markdown)

print("Press Ctrl+C to exit.")
demo.launch()
