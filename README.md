# PlanExe

What if you could plan a dystopian police state from a single prompt?

That's what PlanExe does. It took a two-sentence idea about deploying police robots in Brussels and generated a multi-faceted, 50-page strategic and tactical plan.

[See the "Police Robots" plan here →](https://neoneye.github.io/PlanExe-web/20250824_police_robots_report.html)

---

<details>
<summary><strong> Try it out now (Click to expand)</strong></summary>
<br>

You can generate 1 plan for free. Beyond that it cost money, or you can install PlanExe locally.

[Try it here →](https://app.mach-ai.com/planexe_early_access)

</details>

---

<details>
<summary><strong> Installation (Click to expand)</strong></summary>

<br>

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

# Community

Have questions? Need help? Join the [PlanExe Discord](https://neoneye.github.io/PlanExe-web/discord) to chat about PlanExe, share ideas, and get support.

# :heart: Thank you to all [supporters](https://github.com/neoneye/PlanExe/stargazers)

If you like this project, please give it a star ⭐ and 📢 spread the word in your network or social media:

[![Share on X](https://img.shields.io/twitter/url?style=social&url=https%3A%2F%2Fgithub.com%2Fneoneye%2FPlanExe)](https://x.com/intent/post?text=PlanExe:%20Stop%20starting%20from%20scratch!%20Turn%20vague%20ideas%20into%20actionable%20plans%20in%20minutes%20with%20this%20open-source%20AI%20planner.%20Check%20out%20PlanExe%20on%20GitHub:%20https%3A%2F%2Fgithub.com%2Fneoneye%2FPlanExe)
[![Share on LinkedIn](https://img.shields.io/badge/Share%20on-LinkedIn-blue)](https://www.linkedin.com/feed/?linkOrigin=LI_BADGE&shareActive=true&shareUrl=https://github.com/neoneye/PlanExe)
[![Share on Hacker News](https://img.shields.io/badge/-Share%20on%20Hacker%20News-orange)](https://news.ycombinator.com/submitlink?u=https://github.com/neoneye/PlanExe&t=Transforms%20your%20idea%20into%20a%20plan)
[![Share on Reddit](https://img.shields.io/badge/-Share%20on%20Reddit-blue)](https://www.reddit.com/submit?url=https%3A%2F%2Fgithub.com%2Fneoneye%2FPlanExe&title=Transforms+your+idea+into+a+plan&type=LINK)
