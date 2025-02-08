# PlanExe

PlanExe is a planning AI. You input a vague description of what you want and PlanExe outputs a plan.

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

Getting PlanExe working with OpenRouter. (PlanExe can use other AI providers, such as Ollama, LM Studio).

1. Go to [OpenRouter](https://openrouter.ai/), create an account, purchase 5 USD in credits (plenty for making a several plans), and generate an API key.

2. Copy `.env.example` to a new file called `.env`

3. Open the `.env` file in a text editor and insert your OpenRouter API key.
```OPENROUTER_API_KEY='INSERT YOUR KEY HERE'```

# Usage

PlanExe comes with a Gradio-based web interface. To start the local web server:

```bash
(venv) python -m src.plan.app_text2plan
```

This command launches a server at http://localhost:7860. Open that link in your browser, type a vague idea or description, and PlanExe will produce a detailed plan.

To stop the server at any time, press `Ctrl+C` in your terminal.

# Community & Support

Join the [PlanExe Discord](https://discord.gg/RXQmnxsqAA) to chat about PlanExe, share ideas, and get help.
