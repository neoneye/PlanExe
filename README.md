# PlanExe

<p align="center">
  <img src="extra/planexe-humanoid-factory.gif?raw=true" alt="PlanExe - Turn your idea into a comprehensive plan in minutes, not months." width="700">
</p>

<p align="center">
  <strong>Turn your idea into a comprehensive plan in minutes, not months.</strong>
</p>

---

## Example plans generated with PlanExe

- A business plan for a [Minecraft-themed escape room](https://neoneye.github.io/PlanExe-web/20251016_minecraft_escape_report.html).
- A business plan for a [Faraday cage manufacturing company](https://neoneye.github.io/PlanExe-web/20250720_faraday_enclosure_report.html).
- A pilot project for a [Human as-a Service](https://neoneye.github.io/PlanExe-web/20251012_human_as_a_service_protocol_report.html).
- See more [examples here](https://neoneye.github.io/PlanExe-web/examples/).

## What is PlanExe?

PlanExe is an open-source tool, that turns a single plain-english goal statement into a 40-page, strategic plan in ~15 minutes using a local or cloud models. It's an accelerator for outlines, but no silver bullet for polished plans.

Typical output contains:
- Executive summary
- Gantt chart
- Governance structure
- Role descriptions
- Stakeholder maps
- Risk registers
- SWOT analyses

The technical quality of structure, formatting, and coherence is consistently excellent—often superior to human junior/mid-tier consulting drafts. However, budgets remain headline-only, timelines contain errors, metrics are usually vague, and legal/operational realism is weak on high-stakes topics. A usable, client-ready version still requires weeks to months of skilled human refinement.

PlanExe removes 70–90 % of the labor for the planning scaffold on any topic, but the final 10–30 % that separates a polished document from a credible, defensible plan remains human-only work.

---

<details>
<summary><strong> Try it out now (Click to expand)</strong></summary>
<br>

You can generate 1 plan for free.

[Try it here →](https://app.mach-ai.com/planexe_early_access)

</details>

---

<details>
<summary><strong> Installation (Click to expand)</strong></summary>

<br>

**Prerequisite:** You are a python developer with machine learning experience.

# Installation

Typical python installation procedure:

```bash
git clone https://github.com/neoneye/PlanExe.git
cd PlanExe
python3 -m venv venv
source venv/bin/activate
(venv) pip install './worker_plan[gradio-ui]'
```

# Configuration

**Config A:** Run a model in the cloud using a paid provider. Follow the instructions in [OpenRouter](extra/openrouter.md).

**Config B:** Run models locally on a high-end computer. Follow the instructions for either [Ollama](extra/ollama.md) or [LM Studio](extra/lm_studio.md).

Recommendation: I recommend **Config A** as it offers the most straightforward path to getting PlanExe working reliably.

# Usage

PlanExe comes with a Gradio-based web interface. To start the local web server:

```bash
# Terminal 1: start the worker that runs the pipeline
(venv) uvicorn worker_plan.app:app --host 0.0.0.0 --port 8000

# Terminal 2: start the Gradio frontend (lives in ./frontend_single_user) and point it at the worker
(venv) PLANEXE_WORKER_PLAN_URL=http://localhost:8000 python frontend_single_user/app.py
```

This command launches a server at http://localhost:7860. Open that link in your browser, type a vague idea or description, and PlanExe will produce a detailed plan.

To stop the server at any time, press `Ctrl+C` in your terminal.

</details>

---

<details>
<summary><strong> Screenshots (Click to expand)</strong></summary>

<br>

You input a vague description of what you want and PlanExe outputs a plan.

[YouTube video: Using PlanExe to plan a lunar base](https://www.youtube.com/watch?v=7AM2F1C4CGI)

![Screenshot of PlanExe](/extra/planexe-humanoid-factory.jpg?raw=true "Screenshot of PlanExe")

</details>

---

<details>
<summary><strong> Help (Click to expand)</strong></summary>

<br>

For help or feedback.

Join the [PlanExe Discord](https://neoneye.github.io/PlanExe-web/discord).

</details>
