/**
 * Author: Claude Code using Sonnet 4
 * Date: 2025-09-26
 * PURPOSE: Complete specifications for Phase 2 UI components using shadcn/ui
 * SRP and DRY check: Pass - Single responsibility for UI component documentation
 */

# Phase 2: Enhanced UI Components Specifications

## 📋 **Phase 1 Analysis Summary**

### **SSE Reliability Issues Confirmed**
- **10 Critical Thread Safety Issues** identified in pipeline execution service
- **Global dictionary race conditions** causing KeyError crashes
- **Queue cleanup races** between SSE clients and pipeline completion
- **Resource leaks** from timeout handling and zombie threads
- **Poor error handling** masking real failures

### **Evidence from Real Pipeline Runs**
- Pipeline run `PlanExe_4c535962-dabd-4728-b2f4-37b506bf0bd8` shows actual Luigi execution
- Real user prompt: "snow plow business in eastern CT. already own a truck. just need a plow right? how much are those?"
- Generated files: 109 expected outputs from start_time.json to final report
- Luigi task dependency chain validated: 61 interconnected tasks working correctly

## 🎯 **Phase 2 Objectives**

Transform the current basic UI into a professional-grade interface using the existing shadcn/ui components while maintaining compatibility with the robust Luigi pipeline.

## 🧩 **Available shadcn/ui Components**

**Located in**: `planexe-frontend/src/components/ui/`

### **Core Components Available**:
- `button.tsx` - Multiple variants (default, destructive, outline, secondary, ghost, link)
- `card.tsx` - Card, CardHeader, CardContent, CardDescription, CardTitle
- `input.tsx` - Form inputs with validation states
- `textarea.tsx` - Multi-line text inputs
- `select.tsx` - Dropdown selectors
- `progress.tsx` - Progress bars and indicators
- `tabs.tsx` - Tab navigation
- `dialog.tsx` - Modal dialogs
- `table.tsx` - Data tables
- `form.tsx` - Form components with validation
- `accordion.tsx` - Collapsible content
- `badge.tsx` - Status indicators and labels
- `label.tsx` - Form labels

## 🏗️ **Component Architecture Plan**

### **Component 1: Interactive Luigi Task Dependency Graph**

**File**: `planexe-frontend/src/components/monitoring/TaskDependencyGraph.tsx`

**Purpose**: Visual representation of the 61-task Luigi pipeline with real-time status

**Design Specifications**:
```typescript
interface TaskNode {
  id: string;
  name: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  dependencies: string[];
  outputs: string[];
  startTime?: string;
  endTime?: string;
  duration?: number;
}

interface TaskDependencyGraphProps {
  planId: string;
  tasks: TaskNode[];
  onTaskClick?: (taskId: string) => void;
  className?: string;
}
```

**UI Elements**:
- **Container**: `Card` with fixed height and scrollable content
- **Task Nodes**: `Badge` components with status-based color coding
- **Connections**: SVG lines showing dependencies
- **Legend**: `Badge` components showing status meanings
- **Controls**: `Button` components for zoom, pan, reset view
- **Details Panel**: `Accordion` for expanded task information

**Status Color Scheme**:
- Pending: `badge-secondary` (gray)
- Running: `badge-default` with pulse animation (blue)
- Completed: `badge` with green variant (custom CSS)
- Failed: `badge-destructive` (red)

**Layout Strategy**:
```typescript
// Hierarchical layout based on Luigi dependency chain
const TASK_LAYERS = {
  setup: ['StartTimeTask', 'SetupTask'],
  analysis: ['RedlineGateTask', 'PremiseAttackTask', 'IdentifyPurposeTask'],
  strategic: ['PotentialLeversTask', 'DeduplicateLeversTask', 'EnrichLeversTask'],
  // ... continues for all 61 tasks
};
```

### **Component 2: Enhanced Terminal with Real-time Luigi Logs**

**File**: `planexe-frontend/src/components/monitoring/EnhancedTerminal.tsx`

**Purpose**: Professional terminal interface with advanced log management

**Enhanced Features**:
- **Log Filtering**: `Select` dropdown for log levels (INFO, DEBUG, ERROR, WARN)
- **Search**: `Input` with search icon for log content filtering
- **Export**: `Button` group for downloading logs (TXT, JSON, CSV)
- **Performance Metrics**: `Progress` bars showing CPU/memory usage
- **Bookmarks**: `Button` to bookmark important log entries

**UI Layout**:
```typescript
interface EnhancedTerminalProps {
  planId: string;
  onComplete?: () => void;
  onError?: (error: string) => void;
  showMetrics?: boolean;
  className?: string;
}
```

**Design Structure**:
```tsx
<Card>
  <CardHeader>
    <div className="flex justify-between">
      <CardTitle>Luigi Pipeline Logs</CardTitle>
      <div className="flex gap-2">
        <Select> {/* Log level filter */}
        <Button variant="outline"> {/* Export */}
        <Button variant="outline"> {/* Clear */}
      </div>
    </div>
    <div className="flex gap-2 mt-2">
      <Input placeholder="Search logs..." />
      <Progress value={cpuUsage} className="w-24" />
      <Badge>{logCount} lines</Badge>
    </div>
  </CardHeader>
  <CardContent>
    <div className="terminal-content">
      {/* Scrollable log content */}
    </div>
  </CardContent>
</Card>
```

### **Component 3: File Explorer with Preview**

**File**: `planexe-frontend/src/components/files/FileExplorer.tsx`

**Purpose**: Rich file browser for the 109 generated pipeline outputs

**Features**:
- **Tree View**: `Accordion` for nested file structure
- **File Icons**: Icons based on file type (.json, .md, .html, .csv)
- **Preview Panel**: `Dialog` or side panel for file content
- **File Actions**: `Button` group for download, preview, compare
- **Search**: `Input` for filename/content search
- **Filters**: `Select` for file type filtering

**File Type Support**:
```typescript
interface FileItem {
  name: string;
  type: 'json' | 'markdown' | 'html' | 'csv' | 'txt';
  size: number;
  created: string;
  stage: string; // Which Luigi task generated it
  preview?: string;
}

interface FileExplorerProps {
  planId: string;
  files: FileItem[];
  onFileSelect?: (file: FileItem) => void;
  onFileDownload?: (files: FileItem[]) => void;
  className?: string;
}
```

**Layout Design**:
```tsx
<div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
  <Card className="lg:col-span-1">
    <CardHeader>
      <CardTitle>Files ({files.length})</CardTitle>
      <Input placeholder="Search files..." />
      <Select> {/* File type filter */}
    </CardHeader>
    <CardContent>
      <Accordion type="multiple">
        {/* Hierarchical file tree */}
      </Accordion>
    </CardContent>
  </Card>

  <Card className="lg:col-span-2">
    <CardHeader>
      <CardTitle>Preview</CardTitle>
      <div className="flex gap-2">
        <Button>Download</Button>
        <Button variant="outline">Compare</Button>
      </div>
    </CardHeader>
    <CardContent>
      {/* File content preview */}
    </CardContent>
  </Card>
</div>
```

### **Component 4: Plan Comparison Tool**

**File**: `planexe-frontend/src/components/analysis/PlanComparison.tsx`

**Purpose**: Side-by-side comparison of different plan executions

**Features**:
- **Plan Selector**: `Select` dropdowns for choosing plans to compare
- **Metrics Comparison**: `Table` showing execution time, task counts, success rates
- **File Diff View**: Split view showing differences in generated files
- **Performance Charts**: Visual comparison of execution metrics

**Design**:
```tsx
<Card>
  <CardHeader>
    <CardTitle>Plan Comparison</CardTitle>
    <div className="flex gap-4">
      <div>
        <Label>Plan A</Label>
        <Select> {/* Plan selector */}
      </div>
      <div>
        <Label>Plan B</Label>
        <Select> {/* Plan selector */}
      </div>
    </div>
  </CardHeader>
  <CardContent>
    <Tabs defaultValue="overview">
      <TabsList>
        <TabsTrigger value="overview">Overview</TabsTrigger>
        <TabsTrigger value="tasks">Tasks</TabsTrigger>
        <TabsTrigger value="files">Files</TabsTrigger>
        <TabsTrigger value="performance">Performance</TabsTrigger>
      </TabsList>

      <TabsContent value="overview">
        <Table> {/* Comparison metrics */}
      </TabsContent>

      <TabsContent value="tasks">
        {/* Task-by-task comparison */}
      </TabsContent>
    </Tabs>
  </CardContent>
</Card>
```

### **Component 5: Performance Metrics Dashboard**

**File**: `planexe-frontend/src/components/monitoring/MetricsDashboard.tsx`

**Purpose**: Real-time and historical performance monitoring

**Metrics Tracked**:
- Pipeline execution time
- Task completion rates
- Memory usage over time
- LLM API call statistics
- Error rates and types

**UI Elements**:
```tsx
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
  <Card>
    <CardHeader>
      <CardTitle>Execution Time</CardTitle>
    </CardHeader>
    <CardContent>
      <div className="text-2xl font-bold">{executionTime}</div>
      <Progress value={progressPercent} />
    </CardContent>
  </Card>

  <Card>
    <CardHeader>
      <CardTitle>Tasks Completed</CardTitle>
    </CardHeader>
    <CardContent>
      <div className="text-2xl font-bold">{completedTasks}/61</div>
      <div className="text-sm text-muted-foreground">
        {successRate}% success rate
      </div>
    </CardContent>
  </Card>

  {/* Additional metric cards */}
</div>
```

### **Component 6: Smart Prompt Suggestions**

**File**: `planexe-frontend/src/components/planning/SmartSuggestions.tsx`

**Purpose**: AI-powered prompt suggestions based on successful historical runs

**Features**:
- **Category Tabs**: `Tabs` for different business types (retail, service, tech, etc.)
- **Suggestion Cards**: `Card` components showing example prompts
- **Success Metrics**: `Badge` showing historical success rates
- **Template System**: `Button` to use prompt as template

```tsx
<Card>
  <CardHeader>
    <CardTitle>Smart Prompt Suggestions</CardTitle>
    <CardDescription>
      Based on {historicalPlans} successful plans
    </CardDescription>
  </CardHeader>
  <CardContent>
    <Tabs defaultValue="business">
      <TabsList>
        <TabsTrigger value="business">Business</TabsTrigger>
        <TabsTrigger value="marketing">Marketing</TabsTrigger>
        <TabsTrigger value="project">Project</TabsTrigger>
        <TabsTrigger value="personal">Personal</TabsTrigger>
      </TabsList>

      <TabsContent value="business">
        <div className="grid gap-3">
          {suggestions.map(suggestion => (
            <Card key={suggestion.id} className="cursor-pointer hover:bg-accent">
              <CardContent className="pt-4">
                <div className="flex justify-between items-start">
                  <p className="text-sm">{suggestion.prompt}</p>
                  <Badge variant="secondary">
                    {suggestion.successRate}% success
                  </Badge>
                </div>
                <Button size="sm" className="mt-2">
                  Use Template
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      </TabsContent>
    </Tabs>
  </CardContent>
</Card>
```

## 🔧 **Implementation Guidelines**

### **Component Structure Standard**
```typescript
/**
 * Author: [Developer Name]
 * Date: YYYY-MM-DD
 * PURPOSE: [Component description and responsibility]
 * SRP and DRY check: Pass - [Explanation of single responsibility]
 */

'use client';

import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
// ... other shadcn/ui imports

interface ComponentNameProps {
  planId: string;
  // ... other props
  className?: string;
}

export const ComponentName: React.FC<ComponentNameProps> = ({
  planId,
  className = ''
}) => {
  // Component logic here

  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle>Component Title</CardTitle>
      </CardHeader>
      <CardContent>
        {/* Component content */}
      </CardContent>
    </Card>
  );
};
```

### **State Management Strategy**
- **Local State**: Use React hooks for component-specific state
- **Global State**: Extend existing Zustand stores for shared data
- **Real-time Data**: WebSocket connections (once Phase 1 is complete)
- **API Calls**: Direct FastAPI client calls (no API routes)

### **Styling Guidelines**
- **Use shadcn/ui variants**: Leverage existing button, badge, and card variants
- **Custom CSS**: Only for specific features like terminal syntax highlighting
- **Responsive Design**: Use Tailwind grid and flexbox for layouts
- **Dark Mode**: Ensure components work with existing dark mode support

### **Data Integration**
- **Luigi Task Data**: Source from `docs/LUIGI.md` dependency chain
- **Real Pipeline Outputs**: Use existing `/run` directory structure
- **API Integration**: Connect to existing FastAPI endpoints
- **File Handling**: Support all 109 generated file types

## 📊 **Component Priority Matrix**

### **High Priority (Phase 2A)**:
1. **TaskDependencyGraph** - Critical for understanding 61-task pipeline
2. **EnhancedTerminal** - Improves existing terminal functionality
3. **FileExplorer** - Essential for managing 109 generated files

### **Medium Priority (Phase 2B)**:
4. **MetricsDashboard** - Performance monitoring and debugging
5. **SmartSuggestions** - User experience enhancement

### **Low Priority (Phase 2C)**:
6. **PlanComparison** - Advanced analysis feature

## 🧪 **Testing Strategy**

### **Component Testing**:
- **React Testing Library**: Unit tests for all components
- **Real Data**: Use actual pipeline outputs from `/run` directory
- **shadcn/ui Integration**: Verify component compatibility
- **Responsive Testing**: Ensure mobile/desktop compatibility

### **Integration Testing**:
- **API Connectivity**: Test with real FastAPI backend
- **WebSocket Integration**: Once Phase 1 WebSocket is implemented
- **File Handling**: Test with all 109 generated file types
- **Performance**: Monitor rendering with large datasets

## 📋 **Implementation Checklist**

### **Prerequisites**:
- [ ] Phase 1 WebSocket implementation (optional for Phase 2A)
- [ ] shadcn/ui component library (✅ already installed)
- [ ] Existing FastAPI client (✅ already implemented)
- [ ] Real pipeline data for testing (✅ available in `/run`)

### **Phase 2A Deliverables**:
- [ ] TaskDependencyGraph component with 61-task visualization
- [ ] EnhancedTerminal with filtering and export features
- [ ] FileExplorer with preview and download capabilities
- [ ] Integration with existing page.tsx tab system
- [ ] Component documentation and usage examples

### **Success Criteria**:
- All components render correctly with shadcn/ui styling
- Real-time updates work with existing SSE or new WebSocket
- File operations handle all 109 pipeline output types
- Performance remains smooth with large datasets
- Components integrate seamlessly with existing UI architecture

This specification provides a complete roadmap for the next developer to implement professional-grade UI components that enhance the already solid PlanExe system.