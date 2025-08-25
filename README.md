# PlanExe

What if you could plan a dystopian police state from a single prompt?

That's what PlanExe does. It took a two-sentence idea about deploying police robots in Brussels and generated a multi-faceted, 50-page strategic and tactical plan.

[See the "Police Robots" plan here →](https://neoneye.github.io/PlanExe-web/20250824_police_robots_report.html)

---

<details>
<summary><strong> Try it out now (Click to expand)</strong></summary>
<br>

If you are not a developer. You can generate 1 plan for free, beyond that it cost money.

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
(venv) pip install '.[gradio-ui]'
```

# Configuration

**Config A:** Run a model in the cloud using a paid provider. Follow the instructions in [OpenRouter](extra/openrouter.md).

**Config B:** Run models locally on a high-end computer. Follow the instructions for either [Ollama](extra/ollama.md) or [LM Studio](extra/lm_studio.md).

Recommendation: I recommend **Config A** as it offers the most straightforward path to getting PlanExe working reliably.

# Usage

PlanExe comes with a Gradio-based web interface. To start the local web server:

```bash
(venv) python -m planexe.plan.app_text2plan
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
