# Railway Configuration for `frontend_single_user`

```
PLANEXE_GRADIO_SERVER_NAME="0.0.0.0"
PLANEXE_CONFIG_PATH="/app"
PLANEXE_WORKER_PLAN_URL="http://worker_plan:8000"
PLANEXE_PASSWORD="password"
```

In the deploy log I can see this
```
Starting Gradio UI on 0.0.0.0:8080
```
So Railway seems to prefer using port 8080.

## Logging
- Set `PLANEXE_LOG_LEVEL` (for example `INFO`, `WARNING`, or `DEBUG`) in Railway to control both the worker service and pipeline console logs.
- Console logs are now plain text (no ANSI color codes), so Railway logs stay readable.
