# PlanExe

**What does PlanExe do:** Turn your idea into a comprehensive plan in minutes, not months.

- An business plan for a [Minecraft-themed escape room](https://neoneye.github.io/PlanExe-web/20251016_minecraft_escape_report.html).
- An business plan for a [Faraday cage manufacturing company](https://neoneye.github.io/PlanExe-web/20250720_faraday_enclosure_report.html).
- An pilot project for a [Human as-a Service](https://neoneye.github.io/PlanExe-web/20251012_human_as_a_service_protocol_report.html).
- See more [examples here](https://neoneye.github.io/PlanExe-web/examples/).

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

# Terminal 2: start the Gradio frontend (lives in ./frontend_gradio) and point it at the worker
(venv) WORKER_PLAN_URL=http://localhost:8000 python frontend_gradio/app_text2plan.py
```

This command launches a server at http://localhost:7860. Open that link in your browser, type a vague idea or description, and PlanExe will produce a detailed plan.

To stop the server at any time, press `Ctrl+C` in your terminal.

</details>

---

<details>
<summary><strong> Screenshots (Click to expand)</strong></summary>

<br>

You input a vague description of what you want and PlanExe outputs a plan. [See generated plans here](https://neoneye.github.io/PlanExe-web/use-cases/).

![Video of PlanExe](/extra/planexe-humanoid-factory.gif?raw=true "Video of PlanExe")

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
