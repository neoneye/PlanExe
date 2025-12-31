# Railway Configuration

```
OPENROUTER_API_KEY="SECRET-KEY-HERE"
PLANEXE_CONFIG_PATH="/app"
PLANEXE_HOST_RUN_DIR="/app/run"
PLANEXE_RUN_DIR="/app/run"
PLANEXE_WORKER_RELAY_PROCESS_OUTPUT="true"
```

## Volume - None

The `worker_plan` gets initialized via env vars. It does write to disk inside the `run` dir.
