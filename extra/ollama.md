# Using PlanExe with Ollama

[Ollama](https://ollama.com/) is an open source app for macOS/Windows/Linux for running LLMs on your own computer (or on a remote computer).

PlanExe processes more text than regular chat. You will need expensive hardware to run a LLM at a reasonable speed.

## Configuration

In the `llm_config.json` find a config that starts with `ollama-` such as `"ollama-llama3.1"`.

On the [Ollama Search Models](https://ollama.com/search) website. Find the corresponding model. Go to the info page for the model:
[ollama/library/llama3.1](https://ollama.com/library/llama3.1). The info page shows how to install the model on your computer, in this case `ollama run llama3.1`. To get started, go for a `8b` model that is `4.9GB`.

## Troubleshooting

Use the command line to compare Ollama's list of installed models with the configurations in your `llm_config.json` file. Run:

```bash
PROMPT> ollama list
NAME                                             ID              SIZE      MODIFIED       
hf.co/unsloth/Llama-3.1-Tulu-3-8B-GGUF:Q4_K_M    08fe35cc5878    4.9 GB    19 minutes ago    
phi4:latest                                      ac896e5b8b34    9.1 GB    6 weeks ago       
qwen2.5-coder:latest                             2b0496514337    4.7 GB    2 months ago      
llama3.1:latest                                  42182419e950    4.7 GB    5 months ago      
```

Inside PlanExe, when clicking `Submit`, a new `Output Dir` should be created containing a `log.txt`. Open that file and scroll to the bottom, see if there are any error messages about what is wrong.

Report your issue on [Discord](https://neoneye.github.io/PlanExe-web/discord). Please include info about your system, such as: "I'm on macOS with M1 Max with 64 GB.".

## How to add a new Ollama model to `llm_config.json`

You can find models and installation instructions here:
- [Ollama](https://ollama.com/search) – Overview of popular models, curated by the Ollama team.
- [Hugging Face](https://huggingface.co/docs/hub/ollama) – A vast collection of GGUF models.

For a model to work with PlanExe, it must meet the following criteria:

- Minimum 8192 output tokens.
- Support structured output.
- Reliable. Avoid fragile setups where it works one day, but not the next day. If it's a beta version, be aware that it may stop working.
- Low latency.

Steps to add a model:

1. Follow the instructions on Ollama or Hugging Face to install the model.
1. Copy the model id from the `ollama list` command, such as `llama3.1:latest`
2. Paste the model id into the `llm_config.json`.
3. Restart PlanExe to apply the changes.

## Run Ollama on a remote computer

In `llm_config.json`, insert `base_url` with the url to run on.

```json
"ollama-llama3.1": {
    "comment": "This runs on on a remote computer. Requires Ollama to be installed.",
    "class": "Ollama",
    "arguments": {
        "model": "llama3.1:latest",
        "base_url": "http://example.com:11434",
        "temperature": 0.5,
        "request_timeout": 120.0,
        "is_function_calling_model": false
    }
}
```
