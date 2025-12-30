# Railway Configuration

```
OPENROUTER_API_KEY="SECRET-KEY-HERE"
PLANEXE_IFRAME_GENERATOR_CONFIRMATION_PRODUCTION_URL="https://example.com/iframe_confirm_production"
PLANEXE_IFRAME_GENERATOR_CONFIRMATION_DEVELOPMENT_URL="https://example.com/iframe_confirm_development"
SQLALCHEMY_DATABASE_URI="postgresql+psycopg2://user:password@host:5432/planexe"
PLANEXE_CONFIG_PATH="/app"
PLANEXE_RUN_DIR="/app/run"
PLANEXE_LOG_LEVEL="INFO"
PLANEXE_WORKER_ID="1"
```

- `PLANEXE_IFRAME_GENERATOR_CONFIRMATION_*` are required; the worker exits early if they are missing.
- Use `SQLALCHEMY_DATABASE_URI` for Railway's Postgres URL; otherwise the worker falls back to the `PLANEXE_WORKER_PLAN_DB_*` host/port/user/password defaults.
- Set `OPENROUTER_API_KEY` (and any other model keys in `llm_config.json`) so the pipeline can call the LLM provider.
- `PLANEXE_RUN_DIR` stores pipeline output inside the container; logs follow `PLANEXE_LOG_LEVEL`.
