# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.
Every file you create or edit should start with:
 * 
 * Author: Your NAME  (Example: Claude Code using Sonnet 4)
 * Date: `timestamp`
 * PURPOSE: VERBOSE DETAILS ABOUT HOW THIS WORKS AND WHAT ELSE IT TOUCHES
 * SRP and DRY check: Pass/Fail Is this file violating either? Do these things already exist in the project?  Did you look??
 
## Common Commands
You need to Git add and commit any changes you make to the codebase.  Be detailed in your commit messages.


## Project Overview

PlanExe is a Python-based AI-powered planning system that transforms high-level ideas into detailed strategic and tactical plans. It uses Large Language Models (LLMs) to generate comprehensive multi-faceted plans through a pipeline-based architecture.

## Architecture

### Core Structure
- **Main Package**: `planexe/` - Contains all source code
- **Pipeline Framework**: Uses Luigi for orchestrating complex planning workflows
- **LLM Integration**: Multi-provider LLM support (OpenRouter, Ollama, LM Studio, etc.)
- **UI Options**: Gradio (primary) and Flask (experimental) web interfaces

### Key Modules
- `planexe/plan/` - Core planning logic and pipeline orchestration
- `planexe/prompt/` - Prompt catalog and management
- `planexe/llm_util/` - LLM abstraction and utilities
- `planexe/expert/` - Expert-based cost estimation and analysis
- `planexe/report/` - Report generation (HTML, PDF)
- `planexe/schedule/` - Timeline and Gantt chart generation
- `planexe/ui_flask/` - Flask web interface (experimental)
- `planexe/assume/` - Assumption identification and validation

### Pipeline Architecture
The system uses Luigi tasks for pipeline execution. Main pipeline entry point is `planexe/plan/run_plan_pipeline.py` which orchestrates:
- WBS (Work Breakdown Structure) generation (Level 1, 2, 3)
- Expert cost estimation
- Risk identification and analysis
- Resource planning
- Timeline generation
- Report compilation

## Development Commands

### Installation
```bash
# For development with all UI options
pip install -e '.[gradio-ui,flask-ui]'

# For Gradio UI only (recommended)
pip install '.[gradio-ui]'
```

### Running the Application
```bash
# Start Gradio web interface (primary UI)
python -m planexe.plan.app_text2plan

# Start Flask web interface (experimental)
python -m planexe.ui_flask.app

# Run planning pipeline directly
python -m planexe.plan.run_plan_pipeline

# Resume an existing run
RUN_ID_DIR=/path/to/run python -m planexe.plan.run_plan_pipeline
```

### Testing
```bash
# Run all tests using the custom test runner
python test.py

# Test files are located in various tests/ subdirectories:
# - planexe/plan/tests/
# - planexe/prompt/tests/
# - planexe/llm_util/tests/
# - planexe/markdown_util/tests/
# - planexe/chunk_dataframe_with_context/tests/
```

## Configuration

### LLM Configuration
- **File**: `llm_config.json` - Defines available LLM providers and models
- **Supported Providers**: OpenRouter (paid), Ollama (local), LM Studio (local)
- **Environment Variables**:
  - `OPENROUTER_API_KEY` for OpenRouter models
  - `RUN_ID_DIR` for resuming pipeline runs
  - `IS_HUGGINGFACE_SPACES` for deployment mode

### Environment Files
- `.env` - Local environment configuration
- `.env.example` - Template for environment setup

## Key Files and Entry Points

### Main Applications
- `planexe/plan/app_text2plan.py` - Gradio web interface
- `planexe/ui_flask/app.py` - Flask web interface
- `planexe/plan/run_plan_pipeline.py` - Pipeline execution engine

### Core Utilities
- `planexe/llm_factory.py` - LLM provider factory and management
- `planexe/plan/filenames.py` - File naming conventions for pipeline outputs
- `planexe/plan/generate_run_id.py` - Unique run identifier generation

## Data Flow

1. **Input**: User provides high-level idea/description through web UI
2. **Planning Pipeline**: Luigi orchestrates multi-stage planning process
3. **LLM Processing**: Various specialized prompts generate plan components
4. **Output**: Comprehensive plan with WBS, costs, timelines, and reports
5. **Export**: Plans can be exported as ZIP archives with HTML reports

## Dependencies

- **Core**: Python 3.13+, Luigi (pipeline), LlamaIndex (LLM abstraction)
- **UI**: Gradio (primary), Flask (experimental)
- **LLM Providers**: OpenAI, Ollama, various providers via OpenRouter
- **Output**: Pandas (data processing), Jinja2 (templating)

## Testing Strategy

- Unit tests distributed across module-specific `tests/` directories
- Custom test runner in `test.py` using unittest discovery
- Tests cover prompt generation, LLM utilities, data processing, and core planning logic