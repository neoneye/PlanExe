# PlanExe White-Label SaaS MVP Implementation Plan

**Author: Claude Code using Opus 4.1**
**Date: 2025-09-19**
**PURPOSE: Detailed MVP implementation plan for transforming PlanExe into a white-label multi-tenant SaaS platform**
**SRP and DRY check: Pass - This document focuses solely on MVP planning and reuses existing PlanExe architecture**

---

## 🎯 **Executive Summary**
PlanAnything!
Transform the robust PlanExe Python planning engine into a white-label multi-tenant SaaS MVP that demonstrates:

1. **Multi-tenant capability** - Multiple organizations using isolated instances
2. **White-label branding** - Dynamic theming and customization per tenant
3. **Industry specialization** - Different planning workflows for different industries
4. **Modern frontend** - Next.js interface replacing the current Gradio UI
5. **API-first architecture** - Clean separation between business logic and presentation

**Timeline: 4-6 weeks for fully functional MVP**

---

## 🏗️ **Current Architecture Analysis**

### **Existing Strengths (KEEP & EXTEND)**

#### **1. Luigi Pipeline Architecture**
```python
# Existing robust pipeline orchestration in planexe/plan/run_plan_pipeline.py
- WBS generation (Level 1, 2, 3)
- Expert cost estimation
- Risk identification and analysis
- Resource planning
- Timeline generation
- Report compilation
```
**MVP Strategy**: Extend pipeline with tenant-specific configurations without modifying core logic.

#### **2. FastAPI REST Layer**
```python
# Already exists in planexe_api/api.py
- Plan creation and management
- Real-time progress monitoring via SSE
- File management and downloads
- PostgreSQL persistence
```
**MVP Strategy**: Add tenant awareness to existing endpoints + new tenant management endpoints.

#### **3. LLM Factory Pattern**
```python
# Flexible multi-provider support in planexe/llm_factory.py
- OpenRouter (paid models)
- Ollama (local models)
- LM Studio (local models)
- Auto-fallback capabilities
```
**MVP Strategy**: Add tenant-specific LLM configurations and prompt catalogs.

#### **4. Database Foundation**
```sql
-- Existing robust schema in planexe_api/database.py
- plans table with comprehensive tracking
- llm_interactions table for audit/cost tracking
- plan_files table for output management
- plan_metrics table for analytics
```
**MVP Strategy**: Add tenant tables and foreign key relationships to existing schema.

### **Current Limitations (REPLACE/UPGRADE)**

#### **1. Gradio UI**
- Single-user interface
- No branding customization
- Basic UX/design
- No multi-tenancy support

**MVP Solution**: Replace with Next.js 14 + TypeScript + Tailwind CSS

#### **2. File Storage**
- Local filesystem only
- No tenant isolation
- No scalable storage strategy

**MVP Solution**: Add tenant-scoped directories + cloud storage ready architecture

#### **3. Configuration Management**
- Single global LLM configuration
- No tenant-specific settings
- Hardcoded prompt catalogs

**MVP Solution**: Dynamic tenant configuration system

---

## 🏢 **MVP Multi-Tenant Architecture**

### **Phase 1: Backend Multi-Tenancy (Week 1-2)**

#### **1.1 Database Schema Extensions**

```sql
-- New tenant management tables
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_key VARCHAR(50) UNIQUE NOT NULL,  -- URL-friendly identifier
    name VARCHAR(255) NOT NULL,
    industry VARCHAR(100),  -- 'software', 'nonprofit', 'church', 'consulting'
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    -- Basic white-label configuration
    config JSONB DEFAULT '{}'::jsonb,  -- Stores branding, features, etc.

    -- Status and limits
    status VARCHAR(20) DEFAULT 'active',  -- active, suspended, trial
    plan_limit INTEGER DEFAULT 10,

    -- Contact info
    admin_email VARCHAR(255),
    admin_name VARCHAR(255)
);

-- Tenant branding and customization
CREATE TABLE tenant_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    config_type VARCHAR(50) NOT NULL,  -- 'branding', 'features', 'prompts'
    config_data JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Industry-specific prompt catalogs
CREATE TABLE tenant_prompts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    uuid VARCHAR(255) NOT NULL,  -- Compatible with existing PromptCatalog
    title VARCHAR(255),
    prompt TEXT NOT NULL,
    category VARCHAR(100),
    industry_specific BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Extend existing plans table
ALTER TABLE plans ADD COLUMN tenant_id UUID REFERENCES tenants(id);
ALTER TABLE plans ADD COLUMN industry_context VARCHAR(100);
ALTER TABLE plans ADD COLUMN custom_config JSONB DEFAULT '{}'::jsonb;

-- Add tenant context to LLM interactions
ALTER TABLE llm_interactions ADD COLUMN tenant_id UUID REFERENCES tenants(id);

-- Add indexes for performance
CREATE INDEX idx_plans_tenant_id ON plans(tenant_id);
CREATE INDEX idx_llm_interactions_tenant_id ON llm_interactions(tenant_id);
CREATE INDEX idx_tenants_tenant_key ON tenants(tenant_key);
```

#### **1.2 Tenant Configuration Model**

```python
# planexe_api/tenant_models.py
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from enum import Enum

class IndustryType(str, Enum):
    SOFTWARE = "software"
    NONPROFIT = "nonprofit"
    CHURCH = "church"
    CONSULTING = "consulting"
    GENERIC = "generic"

@dataclass
class TenantBranding:
    logo_url: Optional[str] = None
    primary_color: str = "#3B82F6"  # Default blue
    secondary_color: str = "#1E40AF"
    accent_color: str = "#F59E0B"
    font_family: str = "Inter"
    custom_css: Optional[str] = None

@dataclass
class TenantFeatures:
    max_plans: int = 10
    advanced_analytics: bool = False
    custom_prompts: bool = True
    api_access: bool = False
    white_label_domain: bool = False
    priority_support: bool = False

@dataclass
class TenantConfig:
    tenant_id: str
    tenant_key: str
    name: str
    industry: IndustryType
    branding: TenantBranding
    features: TenantFeatures
    admin_email: str
    admin_name: str
    status: str = "active"

    # Industry-specific configurations
    custom_fields: Dict[str, Any] = None
    workflow_config: Dict[str, Any] = None
    prompt_customizations: Dict[str, Any] = None
```

#### **1.3 FastAPI Tenant Endpoints**

```python
# planexe_api/tenant_api.py
@app.post("/api/tenants", response_model=TenantResponse)
async def create_tenant(request: CreateTenantRequest, db: Session = Depends(get_database)):
    """Create a new tenant (admin-only in MVP)"""

@app.get("/api/tenants/{tenant_key}", response_model=TenantConfigResponse)
async def get_tenant_config(tenant_key: str, db: Session = Depends(get_database)):
    """Get tenant configuration for frontend theming"""

@app.put("/api/tenants/{tenant_key}/config")
async def update_tenant_config(tenant_key: str, config: TenantConfigUpdate, db: Session = Depends(get_database)):
    """Update tenant branding and features"""

# Modified existing endpoints to be tenant-aware
@app.post("/api/{tenant_key}/plans", response_model=PlanResponse)
async def create_tenant_plan(tenant_key: str, request: CreatePlanRequest, db: Session = Depends(get_database)):
    """Create plan for specific tenant"""

@app.get("/api/{tenant_key}/plans", response_model=List[PlanResponse])
async def list_tenant_plans(tenant_key: str, db: Session = Depends(get_database)):
    """List plans for specific tenant"""

@app.get("/api/{tenant_key}/prompts", response_model=List[PromptExample])
async def get_tenant_prompts(tenant_key: str, db: Session = Depends(get_database)):
    """Get tenant-specific prompt catalog"""
```

#### **1.4 Tenant-Aware Pipeline Execution**

```python
# planexe_api/tenant_pipeline.py
def run_tenant_plan_job(plan_id: str, tenant_key: str, request: CreatePlanRequest):
    """Enhanced pipeline runner with tenant context"""

    # Load tenant configuration
    tenant_config = get_tenant_config(tenant_key)

    # Set tenant-specific environment variables
    environment = os.environ.copy()
    environment[PipelineEnvironmentEnum.TENANT_KEY.value] = tenant_key
    environment[PipelineEnvironmentEnum.INDUSTRY_TYPE.value] = tenant_config.industry.value
    environment[PipelineEnvironmentEnum.TENANT_CONFIG.value] = json.dumps(tenant_config.dict())

    # Create tenant-scoped output directory
    tenant_run_dir = run_dir / tenant_key / plan_id
    tenant_run_dir.mkdir(parents=True, exist_ok=True)

    # Rest of pipeline execution with tenant context...
```

### **Phase 2: Next.js Frontend (Week 2-3)**

#### **2.1 Next.js 14 Project Structure**

```
planexe-frontend/
├── src/
│   ├── app/
│   │   ├── (tenant)/
│   │   │   └── [tenantKey]/
│   │   │       ├── page.tsx              # Dashboard
│   │   │       ├── plans/
│   │   │       │   ├── page.tsx          # Plans list
│   │   │       │   ├── create/page.tsx   # Create plan
│   │   │       │   └── [planId]/page.tsx # Plan details
│   │   │       └── layout.tsx            # Tenant-aware layout
│   │   ├── api/                          # Next.js API routes (proxy to Python)
│   │   │   ├── tenants/[tenantKey]/
│   │   │   └── proxy/
│   │   ├── admin/                        # Admin dashboard (optional)
│   │   └── globals.css
│   ├── components/
│   │   ├── ui/                           # shadcn/ui components
│   │   ├── tenant/                       # Tenant-specific components
│   │   ├── planning/                     # Planning workflow components
│   │   └── layout/                       # Layout components
│   ├── lib/
│   │   ├── api/                          # API clients
│   │   ├── hooks/                        # Custom hooks
│   │   ├── stores/                       # Zustand stores
│   │   ├── utils/                        # Utilities
│   │   └── types/                        # TypeScript types
│   ├── styles/
│   │   ├── globals.css
│   │   └── tenant-themes.css
│   └── middleware.ts                     # Route protection & tenant routing
├── package.json
├── tailwind.config.js                    # Dynamic theme configuration
├── next.config.js
└── README.md
```

#### **2.2 Dynamic Tenant Theming System**

```typescript
// lib/tenant/theme.ts
export interface TenantTheme {
  colors: {
    primary: string;
    secondary: string;
    accent: string;
  };
  fonts: {
    heading: string;
    body: string;
  };
  logo?: string;
  customCSS?: string;
}

export const useTenantTheme = (tenantKey: string) => {
  const [theme, setTheme] = useState<TenantTheme | null>(null);

  useEffect(() => {
    // Fetch tenant configuration from API
    fetchTenantConfig(tenantKey).then(config => {
      setTheme(config.branding);

      // Apply CSS custom properties for dynamic theming
      document.documentElement.style.setProperty('--primary', config.branding.primary_color);
      document.documentElement.style.setProperty('--secondary', config.branding.secondary_color);
      document.documentElement.style.setProperty('--accent', config.branding.accent_color);
    });
  }, [tenantKey]);

  return theme;
};
```

```css
/* styles/tenant-themes.css */
:root {
  --primary: #3B82F6;
  --secondary: #1E40AF;
  --accent: #F59E0B;
}

.tenant-branded {
  background-color: rgb(var(--primary));
  color: rgb(var(--primary-foreground));
}

.tenant-branded-secondary {
  background-color: rgb(var(--secondary));
}

/* Tailwind CSS integration */
.bg-tenant-primary {
  background-color: var(--primary);
}

.text-tenant-primary {
  color: var(--primary);
}

.border-tenant-primary {
  border-color: var(--primary);
}
```

#### **2.3 Tenant-Aware Components**

```typescript
// components/tenant/TenantLayout.tsx
interface TenantLayoutProps {
  children: React.ReactNode;
  tenantKey: string;
}

export const TenantLayout = ({ children, tenantKey }: TenantLayoutProps) => {
  const theme = useTenantTheme(tenantKey);
  const tenantConfig = useTenantConfig(tenantKey);

  return (
    <div className="min-h-screen bg-background">
      <TenantHeader
        logo={theme?.logo}
        title={tenantConfig?.name}
        tenantKey={tenantKey}
      />
      <main className="container mx-auto p-6">
        {children}
      </main>
      <TenantFooter tenantConfig={tenantConfig} />
    </div>
  );
};

// components/planning/PlanningWorkflow.tsx
interface PlanningWorkflowProps {
  tenantKey: string;
  industryType: IndustryType;
}

export const PlanningWorkflow = ({ tenantKey, industryType }: PlanningWorkflowProps) => {
  const prompts = useTenantPrompts(tenantKey);
  const workflow = usePlanningWorkflow(industryType);

  return (
    <div className="space-y-6">
      <Card className="tenant-branded">
        <CardHeader>
          <CardTitle>Create {getIndustryLabel(industryType)} Plan</CardTitle>
        </CardHeader>
        <CardContent>
          <IndustrySpecificForm
            industryType={industryType}
            prompts={prompts}
            onSubmit={handlePlanSubmission}
          />
        </CardContent>
      </Card>

      <PlanProgressMonitor />
      <PlanResultsDisplay />
    </div>
  );
};
```

#### **2.4 State Management with Zustand**

```typescript
// lib/stores/tenant.ts
interface TenantStore {
  currentTenant: TenantConfig | null;
  tenants: TenantConfig[];

  // Actions
  loadTenant: (tenantKey: string) => Promise<void>;
  setCurrentTenant: (tenant: TenantConfig) => void;
  updateTenantConfig: (tenantKey: string, config: Partial<TenantConfig>) => Promise<void>;
}

export const useTenantStore = create<TenantStore>((set, get) => ({
  currentTenant: null,
  tenants: [],

  loadTenant: async (tenantKey: string) => {
    const tenant = await api.getTenant(tenantKey);
    set({ currentTenant: tenant });
  },

  setCurrentTenant: (tenant: TenantConfig) => {
    set({ currentTenant: tenant });
  },

  updateTenantConfig: async (tenantKey: string, config: Partial<TenantConfig>) => {
    await api.updateTenantConfig(tenantKey, config);
    // Refresh current tenant if it's the one being updated
    if (get().currentTenant?.tenant_key === tenantKey) {
      get().loadTenant(tenantKey);
    }
  }
}));

// lib/stores/planning.ts
interface PlanningStore {
  currentPlan: Plan | null;
  plans: Plan[];
  isCreating: boolean;
  progress: PlanProgress | null;

  // Actions
  createPlan: (tenantKey: string, request: CreatePlanRequest) => Promise<Plan>;
  loadTenantPlans: (tenantKey: string) => Promise<void>;
  watchPlanProgress: (planId: string) => void;
  stopWatchingProgress: () => void;
}
```

### **Phase 3: Industry Specialization (Week 3-4)**

#### **3.1 Industry-Specific Configurations**

```typescript
// lib/industry/configurations.ts
export const INDUSTRY_CONFIGURATIONS = {
  software: {
    name: "Software Development",
    promptCategories: [
      "Architecture & System Design",
      "Sprint Planning",
      "API Development",
      "DevOps & Deployment",
      "Technical Documentation"
    ],
    customFields: [
      { name: "tech_stack", label: "Technology Stack", type: "multiselect" },
      { name: "team_size", label: "Team Size", type: "number" },
      { name: "timeline", label: "Project Timeline", type: "select" },
      { name: "deployment_target", label: "Deployment Target", type: "select" }
    ],
    reportSections: [
      "Technical Architecture",
      "Development Phases",
      "Testing Strategy",
      "Deployment Plan",
      "Risk Assessment"
    ]
  },

  nonprofit: {
    name: "Non-Profit Organization",
    promptCategories: [
      "Program Development",
      "Fundraising Campaigns",
      "Volunteer Coordination",
      "Community Outreach",
      "Grant Applications"
    ],
    customFields: [
      { name: "program_type", label: "Program Type", type: "select" },
      { name: "target_population", label: "Target Population", type: "text" },
      { name: "budget_range", label: "Budget Range", type: "select" },
      { name: "impact_metrics", label: "Success Metrics", type: "multiselect" }
    ],
    reportSections: [
      "Program Overview",
      "Impact Strategy",
      "Resource Requirements",
      "Fundraising Plan",
      "Volunteer Management"
    ]
  },

  church: {
    name: "Religious Organization",
    promptCategories: [
      "Ministry Planning",
      "Facility Management",
      "Event Coordination",
      "Community Engagement",
      "Spiritual Programs"
    ],
    customFields: [
      { name: "ministry_type", label: "Ministry Type", type: "select" },
      { name: "congregation_size", label: "Congregation Size", type: "select" },
      { name: "age_groups", label: "Target Age Groups", type: "multiselect" },
      { name: "facility_needs", label: "Facility Requirements", type: "multiselect" }
    ],
    reportSections: [
      "Ministry Vision",
      "Spiritual Growth Plan",
      "Community Impact",
      "Resource Allocation",
      "Leadership Development"
    ]
  }
};
```

#### **3.2 Industry-Specific Prompt Catalogs**

```python
# planexe/industry/software_prompts.py
SOFTWARE_PROMPTS = [
    {
        "uuid": "sw-001",
        "title": "SaaS Platform Architecture",
        "category": "Architecture & System Design",
        "prompt": """
        Design a comprehensive plan for building a multi-tenant SaaS platform with the following requirements:
        - Technology stack: {tech_stack}
        - Expected users: {user_scale}
        - Key features: {features}
        - Security requirements: {security_level}
        - Performance targets: {performance_targets}

        Please include system architecture, database design, API structure, deployment strategy, and scaling considerations.
        """
    },
    {
        "uuid": "sw-002",
        "title": "API Development Roadmap",
        "category": "API Development",
        "prompt": """
        Create a detailed plan for developing a REST API with these specifications:
        - API purpose: {api_purpose}
        - Key endpoints: {endpoints}
        - Authentication method: {auth_method}
        - Expected load: {expected_load}
        - Integration requirements: {integrations}

        Include API design, documentation strategy, testing approach, and deployment pipeline.
        """
    }
    # ... more software-specific prompts
]

# planexe/industry/nonprofit_prompts.py
NONPROFIT_PROMPTS = [
    {
        "uuid": "np-001",
        "title": "Community Program Launch",
        "category": "Program Development",
        "prompt": """
        Develop a comprehensive plan for launching a new community program:
        - Program focus: {program_focus}
        - Target population: {target_population}
        - Available budget: {budget}
        - Timeline: {timeline}
        - Success metrics: {success_metrics}

        Include program design, volunteer recruitment, funding strategy, marketing approach, and impact measurement.
        """
    }
    # ... more nonprofit-specific prompts
]
```

#### **3.3 Dynamic Form Generation**

```typescript
// components/industry/DynamicPlanForm.tsx
interface DynamicPlanFormProps {
  industryType: IndustryType;
  tenantKey: string;
  onSubmit: (data: PlanFormData) => void;
}

export const DynamicPlanForm = ({ industryType, tenantKey, onSubmit }: DynamicPlanFormProps) => {
  const config = INDUSTRY_CONFIGURATIONS[industryType];
  const prompts = useTenantPrompts(tenantKey, industryType);

  const form = useForm<PlanFormData>({
    resolver: zodResolver(createIndustrySchema(industryType))
  });

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">

        {/* Base prompt selection */}
        <FormField
          control={form.control}
          name="basePrompt"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Select {config.name} Template</FormLabel>
              <Select onValueChange={field.onChange} defaultValue={field.value}>
                <FormControl>
                  <SelectTrigger>
                    <SelectValue placeholder="Choose a template..." />
                  </SelectTrigger>
                </FormControl>
                <SelectContent>
                  {prompts.map((prompt) => (
                    <SelectItem key={prompt.uuid} value={prompt.uuid}>
                      {prompt.title}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </FormItem>
          )}
        />

        {/* Dynamic industry-specific fields */}
        {config.customFields.map((field) => (
          <DynamicField
            key={field.name}
            field={field}
            control={form.control}
          />
        ))}

        {/* Custom prompt input */}
        <FormField
          control={form.control}
          name="customPrompt"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Additional Details</FormLabel>
              <FormControl>
                <Textarea
                  placeholder="Add any specific requirements or context..."
                  {...field}
                />
              </FormControl>
            </FormItem>
          )}
        />

        <Button type="submit" className="tenant-branded">
          Create {config.name} Plan
        </Button>
      </form>
    </Form>
  );
};
```

### **Phase 4: Integration & Polish (Week 4-5)**

#### **4.1 API Client Layer**

```typescript
// lib/api/client.ts
class PlanExeAPIClient {
  private baseURL: string;

  constructor(baseURL: string) {
    this.baseURL = baseURL;
  }

  // Tenant management
  async getTenant(tenantKey: string): Promise<TenantConfig> {
    const response = await fetch(`${this.baseURL}/api/tenants/${tenantKey}`);
    return response.json();
  }

  // Tenant-specific plan operations
  async createTenantPlan(tenantKey: string, request: CreatePlanRequest): Promise<Plan> {
    const response = await fetch(`${this.baseURL}/api/${tenantKey}/plans`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request)
    });
    return response.json();
  }

  async getTenantPlans(tenantKey: string): Promise<Plan[]> {
    const response = await fetch(`${this.baseURL}/api/${tenantKey}/plans`);
    return response.json();
  }

  // Real-time progress monitoring
  watchPlanProgress(planId: string): EventSource {
    return new EventSource(`${this.baseURL}/api/plans/${planId}/stream`);
  }

  // File operations
  async downloadPlanReport(planId: string): Promise<Blob> {
    const response = await fetch(`${this.baseURL}/api/plans/${planId}/report`);
    return response.blob();
  }
}

export const apiClient = new PlanExeAPIClient(process.env.NEXT_PUBLIC_API_URL ?? "");
```

#### **4.2 Real-time Progress Component**

```typescript
// components/planning/PlanProgressMonitor.tsx
interface PlanProgressMonitorProps {
  planId: string;
  onComplete?: (plan: Plan) => void;
}

export const PlanProgressMonitor = ({ planId, onComplete }: PlanProgressMonitorProps) => {
  const [progress, setProgress] = useState<PlanProgress | null>(null);
  const [eventSource, setEventSource] = useState<EventSource | null>(null);

  useEffect(() => {
    // Set up Server-Sent Events for real-time progress
    const es = apiClient.watchPlanProgress(planId);

    es.onmessage = (event) => {
      const data = JSON.parse(event.data) as PlanProgressEvent;
      setProgress(data);

      if (data.status === 'completed' && onComplete) {
        onComplete(data);
        es.close();
      }
    };

    es.onerror = () => {
      console.error('EventSource failed');
      es.close();
    };

    setEventSource(es);

    return () => {
      es.close();
    };
  }, [planId]);

  if (!progress) return <div>Loading...</div>;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Plan Generation Progress</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          <Progress value={progress.progress_percentage} />
          <p className="text-sm text-muted-foreground">
            {progress.progress_message}
          </p>
          <div className="flex items-center space-x-2">
            <Badge variant={getStatusVariant(progress.status)}>
              {progress.status}
            </Badge>
            <span className="text-xs text-muted-foreground">
              {formatDistanceToNow(new Date(progress.timestamp))} ago
            </span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};
```

---

## 🚀 **MVP Deployment Strategy**

### **Development Environment Setup**

```bash
# Backend (existing Python API)
cd planexe_api/
pip install -r requirements.txt
uvicorn api:app --reload --port 8000

# Frontend (new Next.js app)
cd planexe-frontend/
npm install
npm run dev
```

### **Production Deployment**

#### **Railway (Backend)**
```yaml
# railway.toml
[build]
  builder = "nixpacks"
  buildCommand = "pip install -r planexe_api/requirements.txt"

[deploy]
  startCommand = "uvicorn planexe_api.api:app --host 0.0.0.0 --port $PORT"

[env]
  DATABASE_URL = { from = "DATABASE_URL" }
  OPENROUTER_API_KEY = { from = "OPENROUTER_API_KEY" }
```

#### **Vercel (Frontend)**
```json
{
  "framework": "nextjs",
  "buildCommand": "npm run build",
  "devCommand": "npm run dev",
  "installCommand": "npm install",
  "env": {
    "NEXT_PUBLIC_API_URL": "https://your-railway-app.railway.app"  // optional override; defaults to same origin
  }
}
```

---

## 📊 **MVP Success Metrics**

### **Technical Metrics**
- [ ] Multi-tenant database schema deployed
- [ ] 3+ tenant configurations working simultaneously
- [ ] Dynamic theming system functional
- [ ] Industry-specific prompts loading correctly
- [ ] Real-time plan progress monitoring working
- [ ] File download/report generation working

### **Business Validation Metrics**
- [ ] Software development tenant can create technical plans
- [ ] Non-profit tenant gets appropriate program planning prompts
- [ ] Church tenant sees ministry-focused interface
- [ ] Each tenant has distinct branding (logo, colors, terminology)
- [ ] Plan quality remains high across all tenant types

### **UX Metrics**
- [ ] Page load times < 3 seconds
- [ ] Plan creation flow intuitive for non-technical users
- [ ] Progress monitoring provides clear feedback
- [ ] Mobile responsive on all tenant interfaces
- [ ] No breaking changes to existing PlanExe functionality

---

## 🎯 **MVP Demo Scenarios**

### **Scenario 1: TechCorp (Software Development Tenant)**
1. Navigate to `/techcorp`
2. See TechCorp branding (blue theme, tech logo)
3. View software development prompt templates
4. Create "SaaS Platform Architecture" plan
5. Monitor real-time progress with technical terminology
6. Download comprehensive technical documentation

### **Scenario 2: HopeNonProfit (Non-Profit Tenant)**
1. Navigate to `/hopenonprofit`
2. See HopeNonProfit branding (green theme, heart logo)
3. View program development templates
4. Create "Community Outreach Program" plan
5. Monitor progress with impact-focused language
6. Download program implementation guide

### **Scenario 3: FaithChurch (Religious Organization Tenant)**
1. Navigate to `/faithchurch`
2. See FaithChurch branding (gold theme, cross logo)
3. View ministry planning templates
4. Create "Youth Ministry Launch" plan
5. Monitor progress with spiritual growth terminology
6. Download ministry development roadmap

---

## 🔄 **Implementation Timeline**

### **Week 1: Backend Foundation**
- [ ] Add tenant tables to database schema
- [ ] Implement tenant-aware API endpoints
- [ ] Test multi-tenant plan creation
- [ ] Set up tenant-scoped file storage

### **Week 2: Next.js Setup**
- [ ] Initialize Next.js 14 project with TypeScript
- [ ] Implement tenant routing (`/[tenantKey]`)
- [ ] Create basic tenant-aware layout
- [ ] Set up Tailwind CSS with dynamic theming

### **Week 3: Core UI Components**
- [ ] Build plan creation workflow
- [ ] Implement real-time progress monitoring
- [ ] Create plan listing and details pages
- [ ] Add file download functionality

### **Week 4: Industry Specialization**
- [ ] Add industry-specific prompt catalogs
- [ ] Implement dynamic form generation
- [ ] Create industry-specific reporting templates
- [ ] Test all three demo scenarios

### **Week 5: Integration & Polish**
- [ ] End-to-end testing across all tenants
- [ ] Performance optimization
- [ ] Error handling and user feedback
- [ ] Deploy to staging environment

### **Week 6: Deployment & Documentation**
- [ ] Production deployment to Railway + Vercel
- [ ] Create admin tools for tenant management
- [ ] Document API changes and new features
- [ ] Prepare demo for stakeholders

---

## 🎨 **Design System Foundation**

### **Tenant-Aware Component Library**

```typescript
// components/ui/Button.tsx (enhanced for tenant theming)
interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'default' | 'tenant' | 'outline' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
}

export const Button = ({ variant = 'default', size = 'md', className, ...props }: ButtonProps) => {
  return (
    <button
      className={cn(
        'inline-flex items-center justify-center rounded-md font-medium transition-colors',
        {
          'bg-tenant-primary text-white hover:bg-tenant-primary/90': variant === 'tenant',
          'bg-primary text-primary-foreground hover:bg-primary/90': variant === 'default',
          'border border-tenant-primary text-tenant-primary hover:bg-tenant-primary hover:text-white': variant === 'outline',
          // ... size variants
        },
        className
      )}
      {...props}
    />
  );
};
```

### **Typography System**

```css
/* styles/tenant-typography.css */
.tenant-heading {
  font-family: var(--font-heading, 'Inter');
  color: var(--primary);
  font-weight: 600;
}

.tenant-body {
  font-family: var(--font-body, 'Inter');
  color: var(--foreground);
}

.tenant-accent {
  color: var(--accent);
}
```

---

## 🔒 **Security Considerations**

### **Multi-Tenant Data Isolation**
- Row-level security in PostgreSQL for tenant data separation
- API route validation to ensure users can only access their tenant's data
- File storage scoped to tenant directories with access controls

### **API Security**
- Rate limiting per tenant to prevent abuse
- API key validation for external integrations
- Tenant-scoped authentication and authorization

### **Frontend Security**
- Environment variable validation for API endpoints
- Client-side tenant validation before API calls
- Secure storage of sensitive configuration data

---

## 🚀 **Next Steps After MVP**

### **Enhanced Features for v2**
1. **Advanced Analytics Dashboard** - Tenant-specific metrics and insights
2. **API Access for Tenants** - Allow tenants to integrate via REST API
3. **Custom Domain Support** - Tenant-specific domains (client.planexe.com)
4. **Advanced Role Management** - Multiple users per tenant with permissions
5. **Template Marketplace** - Tenant-specific template sharing
6. **Subscription Management** - Billing and feature gating per tenant

### **Scale Optimizations**
1. **Caching Layer** - Redis for tenant configurations and frequent data
2. **CDN Integration** - Static asset optimization per tenant
3. **Database Optimization** - Tenant partitioning for large-scale deployments
4. **Microservices Architecture** - Split components for independent scaling

---

## 📝 **Conclusion**

This MVP plan leverages PlanExe's existing robust architecture while adding the essential multi-tenant and white-label capabilities needed to demonstrate the SaaS platform vision. By building incrementally on the strong foundation of the Luigi pipeline system, FastAPI REST layer, and comprehensive database schema, we can create a compelling proof-of-concept that showcases:

1. **Technical feasibility** of the multi-tenant architecture
2. **Business value** of industry-specific customization
3. **User experience** improvements with modern Next.js frontend
4. **Scalability potential** for the full enterprise platform

The 6-week timeline is achievable because we're enhancing rather than replacing the core PlanExe functionality, allowing us to focus on the differentiated multi-tenant and white-label features that make this a compelling SaaS offering.

**Key Success Factor**: This MVP maintains 100% backward compatibility with existing PlanExe functionality while adding the new multi-tenant capabilities, ensuring we don't disrupt current users while demonstrating the platform's potential.