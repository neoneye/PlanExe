# Troubleshooting a stuck pipeline

The gradio app (`app_text2plan.py`) starts the `run_plan_pipeline` process via a `Popen` call. I guess the gradio app is a slightly different environment than via commandline `python -m src.plan.run_plan_pipeline`.

## Manually resuming a stuck pipeline

In the UI copy/paste the run_id that is stuck, eg: `20250209_030626`

Insert it on commandline, and run the pipeline.

```bash
PROMPT> RUN_ID=20250209_030626 python -m src.plan.run_plan_pipeline
```

## Why does the pipeline get stuck?

The `log.txt` contains the output from the logger with `DEBUG` level, the most detailed.
Alas the `log.txt` have little info about what exactly went wrong. 
The exceptions rarely have useful info.

- **Censorship**, if it's a sensitive topic, then the LLM may refuse to answer.
- **Timeout**, that happens often when using AI providers in the cloud.
- **Invalid json**, responds from the server that doesn't adhere to the json schema.
- **Too long answer**, if the respond from the server gets too long so it gets truncated, so it's invalid json.
- **Other**, there may be other reasons that I'm not aware of, please let me know if you encounter such a scenario.
