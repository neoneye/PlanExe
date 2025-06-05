# PlanExe changelog

## 2025-june-5

I have renamed the root dir of the project from `src` to `planexe`.
Since `import planexe` makes more sense than `import src`.

When running the Gradio UI. The new way is:

```bash
PROMPT> python -m planexe.plan.app_text2plan
```

The old way was like this:

```bash
PROMPT> python -m src.plan.app_text2plan
```


## 2025-may-27

I have migrated from `requirements.txt` to `pyproject.toml`.

Old way to install PlanExe:

```bash
(venv) pip install -r requirements.txt
```

New way to install PlanExe:

```bash
(venv) pip install .[gradio-ui]
```

## 2025-may-30

Until now `run_plan_pipeline.py` has only been able to use 1 LLM. If that LLM failed to respond, the entire pipeline stopped.
It was up to the user to select another LLM, and click `Retry`. I guess few people could get it to work.

Now the `run_plan_pipeline.py` can cycles through multiple LLMs. Should one LLM fail, the next LLM is tried.
In most cases Gemini is the fastest at responding, but there are a few areas where it fails to respond.
Here OpenAI is good at responding, but much slower.

The Gradio UI settings panel now has an `Auto` radio button.

- When the `Auto` button is selected, the LLMs with `priority` are used.
- When a specific LLM is selected, then only that LLM is used.

The `llm_config.json` now has a `"priority"` value for the LLMs that are to be used with the `Auto` mode. 

- Here `"priority": 1` is for the LLM that is the most preferred.
- Here `"priority": 2` is for the LLM that is the medium preferred.
- Here `"priority": 3` is for the LLM that is the least preferred.

LLMs that doesn't have a `"priority"` are ignored when using the `Auto` mode.
