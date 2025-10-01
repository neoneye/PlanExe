/**
 * Author: Buffy the Base Agent
 * Date: 2025-10-01
 * PURPOSE: A Railway CLI debugging agent that gathers non-interactive diagnostics from deployed Railway projects using the installed Railway CLI and RAILWAY_TOKEN present in the environment. It returns structured JSON consumable by other agents. Avoids exposing secrets. Safe defaults.
 * SRP and DRY check: Pass - Single responsibility (Railway diagnostics via CLI), reuses existing agent patterns
 */

import type {
  AgentDefinition,
  AgentStepContext,
  ToolCall,
} from './types/agent-definition'

const definition: AgentDefinition = {
  id: 'railway-debugger',
  displayName: 'Railway Debugger',
  model: 'qwen/qwen3-coder-flash',

  toolNames: ['run_terminal_command', 'add_message', 'set_output', 'end_turn'],

  spawnerPrompt:
    'Spawn to collect non-interactive diagnostics from Railway using the CLI (version, auth status, environments, services, deployments, and optional logs) and return structured results.',

  inputSchema: {
    prompt: {
      type: 'string',
      description: 'Optional description of what to investigate (e.g., outages, failing deploys)'
    },
    params: {
      type: 'object',
      properties: {
        serviceName: { type: 'string', description: 'Target service name for logs' },
        environmentName: { type: 'string', description: 'Target environment name for logs' },
        since: { type: 'string', description: 'Logs time window, e.g. 30m, 2h, 1d (default 30m)' },
        includeEnvVarValues: { type: 'boolean', description: 'DANGEROUS: if true, allow fetching env var values; defaults to false (names only or skipped). Not recommended.' }
      }
    }
  },

  outputMode: 'structured_output',
  outputSchema: {
    type: 'object',
    properties: {
      status: { type: 'string', description: 'ok | needs_setup (cli missing) | auth_required | error' },
      message: { type: 'string' },
      diagnostics: {
        type: 'object',
        properties: {
          cli: {
            type: 'object',
            properties: {
              installed: { type: 'boolean' },
              version: { type: 'string' }
            }
          },
          auth: {
            type: 'object',
            properties: {
              isAuthenticated: { type: 'boolean' },
              whoami: { type: 'object' }
            }
          },
          environments: { type: 'array', items: { type: 'object' } },
          services: { type: 'array', items: { type: 'object' } },
          deployments: { type: 'array', items: { type: 'object' } },
          logs: { type: 'array', items: { type: 'object' } }
        }
      }
    },
    required: ['status']
  },

  systemPrompt: `You are a non-interactive Railway CLI debugging assistant.
- Assume Railway CLI is installed and RAILWAY_TOKEN is provided via OS environment. Do NOT read or print token values.
- Always use --json where supported for machine-readable output.
- Never expose secrets. Do not run 'railway variables' unless explicitly asked to and only if includeEnvVarValues=true; even then warn and mask values when possible.
- Prefer read-only commands (version, whoami, environments, services, deployments, logs).
- If CLI is missing, return status=needs_setup with guidance. If unauthenticated, return status=auth_required with guidance.
- Parse CLI JSON outputs and produce a compact structured set_output per the output schema.`,

  instructionsPrompt: `Perform a safe Railway diagnostic run and return structured JSON:

1) Check CLI availability and version
- run: railway --version
- If the command fails, set status=needs_setup and a helpful message (how to install Railway CLI) and end.

2) Check authentication
- run: railway whoami --json
- If unauthenticated or error due to missing token, set status=auth_required and provide guidance (ensure RAILWAY_TOKEN or RAILWAY_API_TOKEN in OS environment). Do not try to read .env or print any token.

3) Collect project diagnostics (read-only)
- run: railway environments --json
- run: railway services --json
- run: railway deployments --json

4) Optional logs (only if params.serviceName & params.environmentName are provided)
- run: railway logs --service "{serviceName}" --env "{environmentName}" --since "{since||30m}" --json
- If unsupported or multiple matches, gracefully continue without logs.

5) Synthesize results
- Parse the JSON outputs.
- Produce set_output with: status=ok (or appropriate), diagnostics: { cli, auth, environments, services, deployments, logs? }, message optional.

6) Safety
- Never include secrets in output.
- Do not execute write operations.
- Keep output concise.`,

  handleSteps: function* ({ params }: AgentStepContext) {
    // Step 1: CLI available?
    yield {
      toolName: 'run_terminal_command',
      input: {
        command: 'railway --version',
        process_type: 'SYNC',
        timeout_seconds: 20,
      },
    } satisfies ToolCall

    // Step 2: Auth status
    yield {
      toolName: 'run_terminal_command',
      input: {
        command: 'railway whoami --json',
        process_type: 'SYNC',
        timeout_seconds: 30,
      },
    } satisfies ToolCall

    // Step 3: Read-only inventory
    yield {
      toolName: 'run_terminal_command',
      input: {
        command: 'railway environments --json',
        process_type: 'SYNC',
        timeout_seconds: 30,
      },
    } satisfies ToolCall

    yield {
      toolName: 'run_terminal_command',
      input: {
        command: 'railway services --json',
        process_type: 'SYNC',
        timeout_seconds: 30,
      },
    } satisfies ToolCall

    yield {
      toolName: 'run_terminal_command',
      input: {
        command: 'railway deployments --json',
        process_type: 'SYNC',
        timeout_seconds: 40,
      },
    } satisfies ToolCall

    // Step 4: Optional logs if parameters provided
    if (params?.serviceName && params?.environmentName) {
      const since = params?.since || '30m'
      const svc = String(params.serviceName).replace(/\"/g, '')
      const env = String(params.environmentName).replace(/\"/g, '')
      yield {
        toolName: 'run_terminal_command',
        input: {
          command: `railway logs --service "${svc}" --env "${env}" --since ${since} --json`,
          process_type: 'SYNC',
          timeout_seconds: 60,
        },
      } satisfies ToolCall
    }

    // Let the model parse results and call set_output
    yield {
      toolName: 'add_message',
      input: {
        role: 'assistant',
        content: 'I will now parse the CLI JSON outputs, synthesize a compact diagnostics object, and set structured output per schema.'
      }
    } satisfies ToolCall

    yield 'STEP_ALL'
  },
}

export default definition
