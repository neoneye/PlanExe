# Using PlanExe with Ollama

[Ollama](https://ollama.com/) is an open source app for macOS/Windows/Linux for running LLMs on your own computer.

PlanExe processes more text than regular chat. You will need expensive hardware to run a LLM at a reasonable speed.

## Configuration

In the `llm_config.json` find a config that starts with `ollama-` such as `"ollama-llama3.1"`.

On the [Ollama Search Models](https://ollama.com/search) website. Find the corresponding model. Go to the info page for the model:
[ollama/library/llama3.1](https://ollama.com/library/llama3.1). The info page shows how to install the model on your computer, in this case `ollama run llama3.1`. To get started, go for a `8b` model that is `4.9GB`.

## Troubleshooting

Use the command line to compare Ollama's list of installed models with the configurations in your `llm_config.json` file. Run:

```bash
PROMPT> ollama list
NAME                    ID              SIZE      MODIFIED
phi4:latest             ac896e5b8b34    9.1 GB    6 weeks ago
qwen2.5-coder:latest    2b0496514337    4.7 GB    2 months ago
llama3.1:latest         42182419e950    4.7 GB    5 months ago    
```

Inside PlanExe, when clicking `Submit`, a new `Output Dir` should be created containing a `log.txt`. Open that file and scroll to the bottom, see if there are any error messages about what is wrong.

Report your issue on [Discord](https://neoneye.github.io/PlanExe-web/discord). Please include info about your system, such as: "I'm on macOS with M1 Max with 64 GB.".
