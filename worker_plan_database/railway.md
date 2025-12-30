# Railway Configuration

Create minimum 1 instance. With more traffic, create N instances.

Below is an example of what a `worker_plan_database_1` instance may be configured as:

```
OPENROUTER_API_KEY="SECRET-KEY-HERE"
PLANEXE_WORKER_ID="1"
PLANEXE_IFRAME_GENERATOR_CONFIRMATION_PRODUCTION_URL="https://example.com/iframe_confirm_production"
PLANEXE_IFRAME_GENERATOR_CONFIRMATION_DEVELOPMENT_URL="https://example.com/iframe_confirm_development"
```

- Set `OPENROUTER_API_KEY` (and any other model keys in `llm_config.json`) so the pipeline can call the LLM provider.
- `PLANEXE_WORKER_ID` a unique id that identifies what worker instance it is.
- `PLANEXE_IFRAME_GENERATOR_CONFIRMATION_*` are required; the worker exits early if they are missing.
