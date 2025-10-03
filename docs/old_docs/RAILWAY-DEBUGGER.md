# Railway Debugger Agent

Purpose: Non-interactive diagnostics for deployed Railway projects using the Railway CLI.
- Uses OS environment RAILWAY_TOKEN (or RAILWAY_API_TOKEN) — never reads or prints secrets
- Runs read-only commands: version, whoami, environments, services, deployments, optional logs
- Returns structured JSON other agents can consume

Setup
- Install Railway CLI:
  - Windows PowerShell: npm i -g @railway/cli
  - Verify: railway --version
- Set token in your shell environment (not only .env):
  - PowerShell (current session): $Env:RAILWAY_TOKEN = "<project_token>"
  - PowerShell (persist): setx RAILWAY_TOKEN "<project_token>"
  - CMD (current session): set RAILWAY_TOKEN=<project_token>
  - Bash: export RAILWAY_TOKEN="<project_token>"
- Verify auth: railway whoami --json

Safety
- Agent never prints token values
- Skips railway variables unless you explicitly allow includeEnvVarValues=true (not recommended)
- Only uses read-only CLI commands

Spawn Examples
- Mention: @railway-debugger Check production health for planexe-api
- Programmatic:
  {
    "agents": [
      {
        "agent_type": "railway-debugger",
        "prompt": "Check production health",
        "params": {
          "serviceName": "planexe-api",
          "environmentName": "production",
          "since": "1h"
        }
      }
    ]
  }

What it returns
{
  "status": "ok | needs_setup | auth_required | error",
  "message": "optional human-readable note",
  "diagnostics": {
    "cli": { "installed": true, "version": "x.y.z" },
    "auth": { "isAuthenticated": true, "whoami": { /* masked */ } },
    "environments": [ /* from railway environments --json */ ],
    "services": [ /* from railway services --json */ ],
    "deployments": [ /* from railway deployments --json */ ],
    "logs": [ /* only if service/environment provided */ ]
  }
}

Troubleshooting
- needs_setup: Install CLI and ensure railway is on PATH
- auth_required: Set RAILWAY_TOKEN or RAILWAY_API_TOKEN in your shell environment
- Logs not returned: Provide both serviceName and environmentName; confirm they exist
