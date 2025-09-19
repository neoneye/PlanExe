# Week 1 NextJS Implementation Plan for PlanExe

/**
 * Author: Claude Code using Sonnet 4
 * Date: 2025-09-19
 * PURPOSE: Detailed Week 1 implementation plan for NextJS frontend that respects the complex Luigi pipeline architecture and existing data structures
 * SRP and DRY check: Pass - This document focuses solely on Week 1 planning and respects existing PlanExe architecture
 */

---

## 📋 **Critical Architecture Understanding**

After reading the 4000-line pipeline file, I now understand the true complexity:

### **Luigi Pipeline Architecture (DO NOT TOUCH)**
- **50+ Luigi Tasks** in complex dependency chains
- **File-based I/O pattern** with numbered outputs (FilenameEnum)
- **Multi-stage data flow** from initial prompt → strategic decisions → WBS → reports
- **LLM orchestration** with fallback mechanisms and retry logic
- **Progress tracking** via file completion percentage
- **Complex data transformation** between raw JSON and markdown at each stage

### **Key Data Flow Stages**
1. **Setup Phase**: StartTimeTask, SetupTask (initial prompt)
2. **Analysis Phase**: RedlineGate, PremiseAttack, IdentifyPurpose, PlanType
3. **Strategic Phase**: Potential levers → deduplication → enrichment → vital few → scenarios → selection
4. **Context Phase**: Physical locations, currency strategy, risk identification
5. **Assumptions Phase**: Make → distill → review → consolidate
6. **Planning Phase**: Pre-project assessment, project plan, governance phases (1-6)
7. **Execution Phase**: Team finding/enrichment, SWOT, expert review, data collection
8. **Structure Phase**: WBS Level 1 → Level 2 → Level 3, dependencies, durations
9. **Output Phase**: Pitch, schedule generation, review, executive summary, Q&A, premortem
10. **Report Phase**: HTML report compilation from all components

### **Critical Files and Dependencies**
- Each task produces **numbered outputs** (001-1-start_time.json, 018-2-wbs_level1.json, etc.)
- Tasks have **complex dependency chains** via `requires()` method
- **Context accumulation** - later tasks read outputs from multiple earlier tasks
- **Progress calculation** based on expected vs actual file completion
- **Final report** aggregates 20+ different markdown/HTML sections

---

## 🎯 **Week 1 Objectives**

### **Primary Goal**: Create NextJS UI that **perfectly replicates** current Gradio functionality

### **Key Principle**: **Zero backend changes** - work entirely with existing pipeline

### **Success Criteria**:
1. ✅ NextJS app can submit plans to existing Luigi pipeline
2. ✅ Real-time progress monitoring shows file completion progress
3. ✅ File management works with existing numbered output structure
4. ✅ All Gradio features replicated (model selection, speed settings, etc.)
5. ✅ Session management preserves user state across runs

---

## 📁 **NextJS Project Structure**

```
planexe-frontend/
├── src/
│   ├── app/
│   │   ├── page.tsx                    # Main planning interface
│   │   ├── layout.tsx                  # App layout
│   │   ├── globals.css                 # Global styles
│   │   └── api/                        # Next.js API routes (proxy layer)
│   │       ├── plans/
│   │       │   ├── route.ts           # POST /api/plans - create new plan
│   │       │   └── [planId]/
│   │       │       ├── route.ts       # GET /api/plans/[planId] - plan status
│   │       │       ├── progress/
│   │       │       │   └── route.ts   # GET /api/plans/[planId]/progress
│   │       │       ├── files/
│   │       │       │   └── route.ts   # GET /api/plans/[planId]/files
│   │       │       └── download/
│   │       │           └── route.ts   # GET /api/plans/[planId]/download
│   │       ├── config/
│   │       │   ├── llms/route.ts      # GET /api/config/llms - available models
│   │       │   └── prompts/route.ts   # GET /api/config/prompts - prompt catalog
│   │       └── session/
│   │           └── route.ts           # Session management
│   ├── components/
│   │   ├── ui/                        # shadcn/ui components
│   │   │   ├── button.tsx
│   │   │   ├── input.tsx
│   │   │   ├── textarea.tsx
│   │   │   ├── select.tsx
│   │   │   ├── progress.tsx
│   │   │   ├── card.tsx
│   │   │   └── badge.tsx
│   │   ├── planning/
│   │   │   ├── PlanForm.tsx           # Main plan creation form
│   │   │   ├── ModelSelector.tsx      # LLM model selection
│   │   │   ├── SpeedSelector.tsx      # Speed vs detail options
│   │   │   ├── PromptExamples.tsx     # Prompt catalog examples
│   │   │   └── ApiKeyInput.tsx        # OpenRouter API key input
│   │   ├── monitoring/
│   │   │   ├── ProgressMonitor.tsx    # Real-time pipeline progress
│   │   │   ├── StatusDisplay.tsx      # Current pipeline status
│   │   │   ├── FileList.tsx           # Live file listing
│   │   │   └── ErrorDisplay.tsx       # Error handling
│   │   ├── files/
│   │   │   ├── FileManager.tsx        # File browser interface
│   │   │   ├── DownloadButton.tsx     # Individual file downloads
│   │   │   └── ZipDownload.tsx        # ZIP archive download
│   │   └── layout/
│   │       ├── Header.tsx             # App header
│   │       ├── Navigation.tsx         # Navigation tabs
│   │       └── Footer.tsx             # App footer
│   ├── lib/
│   │   ├── api/
│   │   │   ├── client.ts              # API client wrapper
│   │   │   ├── plans.ts               # Plan-related API calls
│   │   │   ├── config.ts              # Configuration API calls
│   │   │   └── files.ts               # File operations
│   │   ├── types/
│   │   │   ├── plan.ts                # Plan-related types
│   │   │   ├── pipeline.ts            # Pipeline status types
│   │   │   ├── config.ts              # Configuration types
│   │   │   └── session.ts             # Session types
│   │   ├── utils/
│   │   │   ├── cn.ts                  # Class name utility
│   │   │   ├── format.ts              # Data formatting utilities
│   │   │   └── validation.ts          # Form validation
│   │   └── stores/
│   │       ├── session.ts             # Session state management
│   │       ├── planning.ts            # Planning state management
│   │       └── config.ts              # Configuration state
│   ├── hooks/
│   │   ├── useProgress.ts             # Progress monitoring hook
│   │   ├── useSession.ts              # Session management hook
│   │   ├── usePipeline.ts             # Pipeline interaction hook
│   │   └── useConfig.ts               # Configuration hook
│   └── styles/
│       └── globals.css                # Global CSS with Tailwind
├── public/
│   ├── favicon.ico
│   └── logo.png
├── package.json
├── tailwind.config.js
├── next.config.js
├── tsconfig.json
└── README.md
```

---

## 🔧 **Technical Implementation Details**

### **Day 1-2: Project Setup & Basic Structure**

#### **1. Initialize NextJS Project**
```bash
npx create-next-app@latest planexe-frontend --typescript --tailwind --app --eslint
cd planexe-frontend
```

#### **2. Install Core Dependencies**
```bash
# UI Components
npm install @radix-ui/react-select @radix-ui/react-progress @radix-ui/react-tabs
npm install @radix-ui/react-dialog @radix-ui/react-badge @radix-ui/react-label

# State Management
npm install zustand

# Form Handling
npm install react-hook-form @hookform/resolvers zod

# Utilities
npm install clsx tailwind-merge date-fns

# Dev Dependencies
npm install -D @types/node
```

#### **3. Setup shadcn/ui**
```bash
npx shadcn-ui@latest init
npx shadcn-ui@latest add button input textarea select progress card badge tabs dialog label
```

### **Day 3-4: API Proxy Layer**

#### **Core API Routes to Implement**

**1. Plan Management (`/api/plans/`)**
```typescript
// POST /api/plans - Create new plan
interface CreatePlanRequest {
  prompt: string;
  llmModel: string;
  speedVsDetail: 'ALL_DETAILS_BUT_SLOW' | 'FAST_BUT_SKIP_DETAILS';
  openrouterApiKey?: string;
}

interface CreatePlanResponse {
  planId: string;
  runDir: string;
  status: 'created' | 'running' | 'completed' | 'failed';
}
```

**2. Progress Monitoring (`/api/plans/[planId]/progress`)**
```typescript
interface PipelineProgress {
  planId: string;
  status: 'running' | 'completed' | 'failed' | 'stopped';
  progressPercentage: number;
  progressMessage: string;
  filesCompleted: number;
  totalExpectedFiles: number;
  currentTask: string;
  duration: number;
  estimatedTimeRemaining?: number;
}
```

**3. File Operations (`/api/plans/[planId]/files`)**
```typescript
interface PlanFile {
  filename: string;
  path: string;
  size: number;
  type: 'json' | 'md' | 'html' | 'csv' | 'txt';
  stage: string; // e.g., "setup", "analysis", "planning"
  lastModified: Date;
}

interface FileListResponse {
  files: PlanFile[];
  zipUrl?: string;
}
```

**4. Configuration (`/api/config/`)**
```typescript
interface LLMConfig {
  id: string;
  label: string;
  class: 'OpenRouter' | 'Ollama' | 'LMStudio';
  priority?: number;
  available: boolean;
}

interface PromptExample {
  uuid: string;
  title: string;
  prompt: string;
  tags: string[];
}
```

### **Day 5-6: Core UI Components**

#### **1. Main Planning Form**
```typescript
// components/planning/PlanForm.tsx
interface PlanFormData {
  prompt: string;
  llmModel: string;
  speedVsDetail: SpeedVsDetail;
  openrouterApiKey?: string;
}

const PlanForm = () => {
  // Form logic that replicates Gradio interface exactly
  // Submit/Retry/Stop button logic
  // Model selection from llm_config.json
  // Speed vs detail radio buttons
  // OpenRouter API key handling
}
```

#### **2. Progress Monitor**
```typescript
// components/monitoring/ProgressMonitor.tsx
const ProgressMonitor = ({ planId }: { planId: string }) => {
  // Polling-based progress updates (every 2 seconds)
  // Progress bar with percentage
  // Current task display
  // File completion counter
  // Duration and ETA
  // Error state handling
}
```

#### **3. File Manager**
```typescript
// components/files/FileManager.tsx
const FileManager = ({ planId }: { planId: string }) => {
  // File browser with pipeline stage grouping
  // Individual file downloads
  // ZIP archive download
  // File type icons and previews
  // Search and filter capabilities
}
```

### **Day 7: Integration & Testing**

#### **Pipeline Integration**
- Test with real Luigi pipeline execution
- Verify all file outputs are captured correctly
- Ensure progress tracking matches pipeline stages
- Test error handling and pipeline stopping

#### **Session Management**
- Browser-based session persistence
- Multiple concurrent plan management
- API key storage and security
- Settings preservation

---

## 🔄 **Data Flow Architecture**

### **Frontend → Backend Communication**

1. **Plan Creation Flow**:
   ```
   User Input → PlanForm → POST /api/plans →
   Create run directory → Start Luigi pipeline → Return plan ID
   ```

2. **Progress Monitoring Flow**:
   ```
   Plan ID → useProgress hook → GET /api/plans/[id]/progress →
   Read run directory files → Calculate completion → Return status
   ```

3. **File Management Flow**:
   ```
   Plan ID → FileManager → GET /api/plans/[id]/files →
   List run directory contents → Group by stage → Return file list
   ```

### **Luigi Pipeline Integration**

```typescript
// lib/api/pipeline.ts
class PipelineManager {
  async createPlan(request: CreatePlanRequest): Promise<string> {
    // 1. Generate run ID (YYYYMMDD_HHMMSS format)
    // 2. Create run directory structure
    // 3. Write start_time.json file
    // 4. Write initial plan.txt file
    // 5. Set environment variables
    // 6. Start Luigi pipeline subprocess
    // 7. Return plan ID
  }

  async getProgress(planId: string): Promise<PipelineProgress> {
    // 1. Read expected_filenames1.json
    // 2. List actual files in run directory
    // 3. Calculate completion percentage
    // 4. Check for completion/error flags
    // 5. Return progress status
  }

  async stopPipeline(planId: string): Promise<void> {
    // 1. Create pipeline_stop_requested.txt flag
    // 2. Terminate subprocess if running
    // 3. Clean up resources
  }
}
```

---

## 📊 **State Management Strategy**

### **Zustand Stores**

```typescript
// lib/stores/session.ts
interface SessionStore {
  currentPlanId: string | null;
  planHistory: PlanHistoryItem[];
  settings: UserSettings;

  // Actions
  setCurrentPlan: (planId: string) => void;
  addToHistory: (plan: PlanHistoryItem) => void;
  updateSettings: (settings: Partial<UserSettings>) => void;
}

// lib/stores/planning.ts
interface PlanningStore {
  plans: Map<string, PlanState>;

  // Actions
  createPlan: (request: CreatePlanRequest) => Promise<string>;
  updatePlanProgress: (planId: string, progress: PipelineProgress) => void;
  stopPlan: (planId: string) => Promise<void>;
}

// lib/stores/config.ts
interface ConfigStore {
  llmModels: LLMConfig[];
  promptExamples: PromptExample[];

  // Actions
  loadLLMModels: () => Promise<void>;
  loadPromptExamples: () => Promise<void>;
}
```

---

## 🚀 **Week 1 Deliverables**

### **Day 1-2 Deliverables**
- [ ] NextJS project initialized with TypeScript + Tailwind
- [ ] shadcn/ui components installed and configured
- [ ] Basic project structure with folder organization
- [ ] Core TypeScript interfaces defined

### **Day 3-4 Deliverables**
- [ ] API proxy routes implemented and tested
- [ ] Pipeline manager class for Luigi integration
- [ ] Session management system
- [ ] Configuration loading (LLM models, prompts)

### **Day 5-6 Deliverables**
- [ ] PlanForm component with full Gradio feature parity
- [ ] ProgressMonitor with real-time updates
- [ ] FileManager with download capabilities
- [ ] State management with Zustand stores

### **Day 7 Deliverables**
- [ ] End-to-end testing with real pipeline
- [ ] Error handling and edge cases
- [ ] Performance optimization
- [ ] Documentation and deployment preparation

---

## 🔍 **Critical Success Factors**

### **1. Respect Existing Architecture**
- **Never modify** Luigi pipeline or task files
- **Preserve** all FilenameEnum output patterns
- **Maintain** existing environment variable patterns
- **Honor** all existing data structures and formats

### **2. Handle Pipeline Complexity**
- **Account for** 50+ task dependency chains
- **Support** complex progress calculation based on file completion
- **Handle** multi-stage data transformations
- **Manage** large file outputs (reports can be substantial)

### **3. Session Management**
- **Support** multiple concurrent plans
- **Preserve** user settings across sessions
- **Handle** browser refresh without losing state
- **Manage** long-running pipeline processes

### **4. Error Handling**
- **Detect** pipeline failures and stops
- **Handle** missing or corrupted files
- **Manage** subprocess communication issues
- **Provide** clear user feedback

---

## 📈 **Post-Week 1 Roadmap**

### **Week 2: Enhancement & Polish**
- Real-time SSE updates instead of polling
- Advanced file preview capabilities
- Better error recovery mechanisms
- Performance optimizations

### **Week 3: Multi-tenancy Foundation**
- Database layer for plan persistence
- User authentication system
- Tenant-scoped plan management
- API security enhancements

### **Week 4: White-label Features**
- Dynamic theming system
- Configurable branding
- Industry-specific prompt catalogs
- Custom domain support

---

## 🎯 **Success Metrics**

### **Technical Metrics**
- [ ] 100% feature parity with current Gradio app
- [ ] All 50+ Luigi tasks execute correctly
- [ ] Progress tracking accuracy within 5%
- [ ] File operations work for all output types
- [ ] Session persistence across browser restarts

### **User Experience Metrics**
- [ ] Form submission under 2 seconds
- [ ] Progress updates every 2 seconds
- [ ] File downloads work for all browsers
- [ ] Mobile-responsive design
- [ ] Intuitive navigation

### **Performance Metrics**
- [ ] Initial page load under 3 seconds
- [ ] API response times under 500ms
- [ ] Memory usage stable during long pipelines
- [ ] No memory leaks in progress monitoring
- [ ] Handles 10+ concurrent plans

---

## 🔒 **Risk Mitigation**

### **High-Risk Areas**
1. **Pipeline Integration Complexity** - 4000-line codebase with intricate dependencies
2. **File System Operations** - Complex numbered file patterns and directory structures
3. **Long-running Processes** - Luigi pipelines can run 30+ minutes
4. **State Management** - Multiple concurrent plans with complex progress tracking

### **Mitigation Strategies**
1. **Incremental Testing** - Test each Luigi task integration individually
2. **Comprehensive Error Handling** - Graceful degradation for all failure modes
3. **Robust Progress Tracking** - Multiple fallback mechanisms for progress calculation
4. **Thorough Documentation** - Clear interfaces for future team members

---

This Week 1 plan provides a **solid foundation** for the NextJS implementation while **fully respecting** the complex Luigi pipeline architecture. The focus is on **perfect replication** of existing functionality before adding any new features.