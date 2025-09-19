# PlanExe Platform Architecture Plan
**Next.js Multi-Tenant White-Label Planning Platform**

*Date: September 19, 2025*
*Author: Claude Code & Development Team*

---

## 🎯 **Vision & Objectives**

### Core Mission
Transform Simon's robust Python planning engine into a scalable, white-label SaaS platform that enables non-technical users to leverage sophisticated AI planning across diverse industries and use cases.

### Target Markets
- **Software Development**: Sprint planning, architecture design, deployment strategies
- **Non-Profit Organizations**: Program planning, fundraising campaigns, volunteer coordination
- **Religious Organizations**: Ministry planning, event coordination, facility management
- **Business Consulting**: Strategic planning, operational optimization, project management
- **Educational Institutions**: Curriculum planning, facility management, program development

---

## 🏗️ **Architecture Overview**

### Technology Stack
```
Frontend:  Next.js 14 + TypeScript + Tailwind CSS + Zustand
Backend:   Python FastAPI (existing PlanExe engine) + PostgreSQL
Deployment: Railway (API) + Vercel (Frontend)
Storage:    PostgreSQL + S3/Railway Storage
Auth:      NextAuth.js + JWT
```

### System Architecture
```
┌─────────────────────────────────────────────────────────────┐
│                    Multi-Tenant Frontend                    │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐│
│  │   Tenant A      │ │   Tenant B      │ │   Tenant C      ││
│  │ (Software Dev)  │ │ (Non-Profit)    │ │ (Church Org)    ││
│  │                 │ │                 │ │                 ││
│  │ Custom Branding │ │ Custom Branding │ │ Custom Branding ││
│  │ Tailored UI     │ │ Tailored UI     │ │ Tailored UI     ││
│  └─────────────────┘ └─────────────────┘ └─────────────────┘│
└─────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────┐
│                 Unified API Gateway                         │
│              (Next.js API Routes)                          │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ Multi-tenant routing │ Auth │ Rate limiting │ Analytics ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────┐
│              Core Planning Engine (Python)                 │
│  ┌─────────────────────────────────────────────────────────┐│
│  │          Simon's PlanExe Business Logic                 ││
│  │   (AI Planning │ LLM Integration │ Report Generation)   ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

---

## 🏢 **Multi-Tenancy Strategy**

### White-Label Solution Design

#### **1. Tenant Configuration System**
```typescript
interface TenantConfig {
  id: string;
  domain: string;           // custom.planexe.app or custom.com
  branding: {
    logo: string;
    primaryColor: string;
    secondaryColor: string;
    fontFamily: string;
    customCSS?: string;
  };
  features: {
    planTypes: PlanType[];   // software, nonprofit, church, etc.
    maxPlans: number;
    advancedFeatures: boolean;
    apiAccess: boolean;
  };
  prompts: {
    customPrompts: Prompt[];
    templateLibrary: TemplateCategory[];
  };
}
```

#### **2. Dynamic UI Rendering**
- **Component Library**: Shared base components with theme injection
- **Layout System**: Tenant-specific layouts and navigation
- **Content Management**: Dynamic forms, fields, and workflows per tenant
- **Brand Consistency**: Logo, colors, typography automatically applied

#### **3. Plan Type Specialization**
```typescript
// Software Development Planning
interface SoftwarePlanConfig {
  frameworks: Framework[];
  deploymentTargets: DeploymentTarget[];
  teamRoles: DeveloperRole[];
  methodologies: Methodology[]; // Agile, Waterfall, etc.
}

// Non-Profit Planning
interface NonProfitPlanConfig {
  programTypes: ProgramType[];
  fundingSources: FundingSource[];
  impactMetrics: ImpactMetric[];
  complianceRequirements: ComplianceRule[];
}

// Church/Religious Planning
interface ReligiousPlanConfig {
  ministryTypes: MinistryType[];
  facilityNeeds: FacilityRequirement[];
  eventTypes: EventCategory[];
  communityPrograms: ProgramType[];
}
```

---

## 🎨 **Frontend Architecture**

### Next.js 14 App Router Structure
```
src/
├── app/
│   ├── (tenants)/
│   │   ├── [tenant]/
│   │   │   ├── dashboard/
│   │   │   ├── plans/
│   │   │   │   ├── create/
│   │   │   │   ├── [planId]/
│   │   │   │   └── templates/
│   │   │   ├── settings/
│   │   │   └── analytics/
│   │   └── layout.tsx
│   ├── admin/                # Platform administration
│   ├── api/
│   │   ├── auth/
│   │   ├── tenants/
│   │   ├── plans/
│   │   └── proxy/           # Proxy to Python API
│   └── (marketing)/         # Landing pages
├── components/
│   ├── ui/                  # Base Tailwind components
│   ├── tenant/              # Tenant-specific components
│   ├── planning/            # Planning workflow components
│   └── shared/              # Cross-tenant components
├── lib/
│   ├── auth/
│   ├── database/
│   ├── planning-engine/     # Python API client
│   ├── tenant-config/
│   └── utils/
├── stores/                  # Zustand stores
│   ├── tenant.ts
│   ├── planning.ts
│   ├── auth.ts
│   └── ui.ts
└── styles/
    ├── globals.css
    └── tenant-themes/
```

### State Management with Zustand
```typescript
// Tenant Store
interface TenantStore {
  currentTenant: TenantConfig | null;
  theme: ThemeConfig;
  features: FeatureFlags;

  actions: {
    loadTenant: (domain: string) => Promise<void>;
    updateTheme: (theme: Partial<ThemeConfig>) => void;
    checkFeature: (feature: string) => boolean;
  };
}

// Planning Store
interface PlanningStore {
  currentPlan: Plan | null;
  plans: Plan[];
  templates: Template[];
  progress: ProgressState;

  actions: {
    createPlan: (config: PlanConfig) => Promise<Plan>;
    watchProgress: (planId: string) => void;
    loadTemplates: () => Promise<void>;
  };
}
```

### Component Architecture
```typescript
// Base Planning Component
export const PlanningWorkflow = ({
  tenantConfig,
  planType,
  customFields
}: PlanningWorkflowProps) => {
  const workflow = usePlanningWorkflow(planType);
  const theme = useTenantTheme();

  return (
    <div className={cn("planning-workflow", theme.containerClasses)}>
      <PlanningHeader config={tenantConfig} />
      <DynamicForm fields={customFields} />
      <ProgressIndicator workflow={workflow} />
      <ResultsDisplay planType={planType} />
    </div>
  );
};
```

---

## 🔧 **Backend Integration**

### Python API Proxy Layer
```typescript
// Next.js API Route: /api/plans/create
export async function POST(request: Request) {
  const session = await getServerSession(authOptions);
  const tenant = await getTenantFromSession(session);

  // Transform tenant-specific request to Python API format
  const planRequest = await transformTenantRequest(
    await request.json(),
    tenant.config
  );

  // Proxy to Python FastAPI
  const pythonResponse = await fetch(`${PYTHON_API_URL}/api/plans`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Tenant-ID': tenant.id,
    },
    body: JSON.stringify(planRequest)
  });

  // Transform response back to tenant format
  const result = await transformTenantResponse(
    await pythonResponse.json(),
    tenant.config
  );

  return Response.json(result);
}
```

### Database Schema Extensions
```sql
-- Tenant Management
CREATE TABLE tenants (
  id UUID PRIMARY KEY,
  domain VARCHAR(255) UNIQUE,
  name VARCHAR(255),
  config JSONB,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Plan Type Configurations
CREATE TABLE plan_types (
  id UUID PRIMARY KEY,
  tenant_id UUID REFERENCES tenants(id),
  name VARCHAR(255),
  config JSONB,
  templates JSONB[],
  prompts JSONB[]
);

-- Enhanced Plans Table
ALTER TABLE plans ADD COLUMN tenant_id UUID REFERENCES tenants(id);
ALTER TABLE plans ADD COLUMN plan_type VARCHAR(100);
ALTER TABLE plans ADD COLUMN custom_config JSONB;
```

---

## 🚀 **Deployment Strategy**

### Railway + Vercel Architecture
```
┌─────────────────────────────────────────────────────────────┐
│                    Vercel (Frontend)                       │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ Next.js App (Multi-tenant with custom domains)         ││
│  │ - custom1.planexe.app                                  ││
│  │ - custom2.planexe.app                                  ││
│  │ - clientdomain.com (custom domain)                     ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
                                │
                                ▼ (API Calls)
┌─────────────────────────────────────────────────────────────┐
│                  Railway (Backend)                         │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ Python FastAPI + PostgreSQL                            ││
│  │ - Core planning engine                                  ││
│  │ - Multi-tenant data isolation                          ││
│  │ - LLM integrations                                      ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

### Environment Configuration
```bash
# Next.js (.env.local)
NEXTAUTH_SECRET=your-secret
NEXTAUTH_URL=https://planexe.app
DATABASE_URL=postgresql://...
PYTHON_API_URL=https://your-railway-app.railway.app
UPLOADTHING_SECRET=...
STRIPE_SECRET_KEY=...

# Python API (Railway)
DATABASE_URL=postgresql://...
OPENROUTER_API_KEY=...
REDIS_URL=...
JWT_SECRET=...
```

---

## 💼 **Business Model Integration**

### Subscription Tiers
```typescript
interface SubscriptionTier {
  name: string;
  price: number;
  features: {
    maxPlans: number;
    planTypes: string[];
    customBranding: boolean;
    customDomain: boolean;
    apiAccess: boolean;
    advancedAnalytics: boolean;
    prioritySupport: boolean;
  };
}

const SUBSCRIPTION_TIERS = {
  starter: {
    name: "Starter",
    price: 29,
    features: {
      maxPlans: 10,
      planTypes: ["basic"],
      customBranding: false,
      customDomain: false,
      apiAccess: false,
      advancedAnalytics: false,
      prioritySupport: false,
    }
  },
  professional: {
    name: "Professional",
    price: 99,
    features: {
      maxPlans: 100,
      planTypes: ["software", "nonprofit", "church"],
      customBranding: true,
      customDomain: true,
      apiAccess: true,
      advancedAnalytics: true,
      prioritySupport: true,
    }
  }
};
```

### Revenue Streams
1. **SaaS Subscriptions**: Monthly/annual plans
2. **White-Label Licensing**: Custom enterprise deployments
3. **API Usage**: Pay-per-plan for high-volume users
4. **Professional Services**: Custom implementation and training
5. **Template Marketplace**: Premium planning templates

---

## 🎯 **Industry-Specific Implementations**

### Software Development Planning
```typescript
interface SoftwarePlanningConfig {
  components: {
    TechStackSelector: ComponentType;
    ArchitectureDiagram: ComponentType;
    SprintPlanner: ComponentType;
    DeploymentPipeline: ComponentType;
  };

  prompts: {
    systemDesign: string;
    apiDesign: string;
    testingStrategy: string;
    deploymentPlan: string;
  };

  templates: [
    "Microservices Architecture",
    "Mobile App Development",
    "SaaS Platform Launch",
    "API Integration Project"
  ];
}
```

### Non-Profit Organization Planning
```typescript
interface NonProfitPlanningConfig {
  components: {
    ImpactMeasurement: ComponentType;
    FundraisingStrategy: ComponentType;
    VolunteerManagement: ComponentType;
    ComplianceChecker: ComponentType;
  };

  prompts: {
    programDevelopment: string;
    grantApplication: string;
    eventPlanning: string;
    donorEngagement: string;
  };

  templates: [
    "Community Outreach Program",
    "Fundraising Campaign",
    "Volunteer Training Program",
    "Grant Application Strategy"
  ];
}
```

### Religious Organization Planning
```typescript
interface ReligiousPlanningConfig {
  components: {
    MinistryPlanner: ComponentType;
    EventCoordinator: ComponentType;
    FacilityManager: ComponentType;
    CommunityOutreach: ComponentType;
  };

  prompts: {
    ministryDevelopment: string;
    congregationGrowth: string;
    facilityExpansion: string;
    communityEngagement: string;
  };

  templates: [
    "Church Plant Strategy",
    "Youth Ministry Program",
    "Building Renovation Project",
    "Community Service Initiative"
  ];
}
```

---

## 🔄 **Development Phases**

### Phase 1: Foundation (Weeks 1-4)
- [ ] Next.js 14 project setup with TypeScript
- [ ] Tailwind CSS configuration with theme system
- [ ] NextAuth.js authentication integration
- [ ] Basic tenant management system
- [ ] Python API proxy layer
- [ ] Railway deployment setup

### Phase 2: Core Features (Weeks 5-8)
- [ ] Dynamic tenant theming system
- [ ] Plan creation workflow engine
- [ ] Real-time progress monitoring
- [ ] File management and downloads
- [ ] Basic analytics dashboard
- [ ] Subscription management integration

### Phase 3: Specialization (Weeks 9-12)
- [ ] Software development planning module
- [ ] Non-profit planning module
- [ ] Religious organization planning module
- [ ] Template marketplace
- [ ] Advanced customization options
- [ ] White-label deployment tools

### Phase 4: Scale & Polish (Weeks 13-16)
- [ ] Performance optimization
- [ ] Advanced analytics and reporting
- [ ] Mobile responsiveness perfection
- [ ] Enterprise security features
- [ ] API documentation and SDKs
- [ ] Customer onboarding automation

---

## 🎨 **UI/UX Design Principles**

### Design System Philosophy
- **Adaptive Branding**: Seamless integration of client branding
- **Progressive Disclosure**: Complex features revealed as needed
- **Contextual Guidance**: Industry-specific help and examples
- **Data Visualization**: Rich charts and diagrams for plan results
- **Mobile-First**: Full functionality on all devices

### Component Design Patterns
```typescript
// Adaptive Theme System
const useAdaptiveTheme = (tenantConfig: TenantConfig) => {
  return {
    colors: {
      primary: tenantConfig.branding.primaryColor,
      secondary: tenantConfig.branding.secondaryColor,
      accent: generateAccentColor(tenantConfig.branding.primaryColor),
    },
    fonts: {
      heading: tenantConfig.branding.fontFamily,
      body: getOptimalBodyFont(tenantConfig.branding.fontFamily),
    },
    components: generateTailwindClasses(tenantConfig.branding),
  };
};
```

### User Experience Flow
1. **Onboarding**: Industry selection → Template gallery → First plan
2. **Plan Creation**: Guided wizard → Real-time preview → AI assistance
3. **Progress Monitoring**: Live updates → Visual timeline → Milestone alerts
4. **Results**: Interactive reports → Export options → Sharing tools
5. **Iteration**: Plan comparison → Versioning → Collaborative editing

---

## 🔒 **Security & Compliance**

### Multi-Tenant Security
- **Data Isolation**: Row-level security in PostgreSQL
- **Access Control**: Role-based permissions per tenant
- **API Security**: Rate limiting and tenant validation
- **Audit Logging**: Comprehensive activity tracking

### Industry Compliance
- **GDPR**: Data privacy and right to deletion
- **SOC 2**: Security controls for enterprise clients
- **HIPAA**: Healthcare planning compliance (future)
- **Financial**: PCI compliance for payment processing

---

## 📊 **Analytics & Insights**

### Platform Analytics
- Tenant usage patterns and feature adoption
- Plan success rates and completion times
- LLM cost analysis and optimization
- User satisfaction and churn prediction

### Tenant-Specific Analytics
- Plan performance metrics
- Team collaboration insights
- ROI measurement tools
- Custom reporting dashboards

---

## 🎯 **Success Metrics**

### Business Metrics
- **Monthly Recurring Revenue (MRR)**: Target $50k by month 12
- **Customer Acquisition Cost (CAC)**: <3x monthly subscription value
- **Churn Rate**: <5% monthly for paid plans
- **Net Promoter Score (NPS)**: >70

### Technical Metrics
- **API Response Time**: <200ms average
- **Uptime**: 99.9% availability
- **Plan Success Rate**: >95% completion rate
- **User Satisfaction**: >4.5/5 star rating

---

## 🚀 **Next Steps**

### Immediate Actions
1. **Repository Setup**: Initialize Next.js 14 project with TypeScript
2. **Design System**: Create Tailwind config with multi-tenant theming
3. **Authentication**: Implement NextAuth.js with tenant-aware sessions
4. **Database Design**: Extend PostgreSQL schema for multi-tenancy
5. **Python Integration**: Create API proxy layer in Next.js

### Week 1 Deliverables
- [ ] Next.js project structure with tenant routing
- [ ] Basic tenant configuration system
- [ ] Python API integration test
- [ ] Railway deployment pipeline
- [ ] Initial Tailwind design system

This platform will transform Simon's powerful Python planning engine into a scalable, industry-specific SaaS solution that can serve diverse markets while maintaining the core AI planning capabilities. The white-label approach ensures each tenant gets a tailored experience while leveraging shared infrastructure for efficiency and cost-effectiveness.

---

## 🗂️ **Project Structure Overview**

### Current State (What We Built Today)
```
PlanExe/
├── planexe_api/                 # ✅ FastAPI REST API (KEEP)
│   ├── api.py                  # Main API server
│   ├── models.py               # Pydantic schemas
│   ├── database.py             # PostgreSQL models
│   ├── requirements.txt        # Dependencies
│   └── migrations/             # Database migrations
├── docker/                     # ✅ Container config (KEEP)
│   ├── Dockerfile.api
│   ├── docker-compose.yml
│   └── init-db.sql
├── docs/                       # ✅ Documentation (KEEP)
│   ├── API.md
│   ├── 19092025-NextJS-Platform-Plan.md
│   └── README_API.md
├── nodejs-client/              # ❌ DELETED (overcomplicated)
├── nodejs-ui/                  # ❌ DELETED (build complexity)
└── simple-ui/                  # ❌ TO DELETE (CDN approach)
```

### Target Structure (Next Steps)
```
PlanExe/
├── planexe_api/                 # ✅ Python backend (existing)
├── web/                         # 🆕 Next.js 14 platform
│   ├── src/app/
│   │   ├── (tenants)/[tenant]/
│   │   ├── admin/
│   │   └── api/
│   ├── components/
│   ├── lib/
│   ├── stores/
│   └── package.json
├── docker/                      # ✅ Updated for Next.js
└── docs/                        # ✅ Platform documentation
```

## 🎯 **Implementation Priority**

### Phase 1: Foundation
1. **Initialize Next.js 14 project** in `/web` folder
2. **Set up Tailwind CSS** with multi-tenant theming
3. **Integrate Zustand** for state management
4. **Connect to existing Python API** via proxy
5. **Deploy on Railway + Vercel**

### Phase 2: Multi-Tenancy
1. **Tenant configuration system**
2. **Dynamic branding and theming**
3. **Industry-specific plan types**
4. **White-label domain routing**

### Phase 3: Scale
1. **Advanced analytics**
2. **Template marketplace**
3. **Enterprise features**
4. **Mobile optimization**

---

## 📝 **Development Notes**

### What We Accomplished Today
- ✅ **REST API**: Complete FastAPI wrapper around Simon's Python engine
- ✅ **Database**: PostgreSQL with plan persistence and LLM interaction logging
- ✅ **Docker**: Production-ready containerization
- ✅ **Architecture**: Solid foundation for the Next.js platform

### What We're Building Next
- 🚀 **Next.js 14 Platform**: Modern, scalable frontend with TypeScript
- 🎨 **Multi-Tenant UI**: Industry-specific interfaces with custom branding
- 💼 **SaaS Features**: Subscriptions, analytics, white-label deployments
- 🌐 **Railway Deployment**: Scalable infrastructure for growth

### Key Decisions Made
1. **Framework**: Next.js 14 with App Router for maximum flexibility
2. **Styling**: Tailwind CSS for rapid, maintainable development
3. **State**: Zustand for simple, performant state management
4. **Deployment**: Railway (backend) + Vercel (frontend) for optimal performance
5. **Architecture**: Multi-tenant white-label SaaS platform

---

*The foundation is solid. Now we build the platform that will democratize AI planning across industries! 🚀*