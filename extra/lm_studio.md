# Using PlanExe with LM Studio

[LM Studio](https://lmstudio.ai/) is an open source app for macOS/Windows/Linux for running LLMs on your own computer. It's great for troubleshooting.

PlanExe processes more text than regular chat. You will need expensive hardware to run a LLM at a reasonable speed.

In the `llm_config.json` find a config that starts with `lmstudio-` such as `"lmstudio-qwen2.5-7b-instruct-1m"`.

Inside LM Studio, find the model with that exact id and download it. Here is the qwen model on
[huggingface](https://huggingface.co/lmstudio-community/Qwen2.5-7B-Instruct-1M-GGUF). It's around 4.5 GB to download.

Inside LM Studio, go to the `Developer` page (CMD+2 or Windows+2 or Ctrl+2). Start the server.
The UI should show `Status: Running [x]` and `Reachable at: http://127.0.0.1:1234`.

## Troubleshooting

Inside PlanExe, when clicking `Submit`, a new `Output Dir` should be created containing a `log.txt`. Open that file and scroll to the bottom, see if there are any error messages about what is wrong.

Report your issue on [Discord](https://neoneye.github.io/PlanExe-web/discord). Please include info about your system, such as: "I'm on macOS with M1 Max with 64 GB.".
