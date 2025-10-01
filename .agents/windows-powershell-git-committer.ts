/**
 * Author: Claude Code using Sonnet 4
 * Date: 2025-01-29
 * PURPOSE: Windows PowerShell specific git commit agent that uses cheap/fast LLM 
 *          and generates proper PowerShell syntax for git commits using multiple -m flags
 *          instead of problematic embedded newlines. Solves the Windows Command Prompt
 *          quote parsing issues that were causing git commit failures.
 * SRP/DRY check: Pass - Single responsibility (Windows PowerShell git commits), 
 *                       reuses existing agent patterns
 * shadcn/ui: N/A - This is a backend agent definition
 */

import type {
  AgentDefinition,
  AgentStepContext,
  ToolCall,
} from './types/agent-definition'

const definition: AgentDefinition = {
  id: 'windows-powershell-git-committer',
  displayName: 'Windows PowerShell Git Committer',
  publisher: 'mark-barney',
  // Use a cheap and fast model for this task
  model: 'qwen/qwen3-coder-flash',
  
  toolNames: ['read_files', 'run_terminal_command', 'add_message', 'end_turn'],

  inputSchema: {
    prompt: {
      type: 'string',
      description: 'What changes to commit',
    },
  },

  spawnerPrompt:
    'Spawn when you need to commit code changes to git with proper Windows PowerShell syntax using multiple -m flags',

  systemPrompt:
    'You are an expert in Windows PowerShell and Git. Your job is to create git commits using proper Windows PowerShell syntax with multiple -m flags to avoid quote parsing issues.',

  instructionsPrompt: `Follow these steps to create a Windows PowerShell compatible git commit:

1. **Analyze changes** with git diff and git log
2. **Read relevant files** for context if needed
3. **Stage appropriate files** using git add
4. **Create commit using Windows PowerShell syntax**:

**CRITICAL: Windows PowerShell Git Commit Syntax**
- Use multiple -m flags instead of embedded newlines
- Each -m flag creates a separate paragraph with automatic blank line separation
- Use double quotes around each message segment
- DO NOT use embedded \\n or backtick-n characters
- DO NOT try to create multiline strings with quotes

**Correct PowerShell Syntax (Method 1 - Multiple -m flags):**
\`\`\`powershell
git commit -m "feat: Add user authentication" -m "Implement JWT-based login system" -m "Requires USER_SECRET environment variable"
\`\`\`

**Alternative Method (Method 2 - File-based if quotes fail):**
\`\`\`powershell
# Create temporary commit message file
Set-Content -Path "commit-msg.txt" -Value "feat: Add user authentication

Implement JWT-based login system.

Requires USER_SECRET environment variable."

# Commit using file
git commit -F commit-msg.txt

# Clean up
del commit-msg.txt
\`\`\`

**WRONG (Do not use):**
- \`git commit -m "feat: Add user authentication\\nImplement JWT system"\`
- \`git commit -m "feat: Add user authentication\`nImplement JWT system"\`
- \`git commit -m "feat: Add user authentication

Implement JWT system"\`

**Message Structure:**
- First -m flag: Subject line (50 chars or less)
- Second -m flag: Body paragraph explaining what/why
- Third -m flag (optional): Additional details, breaking changes, etc.
- Add footer tags like "🤖 Generated with Codebuff" as separate -m flag

**Commit Message Format:**
- Use conventional commits: feat:, fix:, refactor:, docs:, etc.
- Keep subject line under 50 characters
- Use imperative mood ("Add feature" not "Added feature")
- Include context about why the change was made`,

  handleSteps: function* ({ agentState, prompt, params }: AgentStepContext) {
    // Step 1: Analyze current git state
    yield {
      toolName: 'run_terminal_command',
      input: {
        command: 'git status --porcelain',
        process_type: 'SYNC',
        timeout_seconds: 30,
      },
    } satisfies ToolCall

    yield {
      toolName: 'run_terminal_command',
      input: {
        command: 'git diff --staged',
        process_type: 'SYNC',
        timeout_seconds: 30,
      },
    } satisfies ToolCall

    yield {
      toolName: 'run_terminal_command',
      input: {
        command: 'git diff',
        process_type: 'SYNC',
        timeout_seconds: 30,
      },
    } satisfies ToolCall

    yield {
      toolName: 'run_terminal_command',
      input: {
        command: 'git log --oneline -5',
        process_type: 'SYNC',
        timeout_seconds: 30,
      },
    } satisfies ToolCall

    // Step 2: Guide AI to read relevant files if needed
    yield {
      toolName: 'add_message',
      input: {
        role: 'assistant',
        content:
          "I've analyzed the git status and changes. Now I'll read any relevant files to understand the context, then stage and commit the changes using proper Windows PowerShell syntax with multiple -m flags.",
      },
      includeToolCall: false,
    } satisfies ToolCall

    // Step 3: Let AI generate steps to read files and stage changes
    yield 'STEP'

    // Step 4: Guide AI to create the commit with proper PowerShell syntax
    yield {
      toolName: 'add_message',
      input: {
        role: 'assistant',
        content:
          "Now I'll create the commit using proper Windows PowerShell syntax with multiple -m flags. Each -m flag will be a separate paragraph to avoid quote parsing issues.",
      },
      includeToolCall: false,
    } satisfies ToolCall

    yield 'STEP_ALL'
  },
}

export default definition
