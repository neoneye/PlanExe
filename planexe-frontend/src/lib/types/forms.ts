/**
 * Author: Claude Code using Sonnet 4
 * Date: 2025-09-19
 * PURPOSE: Form validation schemas and UI component types for enterprise planning interface
 * SRP and DRY check: Pass - Single responsibility for form/UI type definitions, uses zod for validation
 */

import { z } from 'zod';
import { SpeedVsDetail, PipelinePhase, PipelineStatus } from './pipeline';

// =======================
// FORM VALIDATION SCHEMAS
// =======================

export const PlanFormSchema = z.object({
  prompt: z
    .string()
    .min(10, 'Plan description must be at least 10 characters')
    .max(5000, 'Plan description must be less than 5000 characters')
    .refine(
      (text) => text.trim().length > 0,
      'Plan description cannot be empty or only whitespace'
    ),

  llmModel: z
    .string()
    .min(1, 'Please select an LLM model'),

  speedVsDetail: z
    .enum(['ALL_DETAILS_BUT_SLOW', 'FAST_BUT_SKIP_DETAILS']),

  openrouterApiKey: z
    .string()
    .optional()
    .refine(
      (key) => !key || key.startsWith('sk-or-v1-'),
      'OpenRouter API key must start with "sk-or-v1-"'
    ),

  title: z
    .string()
    .max(100, 'Title must be less than 100 characters')
    .optional(),

  tags: z
    .array(z.string())
    .max(10, 'Maximum 10 tags allowed')
    .optional(),
});

export const SessionConfigSchema = z.object({
  defaultSpeedVsDetail: z
    .enum(['ALL_DETAILS_BUT_SLOW', 'FAST_BUT_SKIP_DETAILS'])
    .default('ALL_DETAILS_BUT_SLOW'),

  preferredLLMModel: z
    .string()
    .min(1, 'Please select a preferred LLM model'),

  openrouterApiKey: z
    .string()
    .optional(),

  emailNotifications: z
    .boolean()
    .default(false),

  progressUpdates: z
    .boolean()
    .default(true),

  completionAlerts: z
    .boolean()
    .default(true),

  errorAlerts: z
    .boolean()
    .default(true),

  theme: z
    .enum(['light', 'dark', 'auto'])
    .default('auto'),

  compactMode: z
    .boolean()
    .default(false),

  showAdvancedOptions: z
    .boolean()
    .default(false),

  autoSave: z
    .boolean()
    .default(true),

  confirmBeforeStop: z
    .boolean()
    .default(true),
});

export const FileFilterSchema = z.object({
  phase: z
    .enum([
      'setup', 'initial_analysis', 'strategic_planning', 'scenario_planning',
      'contextual_analysis', 'assumption_management', 'project_planning',
      'governance', 'resource_planning', 'documentation', 'work_breakdown',
      'scheduling', 'reporting', 'completion'
    ])
    .optional(),

  fileType: z
    .enum(['json', 'md', 'html', 'csv', 'txt'])
    .optional(),

  outputType: z
    .enum(['raw', 'clean', 'markdown', 'html'])
    .optional(),

  search: z
    .string()
    .max(100, 'Search term must be less than 100 characters')
    .optional(),
});

export const LLMTestSchema = z.object({
  modelId: z
    .string()
    .min(1, 'Model ID is required'),

  apiKey: z
    .string()
    .optional(),

  testPrompt: z
    .string()
    .max(1000, 'Test prompt must be less than 1000 characters')
    .default('Hello, please respond with "OK" to confirm you are working.'),
});

// =======================
// FORM TYPES
// =======================

export type PlanFormData = z.infer<typeof PlanFormSchema>;
export type SessionConfigData = z.infer<typeof SessionConfigSchema>;
export type FileFilterData = z.infer<typeof FileFilterSchema>;
export type LLMTestData = z.infer<typeof LLMTestSchema>;

// =======================
// UI COMPONENT TYPES
// =======================

export interface FormFieldProps {
  name: string;
  label: string;
  description?: string;
  required?: boolean;
  disabled?: boolean;
  placeholder?: string;
  className?: string;
}

export interface SelectOption {
  value: string;
  label: string;
  description?: string;
  disabled?: boolean;
  icon?: string;
}

export interface ModelSelectProps extends FormFieldProps {
  options: SelectOption[];
  defaultValue?: string;
  onValueChange?: (value: string) => void;
  showDescription?: boolean;
  groupByProvider?: boolean;
}

export interface SpeedSelectorProps extends FormFieldProps {
  value: SpeedVsDetail;
  onValueChange: (value: SpeedVsDetail) => void;
  showEstimates?: boolean;
}

export interface PromptExamplesProps {
  examples: Array<{
    uuid: string;
    title: string;
    prompt: string;
    tags: string[];
    complexity: 'simple' | 'medium' | 'complex';
  }>;
  onSelectExample: (prompt: string) => void;
  maxExamples?: number;
  showComplexity?: boolean;
  groupByCategory?: boolean;
}

export interface ProgressBarProps {
  value: number;
  max?: number;
  size?: 'sm' | 'md' | 'lg';
  variant?: 'default' | 'success' | 'warning' | 'error';
  showPercentage?: boolean;
  animated?: boolean;
  className?: string;
}

export interface StatusBadgeProps {
  status: PipelineStatus;
  size?: 'sm' | 'md' | 'lg';
  showIcon?: boolean;
  interactive?: boolean;
  className?: string;
}

export interface PhaseIndicatorProps {
  phases: Array<{
    phase: PipelinePhase;
    status: 'pending' | 'active' | 'completed' | 'error';
    progress?: number;
  }>;
  orientation?: 'horizontal' | 'vertical';
  compact?: boolean;
  interactive?: boolean;
  onPhaseClick?: (phase: PipelinePhase) => void;
}

export interface FileIconProps {
  fileType: 'json' | 'md' | 'html' | 'csv' | 'txt';
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export interface DataTableProps<T> {
  data: T[];
  columns: Array<{
    key: keyof T;
    header: string;
    sortable?: boolean;
    filterable?: boolean;
    render?: (value: T[keyof T], row: T) => React.ReactNode;
  }>;
  pagination?: {
    page: number;
    pageSize: number;
    total: number;
    onPageChange: (page: number) => void;
  };
  sorting?: {
    column: keyof T;
    direction: 'asc' | 'desc';
    onSortChange: (column: keyof T, direction: 'asc' | 'desc') => void;
  };
  filtering?: {
    filters: Record<string, any>;
    onFilterChange: (filters: Record<string, any>) => void;
  };
  selection?: {
    selectedRows: string[];
    onSelectionChange: (selectedRows: string[]) => void;
  };
  loading?: boolean;
  emptyMessage?: string;
  className?: string;
}

// =======================
// LAYOUT COMPONENT TYPES
// =======================

export interface HeaderProps {
  title?: string;
  subtitle?: string;
  actions?: React.ReactNode;
  breadcrumbs?: Array<{
    label: string;
    href?: string;
    active?: boolean;
  }>;
  className?: string;
}

export interface SidebarProps {
  children: React.ReactNode;
  collapsed?: boolean;
  onToggle?: () => void;
  position?: 'left' | 'right';
  width?: number;
  className?: string;
}

export interface NavigationProps {
  items: Array<{
    id: string;
    label: string;
    icon?: string;
    href?: string;
    active?: boolean;
    badge?: string | number;
    children?: NavigationProps['items'];
  }>;
  orientation?: 'horizontal' | 'vertical';
  variant?: 'default' | 'pills' | 'underline';
  onItemClick?: (id: string) => void;
  className?: string;
}

export interface DashboardLayoutProps {
  header?: React.ReactNode;
  sidebar?: React.ReactNode;
  main: React.ReactNode;
  footer?: React.ReactNode;
  sidebarCollapsed?: boolean;
  fullHeight?: boolean;
  className?: string;
}

// =======================
// MODAL & DIALOG TYPES
// =======================

export interface ModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title?: string;
  description?: string;
  children: React.ReactNode;
  size?: 'sm' | 'md' | 'lg' | 'xl' | 'full';
  closable?: boolean;
  className?: string;
}

export interface ConfirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  confirmText?: string;
  cancelText?: string;
  variant?: 'default' | 'destructive';
  onConfirm: () => void;
  onCancel?: () => void;
  loading?: boolean;
}

export interface AlertDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  type?: 'info' | 'success' | 'warning' | 'error';
  actionText?: string;
  onAction?: () => void;
}

// =======================
// NOTIFICATION TYPES
// =======================

export interface Toast {
  id: string;
  title: string;
  description?: string;
  type: 'info' | 'success' | 'warning' | 'error';
  duration?: number;
  action?: {
    label: string;
    onClick: () => void;
  };
  persistent?: boolean;
}

export interface NotificationCenter {
  notifications: Array<{
    id: string;
    title: string;
    message: string;
    type: 'info' | 'success' | 'warning' | 'error';
    timestamp: Date;
    read: boolean;
    actions?: Array<{
      label: string;
      onClick: () => void;
      variant?: 'default' | 'primary' | 'destructive';
    }>;
  }>;
  unreadCount: number;
  onMarkAsRead: (id: string) => void;
  onMarkAllAsRead: () => void;
  onClear: () => void;
}

// =======================
// ERROR BOUNDARY TYPES
// =======================

export interface ErrorInfo {
  componentStack: string;
  errorBoundary?: string;
  eventId?: string;
}

export interface ErrorBoundaryProps {
  children: React.ReactNode;
  fallback?: React.ComponentType<{ error: Error; errorInfo: ErrorInfo }>;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
  isolate?: boolean;
  level?: 'page' | 'section' | 'component';
}

export interface ErrorFallbackProps {
  error: Error;
  errorInfo: ErrorInfo;
  resetError?: () => void;
  showDetails?: boolean;
  reportError?: () => void;
}

// =======================
// RESPONSIVE & ADAPTIVE TYPES
// =======================

export interface BreakpointConfig {
  sm: number;   // 640px
  md: number;   // 768px
  lg: number;   // 1024px
  xl: number;   // 1280px
  '2xl': number; // 1536px
}

export interface ResponsiveProps {
  breakpoints?: Partial<BreakpointConfig>;
  children: React.ReactNode | ((breakpoint: keyof BreakpointConfig) => React.ReactNode);
}

export interface AdaptiveLayoutProps {
  mobile: React.ReactNode;
  tablet?: React.ReactNode;
  desktop: React.ReactNode;
  breakpoint?: keyof BreakpointConfig;
}

// =======================
// KEYBOARD SHORTCUT TYPES
// =======================

export interface KeyboardShortcut {
  key: string;
  modifiers?: Array<'ctrl' | 'alt' | 'shift' | 'meta'>;
  description: string;
  action: () => void;
  disabled?: boolean;
  global?: boolean;
}

export interface ShortcutGroup {
  name: string;
  shortcuts: KeyboardShortcut[];
}

// =======================
// ACCESSIBILITY TYPES
// =======================

export interface A11yProps {
  ariaLabel?: string;
  ariaDescription?: string;
  ariaExpanded?: boolean;
  ariaSelected?: boolean;
  ariaDisabled?: boolean;
  role?: string;
  tabIndex?: number;
}

export interface FocusManagementProps {
  autoFocus?: boolean;
  restoreFocus?: boolean;
  trapFocus?: boolean;
  focusLock?: boolean;
}