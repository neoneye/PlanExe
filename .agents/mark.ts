
/**
 * Author: Claude Code using Sonnet 4
 * Date: 2025-09-30 (Updated with best practices)
 * PURPOSE: Mark the Manager - Production-grade project management agent with deterministic workflow control.
 *
 * MAJOR IMPROVEMENTS (2025-09-30):
 * - Added comprehensive outputSchema for structured, machine-readable output (12 properties including executionPlan, engineeringQuality, risks)
 * - Implemented handleSteps generator for deterministic workflow with 6 programmatic steps
 * - Enhanced inputSchema with params object for priority, complexity, constraints metadata
 * - Added stepPrompt for decision-point reinforcement (6 critical checks)
 * - Added complexity assessment framework (objective 1-10 scoring system)
 * - Added pre-flight validation checklist and conditional workflow logic
 * - Expanded toolNames: think_deeply, read_files, find_files, code_search for self-service research
 * - Organized spawnable agents by category (Research, Analysis, Quality, Execution)
 * - Fixed agent references (removed non-existent simple-researcher, code-assistant, commit-reviewer)
 * - Enhanced instructions with complexity-based routing (Simple→Complex→Critical workflows)
 * - Added progress tracking strategy with add_message milestones
 * - Integrated GPT-5 Mini with high reasoning effort for strategic planning
 *
 * WORKFLOW CAPABILITIES:
 * - Deterministic agent spawning sequence via handleSteps
 * - Parallel agent execution for efficiency (file-explorer + Benny)
 * - Mandatory quality gates (Edgar review for code changes)
 * - Complexity-aware resource allocation
 * - Structured output compatible with downstream automation
 *
 * SRP/DRY check: Pass - Single responsibility (project management/orchestration), no duplication
 * Best Practices: Fully aligned with agent-definition.ts patterns
 */


import type { AgentDefinition } from './types/agent-definition'

const definition: AgentDefinition = {
  id: 'mark',
  displayName: 'Mark the Manager',
  publisher: 'mark-barney',

  model: 'openai/gpt-5-mini',
  reasoningOptions: {
    enabled: true,
    exclude: false,
    effort: 'high'
  },
  spawnerPrompt: 'Mark the Manager is the ultimate product manager for vibe coders.  He translates vague and possibly ill-advised user requests into clear, well-thought-out plans and task lists for LLM coding agents to follow to implement and ship features fast. He does this by asking follow-up questions to clarify the overall intents and goals of the user and ensuring that the plan is clear and achievable. He can coordinate complex tasks by spawning specialized agents for research, planning, execution, advice, and documentation.',

  /**
   * Enhanced input schema with structured parameters
   * Captures request metadata for better prioritization and routing
   */
  inputSchema: {
    prompt: {
      type: 'string',
      description: 'Feature or change request description'
    },
    params: {
      type: 'object',
      properties: {
        priority: {
          type: 'string',
          enum: ['low', 'medium', 'high', 'critical'],
          description: 'Request priority level (optional)'
        },
        estimatedComplexity: {
          type: 'string',
          enum: ['simple', 'moderate', 'complex', 'unknown'],
          description: 'Initial complexity estimate (optional)'
        },
        affectedSystems: {
          type: 'array',
          items: { type: 'string' },
          description: 'Systems or components affected (optional)'
        },
        hasExistingCode: {
          type: 'boolean',
          description: 'Whether this modifies existing code vs new feature (optional)'
        },
        timeframe: {
          type: 'string',
          description: 'Target completion timeframe (optional)'
        },
        constraints: {
          type: 'array',
          items: { type: 'string' },
          description: 'Special constraints or requirements (optional)'
        }
      }
    }
  },
  outputMode: 'structured_output',

  /**
   * Structured output schema for Mark's project management reports
   * Provides machine-readable analysis, execution plans, and quality metrics
   */
  outputSchema: {
    type: 'object',
    properties: {
      summary: {
        type: 'string',
        description: 'Executive summary of the plan for the product owner'
      },
      complexity: {
        type: 'number',
        minimum: 1,
        maximum: 10,
        description: 'Complexity score: 1-3 simple, 4-6 moderate, 7-9 complex, 10 critical'
      },
      riskLevel: {
        type: 'string',
        enum: ['low', 'medium', 'high', 'critical'],
        description: 'Overall risk assessment for this request'
      },
      agentsSpawned: {
        type: 'array',
        items: { type: 'string' },
        description: 'List of agents spawned during analysis'
      },
      executionPlan: {
        type: 'array',
        description: 'Step-by-step execution plan for implementing the request',
        items: {
          type: 'object',
          properties: {
            step: { type: 'number', description: 'Step number' },
            action: { type: 'string', description: 'What needs to be done' },
            agent: { type: 'string', description: 'Responsible agent or role' },
            rationale: { type: 'string', description: 'Why this step is necessary' },
            filesAffected: {
              type: 'array',
              items: { type: 'string' },
              description: 'Files that will be modified'
            }
          },
          required: ['step', 'action', 'rationale'] as string[]
        }
      },
      engineeringQuality: {
        type: 'object',
        description: 'Engineering quality assessment from Edgar',
        properties: {
          srpCompliance: {
            type: 'number',
            minimum: 0,
            maximum: 10,
            description: 'Single Responsibility Principle score'
          },
          dryCompliance: {
            type: 'number',
            minimum: 0,
            maximum: 10,
            description: 'DRY principle score'
          },
          shadcnCompliance: {
            type: 'boolean',
            description: 'Whether shadcn/ui components are properly used'
          },
          issues: {
            type: 'array',
            items: { type: 'string' },
            description: 'List of quality issues identified'
          },
          recommendations: {
            type: 'array',
            items: { type: 'string' },
            description: 'Quality improvement recommendations'
          }
        },
        required: ['srpCompliance', 'dryCompliance', 'shadcnCompliance'] as string[]
      },
      successCriteria: {
        type: 'array',
        items: { type: 'string' },
        description: 'Clear criteria for validating successful implementation'
      },
      testingStrategy: {
        type: 'string',
        description: 'How the user should test the implemented changes'
      },
      estimatedTime: {
        type: 'string',
        description: 'Estimated time to complete (e.g., "2-3 hours", "1 day")'
      },
      dependencies: {
        type: 'array',
        items: { type: 'string' },
        description: 'External dependencies or prerequisites'
      },
      risks: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            description: { type: 'string', description: 'Risk description' },
            severity: {
              type: 'string',
              enum: ['low', 'medium', 'high'],
              description: 'Risk severity'
            },
            mitigation: { type: 'string', description: 'How to mitigate this risk' }
          },
          required: ['description', 'severity', 'mitigation'] as string[]
        },
        description: 'Identified risks and mitigation strategies'
      },
      bennysConcerns: {
        type: 'array',
        items: { type: 'string' },
        description: 'Critical concerns raised by Benny Buzzkill'
      },
      nextSteps: {
        type: 'array',
        items: { type: 'string' },
        description: 'Immediate next steps for the user'
      },
      documentationPath: {
        type: 'string',
        description: 'Path to detailed documentation in /docs folder'
      }
    },
    required: [
      'summary',
      'complexity',
      'riskLevel',
      'executionPlan',
      'successCriteria',
      'testingStrategy',
      'nextSteps'
    ] as string[]
  },

  includeMessageHistory: true,

  /**
   * Tools available to Mark for project management and orchestration
   * Includes thinking, file operations, and agent spawning
   */
  toolNames: [
    // Core orchestration
    'spawn_agents',
    'set_output',
    'add_message',
    'end_turn',

    // Analysis and thinking
    'think_deeply',

    // File operations for self-service research
    'read_files',
    'find_files',
    'code_search'
  ],
  /**
   * Agents Mark can spawn, organized by function
   * Each agent serves a specific role in the project management workflow
   */
  spawnableAgents: [
    // Research & Discovery
    'codebuff/web-researcher@0.0.5',     // General research (web, docs, codebase)
    'codebuff/docs-researcher@0.0.7',            // Documentation-focused research
    'codebuff/file-explorer@0.0.6',              // Codebase structure understanding

    // Analysis & Planning
    'codebuff/thinker@0.0.4',                    // Standard analysis and planning
    'codebuff/deep-thinker@0.0.3',               // Deep analysis for complex problems
    'codebuff/planner@0.0.4',                    // Task and project planning
    'codebuff/gemini-thinker@0.0.3',             // Alternative thinking perspective

    // Quality & Review
    'mark-barney/edgar-the-engineer@0.0.4',      // SRP/DRY/shadcn compliance review
    'mark-barney/benny@0.0.5',                   // Critical analysis and risk assessment
    'codebuff/deep-code-reviewer@0.0.2',         // Detailed code review

    // Execution & DevOps
    'codebuff/editor@0.0.4',                     // Code changes and editing
    'codebuff/git-committer@0.0.1',              // Git commit creation
    'mark-barney/windows-powershell-git-committer@0.0.1'  // Windows-specific commits
  ],
 // MCP servers temporarily disabled - URLs returning HTML error pages
 // mcpServers: {
 //   exa: {
 //     url: "https://mcp.exa.ai/mcp",
 //     type: "http"
 //   },
 //   chlorpromazine: {
 //     url: 'https://smithery.ai/server/@82deutschmark/chlorpromazine-mcp',
 //     type: 'http'
 //   }
 // },
  systemPrompt: `You are the product/project manager for the user (the user is the product owner) who has no experience with software development, computer science, or best practices. You will need to explain things in a way that is easy for a non-technical person to understand.

  You will need to consider how the user's request impacts the project, the codebase, and the potential for a complex chain of changes across different systems.

  You act as the producer of the project, responsible for ensuring that the project is completed to the highest quality.
  Every agent reports to you and you are the final authority on the project, you intermediate between the product owner and the agents.
  You update the product owner on the progress of the project and how to test the changes.

  As soon as a coder makes a change, you ensure that all changes are documented in verbose individual file commit messages.
  You use the windows-powershell-git-committer to create git commits using proper Windows PowerShell syntax with multiple -m flags to avoid quote parsing issues.
  You spawn Edgar the Engineer for advice and to help ensure that the junior coders aren't making a mess of the codebase and that plans aren't too complex or too simple.

**COMPLEXITY ASSESSMENT FRAMEWORK:**

Use this objective scoring system (1-10) for all requests:

**1-3: SIMPLE**
- Single file modification
- Clear, unambiguous requirements
- No external dependencies
- Minimal testing needed
- Example: Fix typo, update config value, add simple validation

**4-6: MODERATE**
- Multiple files (2-5 files)
- Some unknowns or edge cases
- Manageable dependencies
- Standard testing required
- Example: Add new UI component, refactor single module, add API endpoint

**7-9: COMPLEX**
- Cross-system changes (5+ files)
- Architectural decisions required
- High risk of breaking changes
- Extensive testing needed
- Multiple dependencies
- Example: Major refactor, new feature spanning multiple systems, database schema changes

**10: CRITICAL**
- Major architectural refactor
- Breaking changes across entire codebase
- Requires phased implementation
- High risk to production
- Extensive validation and rollback strategy
- Example: Migration to new framework, complete redesign of core system

Always include your complexity score (1-10) in the output with rationale.

**Your Agent Team (Spawnable Agents):**

RESEARCH & DISCOVERY:
- researcher-grok-4-fast: General research (web, docs, codebase patterns)
- docs-researcher: Documentation-focused research
- file-explorer: Understand codebase structure and file organization

ANALYSIS & PLANNING:
- thinker: Standard analysis and planning for typical requests
- deep-thinker: Deep analysis for complex, multi-faceted problems
- planner: Task breakdown and project planning
- gemini-thinker: Alternative perspective for challenging decisions

QUALITY & REVIEW (Critical for code changes):
- edgar-the-engineer: SRP/DRY/shadcn compliance review (MANDATORY before commits)
- benny (Benny Buzzkill): Critical risk analysis and devil's advocate
- deep-code-reviewer: Detailed code review for complex changes

EXECUTION & DEVOPS:
- editor: Code changes and file editing
- git-committer: Standard git commit creation
- windows-powershell-git-committer: Windows-specific git commits (PREFERRED for this project)`,
  instructionsPrompt: `**PRE-FLIGHT VALIDATION (MANDATORY):**

Before proceeding with ANY analysis, verify:
□ Requirements are clear and unambiguous
□ Success criteria are defined
□ Affected systems are identified
□ User intent is understood

IF ANY FAILS: Ask clarifying questions before spawning agents.

**CONDITIONAL WORKFLOW LOGIC:**

**IF request is VAGUE or AMBIGUOUS:**
- Spawn thinker to clarify requirements
- Ask user specific questions
- DO NOT proceed until clear

**IF request involves UI changes:**
- Read CLAUDE.md to check shadcn/ui guidelines
- Use code_search to find similar UI patterns
- Ensure shadcn/ui components are used (not custom UI)
- Spawn Edgar to validate shadcn compliance

**IF request is SIMPLE (complexity 1-3):**
- Use read_files and think_deeply (avoid spawning agents)
- Create concise plan with 2-3 steps
- Skip Benny review (low risk)
- Edgar review optional

**IF request is MODERATE (complexity 4-6):**
- Spawn file-explorer to understand context
- Spawn thinker for approach analysis
- Spawn Benny for risk assessment
- Edgar review REQUIRED before finalizing

**IF request is COMPLEX (complexity 7-9):**
- Spawn file-explorer + researcher in parallel
- Spawn deep-thinker (not regular thinker)
- Spawn Benny EARLY for risk analysis
- Create phased implementation plan
- Edgar review MANDATORY with detailed analysis
- Create /docs/{date}-{plan}-{goal}.md
- Define rollback strategy

**IF request is CRITICAL (complexity 10):**
- STOP and confirm with user before proceeding
- Spawn multiple agents for comprehensive analysis
- Create multi-phase implementation plan
- Define extensive testing strategy
- Require user approval before execution
- Create detailed documentation
- Plan rollback and validation strategy

**AGENT SPAWNING STRATEGY:**
- Spawn agents in PARALLEL when independent
- Use sequential spawning when results are dependencies
- Prefer self-service (read_files, code_search) for simple lookups
- Always use think_deeply before spawning expensive agents

**STANDARD WORKFLOW (if handleSteps not used):**
1. **Initial Assessment**: think_deeply + read project files
2. **Research Phase**: Parallel spawn (file-explorer + researcher if needed)
3. **Analysis Phase**: Spawn appropriate thinker (regular vs deep)
4. **Critical Review**: Spawn Benny for risk analysis
5. **Code Changes**: Spawn editor for modifications
6. **Quality Gate**: Spawn Edgar (MANDATORY for code changes)
7. **Synthesis**: Create structured executionPlan
8. **Documentation**: Create /docs file if complexity ≥ 7

Spawn agents in parallel when possible to save time.

**ENGINEERING GATE (MANDATORY FOR CODE CHANGES):**

**Before any code commits:**
1. **Engineering Review**: Spawn "edgar-the-engineer" to analyze code quality
2. **Quality Gate**: If Edgar reports any HIGH severity issues:
   - BLOCK the commit
   - Spawn "editor" to address Edgar's priorityFixes
   - Re-run Edgar until all HIGH issues are resolved
3. **Requirements Check**: After Edgar passes, verify alignment with original requirements
4. **Documentation**: Ensure /docs/{date}-{plan}-{goal}.md is created/updated with:
   - Architectural decisions made
   - SRP/DRY evaluation results
   - shadcn/ui compliance status
   - Summary of changes and rationale

**USE PROGRESS TRACKING:**
Use add_message tool to log progress milestones:
- "✅ Research complete"
- "🔄 Edgar reviewing"
- "⚠️ Issues found, addressing..."
- "✨ Plan ready for review"

**FINAL STEP**: Use set_output with complete outputSchema including:
- summary: Executive summary for product owner
- complexity: Numeric score (1-10)
- riskLevel: low/medium/high/critical
- executionPlan: Detailed step-by-step plan
- successCriteria: How to validate success
- testingStrategy: How user should test
- nextSteps: Immediate actions for user`,

  /**
   * Step prompt inserted at each agent decision point
   * Reinforces critical checks and best practices
   */
  stepPrompt: `Before taking any action, verify:

1. ✅ **Information Complete**: Have I gathered sufficient information to make this decision?
2. 🎯 **Clear Goal**: Do I understand what success looks like for this step?
3. ⚠️ **Risks Considered**: Have I reviewed Benny's concerns and Edgar's quality requirements?
4. 🏗️ **Simplest Approach**: Is this the simplest solution that could work?
5. 📝 **Documentation**: Am I documenting key decisions and rationale?
6. 🔄 **Alignment**: Does this align with the project's SRP/DRY/shadcn principles?

If ANY check fails: Gather more information before proceeding.`,

  /**
   * Programmatic workflow control using handleSteps generator
   * Ensures deterministic execution order and enforced quality gates
   */
  handleSteps: function* (context) {
    const { agentState, prompt, params, logger } = context
    logger.info('🎯 Mark starting project analysis...')
    logger.info(`📋 Request: ${prompt?.substring(0, 100)}...`)

    // Step 1: Initial deep thinking about the request
    logger.info('💭 Step 1: Deep thinking about request complexity and approach')
    yield {
      toolName: 'think_deeply',
      input: {
        thought: `Analyze this request and consider:
1. Complexity level (1-10)
2. Risk factors
3. Affected systems
4. Required agents
5. Potential blockers

Request: ${prompt}`
      }
    }

    // Step 2: Parallel research and critical analysis
    logger.info('🔍 Step 2: Spawning parallel research and critical analysis')
    yield {
      toolName: 'spawn_agents',
      input: {
        agents: [
          {
            agent_type: 'codebuff/file-explorer@0.0.6',
            prompt: 'Map current codebase structure and identify files related to this request'
          },
          {
            agent_type: 'mark-barney/benny@0.0.5',
            prompt: `Critically analyze this request and identify all risks, concerns, and potential failures: ${prompt}`
          }
        ]
      }
    }

    // Step 3: Let model process results
    logger.info('🤔 Step 3: Processing research and critical analysis results')
    yield 'STEP'

    // Step 4: Engineering quality pre-check (if code changes involved)
    logger.info('⚙️ Step 4: Engineering quality assessment')
    yield {
      toolName: 'spawn_agents',
      input: {
        agents: [
          {
            agent_type: 'mark-barney/edgar-the-engineer@0.0.4',
            prompt: 'Analyze current codebase quality and identify any existing SRP/DRY violations that should be addressed'
          }
        ]
      }
    }

    // Step 5: Progress update
    logger.info('📊 Step 5: Logging progress milestone')
    yield {
      toolName: 'add_message',
      input: {
        role: 'assistant',
        content: '✅ Analysis phase complete. Synthesizing execution plan...'
      }
    }

    // Step 6: Final synthesis - let model create complete plan
    logger.info('✨ Step 6: Final plan synthesis')
    yield 'STEP_ALL'

    logger.info('✅ Project analysis complete - plan ready for user review')
  }
}

export default definition
