"""
Start the UI in single user mode.
PROMPT> python -m src.plan.app_text2plan

Start the UI in multi user mode, as on: Hugging Face Spaces.
PROMPT> IS_HUGGINGFACE_SPACES=true python -m src.plan.app_text2plan
"""
import gradio as gr
import os
import subprocess
import time
import sys
import threading
import logging
from dataclasses import dataclass
from math import ceil
from src.llm_factory import get_available_llms
from src.plan.generate_run_id import generate_run_id, RUN_ID_PREFIX
from src.plan.create_zip_archive import create_zip_archive
from src.plan.filenames import FilenameEnum
from src.plan.plan_file import PlanFile
from src.plan.speedvsdetail import SpeedVsDetailEnum
from src.prompt.prompt_catalog import PromptCatalog
from src.purge.purge_old_runs import start_purge_scheduler
from src.utils.get_env_as_string import get_env_as_string
from src.utils.is_huggingface_spaces import is_huggingface_spaces
from src.utils.time_since_last_modification import time_since_last_modification

# Slightly different behavior when running inside Hugging Face Spaces, where it's not possible to open a file explorer.
# And it's multi-user, so we need to keep track of the state for each user.
IS_HUGGINGFACE_SPACES = is_huggingface_spaces()

@dataclass
class Config:
    use_uuid_as_run_id: bool
    visible_top_header: bool
    visible_open_output_dir_button: bool
    visible_openrouter_api_key_textbox: bool
    allow_only_openrouter_models: bool
    enable_purge_old_runs: bool

CONFIG_LOCAL = Config(
    use_uuid_as_run_id=False,
    visible_top_header=True,
    visible_open_output_dir_button=True,
    visible_openrouter_api_key_textbox=False,
    allow_only_openrouter_models=False,
    enable_purge_old_runs=False,
)
CONFIG_HUGGINGFACE_SPACES = Config(
    use_uuid_as_run_id=True,
    visible_top_header=False,
    visible_open_output_dir_button=False,
    visible_openrouter_api_key_textbox=True,
    allow_only_openrouter_models=True,
    enable_purge_old_runs=True,
)

CONFIG = CONFIG_HUGGINGFACE_SPACES if IS_HUGGINGFACE_SPACES else CONFIG_LOCAL

MODULE_PATH_PIPELINE = "src.plan.run_plan_pipeline"
DEFAULT_PROMPT_UUID = "4dc34d55-0d0d-4e9d-92f4-23765f49dd29"

# Set to True if you want the pipeline process output relayed to your console.
RELAY_PROCESS_OUTPUT = False

# Global constant for the zip creation interval (in seconds)
ZIP_INTERVAL_SECONDS = 10

RUN_DIR = "run"

# Load prompt catalog and examples.
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

all_available_models = get_available_llms()
if CONFIG.allow_only_openrouter_models:
    available_model_names = [model for model in all_available_models if model.startswith("openrouter")]
else:
    available_model_names = all_available_models

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
        self.add_line("### Status")
        self.add_line(status_message)

    def path_to_run_dir(self, absolute_path_to_run_dir: str):
        self.add_line("### Output dir")
        self.add_code_block(absolute_path_to_run_dir)

    def list_files(self, path_dir: str):
        self.add_line("### Output files")
        files = os.listdir(path_dir)
        files.sort()
        filenames = "\n".join(files)
        self.add_code_block(filenames)

    def to_markdown(self):
        return "\n".join(self.rows)

class SessionState:
    """
    In a multi-user environment (e.g. Hugging Face Spaces), this class hold each users state.
    In a single-user environment, this class is used to hold the state of that lonely user.

    IDEA: Persist the user settings for longer. The settings survive a page refresh, but not a server restart.
    The browser has a local storage. Can Gradio access that, so that the settings are remembered between sessions?
    """
    def __init__(self):
        # Settings: the user's OpenRouter API key.
        self.openrouter_api_key = "" # Initialize to empty string
        # Settings: The model that the user has picked.
        self.llm_model = available_model_names[0]
        # Settings: The speedvsdetail that the user has picked.
        self.speedvsdetail = SpeedVsDetailEnum.ALL_DETAILS_BUT_SLOW
        # Holds the subprocess.Popen object for the currently running pipeline process.
        self.active_proc = None
        # A threading.Event used to signal that the running process should stop.
        self.stop_event = threading.Event()
        # Stores the unique identifier of the last submitted run.
        self.latest_run_id = None
        # Stores the absolute path to the directory for the last submitted run.
        self.latest_run_dir = None

    def __deepcopy__(self, memo):
        """
        Override deepcopy so that the SessionState instance is not actually copied.
        This avoids trying to copy unpickleable objects (like threading locks) and
        ensures the same instance is passed along between Gradio callbacks.
        """
        return self

def run_planner(submit_or_retry_button, plan_prompt, session_state: SessionState):
    """
    Generator function for launching the pipeline process and streaming updates.
    The session state is carried in a SessionState instance.
    """

    # Clear any previous stop signal.
    session_state.stop_event.clear()

    submit_or_retry = submit_or_retry_button.lower()

    if submit_or_retry == "retry":
        if not session_state.latest_run_id:
            raise ValueError("No previous run to retry. Please submit a plan first.")
        run_id = session_state.latest_run_id
        run_path = os.path.join(RUN_DIR, run_id)
        absolute_path_to_run_dir = session_state.latest_run_dir
        print(f"Retrying the run with ID: {run_id}")
        if not os.path.exists(run_path):
            raise Exception(f"The run path is supposed to exist from an earlier run. However the no run path exists: {run_path}")
        
    elif submit_or_retry == "submit":
        run_id = generate_run_id(CONFIG.use_uuid_as_run_id)
        run_path = os.path.join(RUN_DIR, run_id)
        absolute_path_to_run_dir = os.path.abspath(run_path)

        print(f"Submitting a new run with ID: {run_id}")
        # Prepare a new run directory.
        session_state.latest_run_id = run_id
        session_state.latest_run_dir = absolute_path_to_run_dir
        if os.path.exists(run_path):
            raise Exception(f"The run path is not supposed to exist at this point. However the run path already exists: {run_path}")
        os.makedirs(run_path)

        # Create the initial plan file.
        plan_file = PlanFile.create(plan_prompt)
        plan_file.save(os.path.join(run_path, FilenameEnum.INITIAL_PLAN.value))

    # Set environment variables for the pipeline.
    env = os.environ.copy()
    env["RUN_ID"] = run_id
    env["LLM_MODEL"] = session_state.llm_model
    env["SPEED_VS_DETAIL"] = session_state.speedvsdetail

    # If there is a non-empty OpenRouter API key, set it as an environment variable.
    if session_state.openrouter_api_key and len(session_state.openrouter_api_key) > 0:
        print("Setting OpenRouter API key as environment variable.")
        env["OPENROUTER_API_KEY"] = session_state.openrouter_api_key
    else:
        print("No OpenRouter API key provided.")

    start_time = time.perf_counter()
    # Initialize the last zip creation time to be ZIP_INTERVAL_SECONDS in the past
    last_zip_time = time.time() - ZIP_INTERVAL_SECONDS
    most_recent_zip_file = None

    # Launch the pipeline as a separate Python process.
    command = [sys.executable, "-m", MODULE_PATH_PIPELINE]
    print(f"Executing command: {' '.join(command)}")
    if RELAY_PROCESS_OUTPUT:
        session_state.active_proc = subprocess.Popen(
            command,
            cwd=".",
            env=env,
            stdout=None,
            stderr=None
        )
    else:
        session_state.active_proc = subprocess.Popen(
            command,
            cwd=".",
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

    # Obtain process id
    child_process_id = session_state.active_proc.pid
    print(f"Process started. Process ID: {child_process_id}")

    # Poll the output directory every second.
    while True:
        # Check if the process has ended.
        if session_state.active_proc.poll() is not None:
            break

        # print("running...")
        end_time = time.perf_counter()
        duration = int(ceil(end_time - start_time))

        # If a stop has been requested, terminate the process.
        if session_state.stop_event.is_set():
            try:
                session_state.active_proc.terminate()
            except Exception as e:
                print("Error terminating process:", e)

            markdown_builder = MarkdownBuilder()
            markdown_builder.status("Process terminated by user.")
            markdown_builder.path_to_run_dir(absolute_path_to_run_dir)
            markdown_builder.list_files(run_path)
            zip_file_path = create_zip_archive(run_path)
            if zip_file_path:
                most_recent_zip_file = zip_file_path
            yield markdown_builder.to_markdown(), most_recent_zip_file, session_state
            break

        last_update = ceil(time_since_last_modification(run_path))
        markdown_builder = MarkdownBuilder()
        markdown_builder.status(f"Working. {duration} seconds elapsed. Last output update was {last_update} seconds ago.")
        markdown_builder.path_to_run_dir(absolute_path_to_run_dir)
        markdown_builder.list_files(run_path)

        # Create a new zip archive every ZIP_INTERVAL_SECONDS seconds.
        current_time = time.time()
        if current_time - last_zip_time >= ZIP_INTERVAL_SECONDS:
            zip_file_path = create_zip_archive(run_path)
            if zip_file_path:
                most_recent_zip_file = zip_file_path
            last_zip_time = current_time

        yield markdown_builder.to_markdown(), most_recent_zip_file, session_state

        # If the pipeline complete file is found, finish streaming.
        if has_pipeline_complete_file(run_path):
            break

        time.sleep(1)
    
    # Wait for the process to end and clear the active process.
    returncode = 'NOT SET'
    if session_state.active_proc is not None:
        session_state.active_proc.wait()
        returncode = session_state.active_proc.returncode
        session_state.active_proc = None

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

    # Create zip archive
    zip_file_path = create_zip_archive(run_path)
    if zip_file_path:
        most_recent_zip_file = zip_file_path

    yield markdown_builder.to_markdown(), most_recent_zip_file, session_state

def stop_planner(session_state: SessionState):
    """
    Sets a stop flag in the session_state and attempts to terminate the active process.
    """

    session_state.stop_event.set()

    if session_state.active_proc is not None:
        try:
            if session_state.active_proc.poll() is None:
                session_state.active_proc.terminate()
            msg = "Stop signal sent. Process termination requested."
        except Exception as e:
            msg = f"Error terminating process: {e}"
    else:
        msg = "No active process to stop."

    return msg, session_state

def open_output_dir(session_state: SessionState):
    """
    Opens the latest output directory in the native file explorer.
    """

    latest_run_dir = session_state.latest_run_dir
    if not latest_run_dir or not os.path.exists(latest_run_dir):
        return "No output directory available.", session_state

    try:
        if sys.platform == "darwin":  # macOS
            subprocess.Popen(["open", latest_run_dir])
        elif sys.platform == "win32":  # Windows
            subprocess.Popen(["explorer", latest_run_dir])
        else:  # Linux or other Unix-like OS
            subprocess.Popen(["xdg-open", latest_run_dir])
        return f"Opened the directory: {latest_run_dir}", session_state
    except Exception as e:
        return f"Failed to open directory: {e}", session_state

def update_openrouter_api_key(openrouter_api_key, session_state: SessionState):
    """Updates the OpenRouter API key in the session state."""
    session_state.openrouter_api_key = openrouter_api_key
    return openrouter_api_key, session_state

def update_model_radio(llm_model, session_state: SessionState):
    """Updates the llm_model in the session state"""
    session_state.llm_model = llm_model
    return llm_model, session_state

def update_speedvsdetail_radio(speedvsdetail, session_state: SessionState):
    """Updates the speedvsdetail in the session state"""
    session_state.speedvsdetail = speedvsdetail
    return speedvsdetail, session_state

def initialize_settings(session_state: SessionState):
    """Initializes the settings from session_state, if available."""
    return (session_state.openrouter_api_key,
            session_state.llm_model,
            session_state.speedvsdetail,
            session_state)

def check_api_key(session_state: SessionState):
    """Checks if the API key is provided and returns a warning if not."""
    if CONFIG.visible_openrouter_api_key_textbox and (not session_state.openrouter_api_key or len(session_state.openrouter_api_key) == 0):
        return "<div style='background-color: #FF7777; color: black; border: 1px solid red; padding: 10px;'>Welcome to PlanExe. Please provide an OpenRouter API key in the <b>Settings</b> tab to start using PlanExe.</div>"
    return "" # No warning

# Build the Gradio UI using Blocks.
with gr.Blocks(title="PlanExe") as demo_text2plan:
    gr.Markdown("# PlanExe: crack open pandora’s box of ideas", visible=CONFIG.visible_top_header)
    api_key_warning = gr.Markdown()
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
                    open_dir_btn = gr.Button("Open Output Dir", visible=CONFIG.visible_open_output_dir_button)

                output_markdown = gr.Markdown("Output will appear here...")
                status_markdown = gr.Markdown("Status messages will appear here...")
                download_output = gr.File(label="Download latest output (excluding log.txt) as zip")

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
        openrouter_api_key_text = gr.Textbox(
            label="OpenRouter API Key",
            type="password",
            placeholder="Enter your OpenRouter API key (required)",
            info="Sign up at [OpenRouter](https://openrouter.ai/) to get an API key. A small top-up (e.g. 5 USD) is needed to access paid models.",
            visible=CONFIG.visible_openrouter_api_key_textbox
        )

    with gr.Tab("Join the community"):
        gr.Markdown("""
- [GitHub](https://github.com/neoneye/PlanExe) the source code.
- [Discord](https://neoneye.github.io/PlanExe-web/discord) join the community. Suggestions, feedback, and questions are welcome.
""")
    
    # Manage the state of the current user
    session_state = gr.State(SessionState())

    # Submit and Retry buttons call run_planner and update the state.
    submit_btn.click(
        fn=run_planner,
        inputs=[submit_btn, prompt_input, session_state],
        outputs=[output_markdown, download_output, session_state]
    ).then(
        fn=check_api_key,  # Check after submitting.
        inputs=[session_state],
        outputs=[api_key_warning]
    )
    retry_btn.click(
        fn=run_planner,
        inputs=[retry_btn, prompt_input, session_state],
        outputs=[output_markdown, download_output, session_state]
    ).then(
        fn=check_api_key,  # Check after retrying.
        inputs=[session_state],
        outputs=[api_key_warning]
    )
    # The Stop button uses the state to terminate the running process.
    stop_btn.click(
        fn=stop_planner,
        inputs=session_state,
        outputs=[status_markdown, session_state]
    )
    # Open Output Dir button.
    open_dir_btn.click(
        fn=open_output_dir,
        inputs=session_state,
        outputs=[status_markdown, session_state]
    )

    openrouter_api_key_text.change(
        fn=update_openrouter_api_key,
        inputs=[openrouter_api_key_text, session_state],
        outputs=[openrouter_api_key_text, session_state]
    ).then(
        fn=check_api_key,  # Check when the API key changes.
        inputs=[session_state],
        outputs=[api_key_warning]
    )
    model_radio.change(
        fn=update_model_radio,
        inputs=[model_radio, session_state],
        outputs=[model_radio, session_state]
    )
    speedvsdetail_radio.change(
        fn=update_speedvsdetail_radio,
        inputs=[speedvsdetail_radio, session_state],
        outputs=[speedvsdetail_radio, session_state]
    )


    demo_text2plan.load(
        fn=initialize_settings,
        inputs=[session_state],
        outputs=[openrouter_api_key_text, model_radio, speedvsdetail_radio, session_state]
    ).then(
        fn=check_api_key,  # Check on initial load.
        inputs=[session_state],
        outputs=[api_key_warning]
    )

def run_app_text2plan():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler()
        ]
    )

    if CONFIG.enable_purge_old_runs:
        start_purge_scheduler(run_dir=os.path.abspath(RUN_DIR), purge_interval_seconds=60*60, prefix=RUN_ID_PREFIX)

    # print("Environment variables Gradio:\n" + get_env_as_string() + "\n\n\n")

    print("Press Ctrl+C to exit.")
    demo_text2plan.launch()

if __name__ == "__main__":
    run_app_text2plan()
