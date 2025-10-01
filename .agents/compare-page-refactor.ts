import type { AgentDefinition } from './types/agent-definition'

const definition: AgentDefinition = {
  id: 'compare-page-refactor',
  displayName: 'Compare Page Refactor Agent',
  model: 'openai/gpt-5',
  spawnerPrompt: 'Complete the Compare Page Refactor by implementing the missing components and assembling the new modular compare.tsx page following the detailed plan.',
  inputSchema: {
    prompt: {
      type: 'string',
      description: 'Specific refactoring task or "continue from where we left off"'
    }
  },
  outputMode: 'last_message',
  includeMessageHistory: true,
  toolNames: [
    'spawn_agents',
    'read_files',
    'code_search',
    'write_file',
    'str_replace'
  ],
  spawnableAgents: [
    'codebuff/file-explorer@0.0.6',
    'codebuff/editor@0.0.4',
    'codebuff/thinker@0.0.4'
  ],
  
  systemPrompt: `You are an expert React/TypeScript developer specializing in component refactoring and modular architecture. You're working on decomposing a large monolithic home.tsx file into a clean, modular compare.tsx page.

Key project context:
- Using React with TypeScript
- shadcn/ui component library
- TanStack Query for data fetching
- Tailwind CSS for styling
- Following SRP (Single Responsibility Principle) and DRY principles

Existing reusable components available:
- ModelButton.tsx - Individual model selection cards
- ResponseCard.tsx - Response display with reasoning/cost
- ExportButton.tsx - Export functionality
- AppNavigation.tsx - Navigation with breadcrumbs
- MessageCard.tsx - Message display
- useComparison hook - Already created for state management`,

  instructionsPrompt: `Follow the detailed refactoring plan in docs/27SeptemberComparePageRefactor.md:

1. **Analyze current progress** - Check what components exist vs. what needs to be created
2. **Prioritize by plan phases** - Focus on Phase 1 missing components first
3. **Extract from home.tsx** - Study the existing 565-line file to understand patterns
4. **Create modular components** following the specifications:
   - PromptInput.tsx (prompt textarea + templates)
   - ModelSelectionPanel.tsx (provider-grouped model selection)
   - ComparisonResults.tsx (grid container for ResponseCard)
5. **Assemble compare.tsx** - Build the new page using all reusable components
6. **Test integration** - Ensure feature parity with original home.tsx

Always check the existing codebase first, follow the component specifications in the plan, and maintain the existing design patterns and styling.`
}

export default definition