# Installing PlanExe

This guide explains how to get PlanExe up and running.

## Install on macOS or Linux

Clone this repo, then install and activate a virtual environment. Finally, install the required packages:

```bash
git clone https://github.com/neoneye/PlanExe.git
cd PlanExe
python3 -m venv venv
source venv/bin/activate
(venv) pip install .[gradio-ui]
```

## Install on Windows

Clone this repo, then install and activate a virtual environment. Finally, install the required packages:

```bash
git clone https://github.com/neoneye/PlanExe.git
cd PlanExe
python3 -m venv venv
.venv\Scripts\activate
(venv) pip install .[gradio-ui]
```

# Configuration

**Config A:** Run a model in the cloud using a paid provider. Follow the instructions in [OpenRouter](extra/openrouter.md).

**Config B:** Run models locally on a high-end computer. Follow the instructions for either [Ollama](extra/ollama.md) or [LM Studio](extra/lm_studio.md).

Recommendation: I recommend **Config A** as it offers the most straightforward path to getting PlanExe working reliably.

# Usage

PlanExe comes with a Gradio-based web interface. To start the local web server:

```bash
(venv) python -m worker_plan_internal.plan.app_text2plan
```

This command launches a server at http://localhost:7860. Open that link in your browser, type a vague idea or description, and PlanExe will produce a detailed plan.

To stop the server at any time, press `Ctrl+C` in your terminal.

# Community 

If need help getting PlanExe installed or troubleshooting.

Have questions? Need help? Join the [PlanExe Discord](https://neoneye.github.io/PlanExe-web/discord) to chat about PlanExe, share ideas, and get support.
