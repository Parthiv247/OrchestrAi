// Core domain types shared across pages

import type { LucideIcon } from 'lucide-react'

export type { LucideIcon }

export interface Pipeline {
  id: string | number
  name: string
  dag_id?: string
  source_type: 'postgresql' | 'rest_api' | 'csv' | 'google_sheets' | string
  destination_type?: string
  schedule?: string
  status?: string
  is_active?: boolean
  last_run?: PipelineRun | null
  workspace_id?: string
  created_at?: string
}

export interface PipelineRun {
  id: string | number
  run_id?: string
  pipeline_id?: string | number
  pipeline_name?: string
  status: 'success' | 'failed' | 'running' | 'pending' | string
  records_ingested?: number
  records_loaded?: number
  records_failed?: number
  duration_seconds?: number
  started_at?: string
  finished_at?: string
  error_message?: string
  dag_id?: string
  date?: string
  records?: number
}

export interface Incident {
  id: string | number
  pipeline_name?: string
  anomaly_type?: 'ZERO_LOAD' | 'ROW_COUNT_DROP' | 'NULL_SPIKE' | 'PIPELINE_DELAY' | 'CONSECUTIVE_FAILURES' | 'ML_ANOMALY' | string
  approval_status?: 'pending' | 'approved' | 'rejected' | 'auto_healed' | string
  approval_token?: string
  root_cause?: string
  root_cause_confidence?: number
  fix_code?: string
  fix_language?: string
  confidence_score?: number
  sandbox_results?: Record<string, boolean>
  tests_passed?: number
  created_at?: string
  resolved_at?: string
  detection_time?: string
  // Extended fields used in observability
  detected_at?: string
  updated_at?: string
  status?: string
  type?: string
  severity?: string
  title?: string
  description?: string
  dag_id?: string
  pipeline?: string
  resolution?: string
  fix_applied?: string
  time_window?: string
}

export interface Connector {
  id: string | number
  name: string
  source_type: string
  status?: 'active' | 'paused' | 'error' | string
  last_synced?: string
  config?: Record<string, string>
}

export interface CatalogConnector {
  id: string
  name: string
  category: string
  description: string
  color: string
  logo?: string
  logo_url?: string
  domain?: string
  popular?: boolean
  fields?: ConnectorField[]
}

export interface ConnectorField {
  key: string
  label: string
  type: 'text' | 'password' | 'number' | 'textarea' | 'select' | string
  placeholder?: string
  options?: string[]
}

export interface SavedConnection {
  id: string
  connector_id: string
  name: string
  status?: 'connected' | 'error' | 'untested' | string
  connector_name?: string
  connector_category?: string
  connector_logo?: string
  connector_logo_url?: string
  connector_domain?: string
  connector_color?: string
  test_message?: string
  last_tested_at?: string
  updated_at?: string
}

export interface HealingStatus {
  total_incidents: number
  auto_healed: number
  pending_approval: number
  pending?: number
  approved?: number
  deployed?: number
  mttr_minutes?: number
  success_rate?: number
}

export interface LearningStats {
  total_fixes_stored?: number
  total_queries_stored?: number
  auto_healed_count?: number
  avg_mttr?: number
  success_rate?: number
  weekly_improvement_pct?: number
  mttr_trend?: MTTRPoint[]
  strategy_performance?: Record<string, unknown>
}

export interface MTTRPoint {
  date: string
  avg_mttr_seconds: number
  incident_count: number
}

export interface MLMetrics {
  isolation_forest?: {
    f1: number
    precision: number
    recall: number
    roc_auc: number
    n_samples?: number
    trained_on?: number
    trained_at?: string
    last_trained?: string
    [key: string]: number | string | undefined
  }
  random_forest?: {
    weighted_f1: number
    accuracy: number
    n_samples?: number
    last_trained?: string
    classes?: string[]
    per_class_f1?: Record<string, number>
    [key: string]: number | string | string[] | Record<string, number> | undefined
  }
  anomaly_classifier?: {
    weighted_f1: number
    accuracy: number
    per_class_f1?: Record<string, number>
  }
}

export interface InsightItem {
  id?: string | number
  title?: string
  description?: string
  severity?: 'anomaly' | 'warning' | 'opportunity' | 'info' | string
  pipeline_name?: string
  metric?: string
  value?: number | string
  created_at?: string
  time_window?: string
}

export interface DataQualityRule {
  id: string | number
  name: string
  rule_type?: string
  column_name?: string
  status?: 'pass' | 'fail' | 'warning' | string
  last_checked?: string
}

export interface LineageNode {
  id: string
  label?: string
  type?: 'source' | 'pipeline' | 'destination' | 'model' | string
  status?: string
}

export interface LineageEdge {
  source: string
  target: string
  label?: string
}

export interface CostOptimization {
  id?: string | number
  query?: string
  original_cost?: number
  optimized_cost?: number
  savings_pct?: number
  suggestion?: string
}

export interface ReportConfig {
  id: string | number
  name: string
  schedule?: string
  recipients?: string[]
  format?: 'pdf' | 'csv' | 'email' | string
  last_sent?: string
}

export interface TeamMember {
  id: string | number
  name: string
  email: string
  role: 'admin' | 'editor' | 'viewer' | string
  status?: 'active' | 'invited' | string
  initials?: string
  last_active?: string
}

export interface ApiToken {
  id: string | number
  name: string
  scopes?: string
  token_preview?: string
  revoked?: boolean
  created_at?: string
  expires_at?: string
}

export interface AlertRule {
  id: string | number
  name: string
  condition?: string
  channel?: string
  enabled?: boolean
  fire_count?: number
}

export interface NotificationHistory {
  id: string | number
  channel?: string
  subject?: string
  status?: string
  sent_at?: string
}

export interface AuditLogEntry {
  id: string | number
  user?: string
  actor?: string
  action?: string
  resource?: string
  resource_type?: string
  details?: Record<string, unknown>
  timestamp?: string
  created_at?: string
  ip?: string
}

export interface QueryResult {
  columns: string[]
  rows: (string | number | null)[][]
}

export interface TableInfo {
  table_name: string
  schema?: string
  row_count?: number
  description?: string
}

export interface DbtModel {
  id?: string | number
  name: string
  schema_layer?: 'staging' | 'marts' | string
  sql?: string
  description?: string
  columns?: string[]
  status?: string
}

export interface DbtRun {
  id?: string | number
  model_name?: string
  status?: string
  started_at?: string
  duration_seconds?: number
  rows?: (string | number | null)[][]
}

export interface AntiPattern {
  type?: string
  pattern?: string
  description?: string
  suggestion?: string
  line?: number
}

export interface OptimizerResult {
  optimized_sql?: string
  anti_patterns?: AntiPattern[]
  changes_made?: string[]
  savings_percent?: number
  dollar_savings?: number
  improvement_pct?: number
  explanation?: string
}

export interface SavingsBreakdown {
  [key: string]: {
    queries_optimized?: number
    savings_usd?: number
    avg_improvement_pct?: number
  }
}

export interface SavingsHistory {
  original_sql?: string
  dollar_savings?: number
  savings_percent?: number
  ts?: Date | string
  created_at?: string
  date?: string
  saved_usd?: number
  queries?: number
}
