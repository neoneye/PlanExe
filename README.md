# PlanExe: Transform your ideas into actionable plans

## Comparison with similar tools

|                          | PlanExe | Open Source LLM            | Commercial LLM           |  LLM w/ Agents | Consulting Firms | Project Mgt Software |
| ------------------------ | ------- | -------------------------- | ------------------------ | -------------- | ---------------- | -------------------- |
| Detailed Plans           | ✅      | ❌                          | ❌                       | ✅             | ✅                | ✅                   |
| Report Generation Time   | 30m     | 10s                        | 10s                      | 30m            | 1 week+          | Manual work          |
| Cost                     | Low     | Low                        | Low                      | Low            | High             | Medium               |
| Factual Accuracy         | ⭐      | ⭐                          | ⭐                       | ⭐⭐⭐⭐        | ⭐⭐⭐⭐⭐         | 1-5 Stars            |
| Open Source              | ✅      | ✅                          | ❌                       | ❌             | ❌                | ❌                   |

**Where:**
* **Open Source LLM, without agents:** Ollama, LM Studio
* **Commercial LLM, without agents:** OpenAI, Google, Anthropic
* **LLM w/ Agents:** OpenAI’s Deep Research, Manus. Only 4 star in `Factual Accuracy`, since this is AI-generated with limited verification.
* **Consulting Firms:** McKinsey, BCG, Bain. 5 star in `Factual Accuracy`, assuming it's expert verified data.
* **Project Management Software:** Asana, Monday, Jira, ClickUp. Variable number of stars in `Factual Accuracy` since it depends on team, effort, budget.


## What is PlanExe?

PlanExe is a planning AI. You input a vague description of what you want and PlanExe outputs a plan. [See generated plans here](https://neoneye.github.io/PlanExe-web/use-cases/).

![Video of PlanExe](/extra/planexe-humanoid-factory.gif?raw=true "Video of PlanExe")

[YouTube video: Using PlanExe to plan a lunar base](https://www.youtube.com/watch?v=7AM2F1C4CGI)

![Screenshot of PlanExe](/extra/planexe-humanoid-factory.jpg?raw=true "Screenshot of PlanExe")

# Installation

Clone this repo, then install and activate a virtual environment. Finally, install the required packages:

```bash
git clone https://github.com/neoneye/PlanExe.git
cd PlanExe
python3 -m venv venv
source venv/bin/activate
(venv) pip install -r requirements.txt
```

# Configuration

**Config A:** Run a model in the cloud using a paid provider. Follow the instructions in [OpenRouter](extra/openrouter.md).

**Config B:** Run models locally on a high-end computer. Follow the instructions for either [Ollama](extra/ollama.md) or [LM Studio](extra/lm_studio.md).

Recommendation: I recommend **Config A** as it offers the most straightforward path to getting PlanExe working reliably.

# Usage

PlanExe comes with a Gradio-based web interface. To start the local web server:

```bash
(venv) python -m src.plan.app_text2plan
```

This command launches a server at http://localhost:7860. Open that link in your browser, type a vague idea or description, and PlanExe will produce a detailed plan.

To stop the server at any time, press `Ctrl+C` in your terminal.

# Community & Support

Join the [PlanExe Discord](https://neoneye.github.io/PlanExe-web/discord) to chat about PlanExe, share ideas, and get help.
