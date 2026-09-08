'use client'
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ShieldCheck, AlertTriangle, AlertCircle, CheckCircle2,
  Plus, Play, Trash2, RefreshCw, ChevronRight, GitBranch,
  Database, X, Search, Eye, EyeOff, Scan,
} from 'lucide-react'
import api from '@/lib/api'
import { DEMO_QUALITY_SUMMARY, DEMO_QUALITY_TABLES, DEMO_QUALITY_RULES, DEMO_DRIFT_EVENTS } from '@/lib/demo'

async function apiFetch(path: string, opts?: RequestInit) {
  const method = ((opts?.method ?? 'GET') as string).toUpperCase()
  let body: unknown
  if (opts?.body) {
    try { body = JSON.parse(opts.body as string) } catch { body = opts.body }
  }
  const r = await api.request({ method, url: path, data: body })
  return r.data
}

// ── Types ──────────────────────────────────────────────────────────────────────
interface TableHealth {
  name: string
  row_count: number
  column_count: number
  null_pct: number
  health_score: number
  status: 'healthy' | 'warning' | 'critical' | 'unknown'
}

interface QualityRule {
  id: string
  name: string
  description: string
  table_name: string
  column_name: string
  rule_type: string
  condition: string
  threshold: number
  severity: string
  enabled: boolean
  last_run_at: string | null
  last_status: string
  last_message: string
}

interface DriftEvent {
  id: string
  table_name: string
  event_type: string
  column_name: string
  old_value: string
  new_value: string
  detected_at: string
  resolved: boolean
}

interface ColumnStat {
  name: string
  type: string
  nullable: boolean
  null_pct: number | null
  distinct_count: number | null
  min?: string
  max?: string
}

// ── Small components ───────────────────────────────────────────────────────────

function ScoreBadge({ score }: { score: number }) {
  const color = score >= 80 ? '#10B981' : score >= 50 ? '#f59e0b' : '#ef4444'
  return (
    <div className="relative w-12 h-12 flex-shrink-0">
      <svg viewBox="0 0 36 36" className="w-full h-full -rotate-90">
        <circle cx="18" cy="18" r="15" fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="3" />
        <circle cx="18" cy="18" r="15" fill="none" stroke={color} strokeWidth="3"
          strokeDasharray={`${score * 0.942} 94.2`} strokeLinecap="round" />
      </svg>
      <span className="absolute inset-0 flex items-center justify-center text-[11px] font-bold text-white">{score}</span>
    </div>
  )
}

function StatusPill({ status }: { status: string }) {
  const map: Record<string, { color: string; label: string }> = {
    healthy:  { color: 'rgba(34,197,94,0.15)',   label: 'Healthy' },
    warning:  { color: 'rgba(245,158,11,0.15)',  label: 'Warning' },
    critical: { color: 'rgba(239,68,68,0.15)',   label: 'Critical' },
    passed:   { color: 'rgba(34,197,94,0.15)',   label: 'Passed' },
    failed:   { color: 'rgba(239,68,68,0.15)',   label: 'Failed' },
    pending:  { color: 'rgba(148,163,184,0.15)', label: 'Pending' },
    unknown:  { color: 'rgba(148,163,184,0.15)', label: 'Unknown' },
  }
  const s = map[status] || map.unknown
  const textColor = status === 'healthy' || status === 'passed' ? '#10B981'
    : status === 'warning' ? '#f59e0b'
    : status === 'critical' || status === 'failed' ? '#ef4444'
    : '#94a3b8'
  return (
    <span className="text-xs px-2 py-0.5 rounded-full font-medium" style={{ background: s.color, color: textColor }}>
      {s.label}
    </span>
  )
}

// ── Add Rule Modal ─────────────────────────────────────────────────────────────

function AddRuleModal({ tables, onClose, onSave }: {
  tables: TableHealth[]
  onClose: () => void
  onSave: (data: Record<string, unknown>) => void
}) {
  const [form, setForm] = useState({
    name: '',
    description: '',
    table_name: tables[0]?.name || '',
    column_name: '',
    rule_type: 'not_null',
    condition: '',
    threshold: 0,
    severity: 'warning',
    enabled: true,
  })

  const ruleTypes = [
    { value: 'not_null',   label: 'Not Null',     desc: 'Column null % < threshold' },
    { value: 'uniqueness', label: 'Uniqueness',   desc: 'Duplicate % < threshold' },
    { value: 'row_count',  label: 'Row Count',    desc: 'Table rows ≥ threshold' },
    { value: 'freshness',  label: 'Freshness',    desc: 'Max timestamp age < threshold (hours)' },
    { value: 'range',      label: 'Range Check',  desc: 'Show min/max of a column' },
    { value: 'custom_sql', label: 'Custom SQL',   desc: 'SELECT returning TRUE/FALSE' },
  ]

  const needsColumn = ['not_null', 'uniqueness', 'freshness', 'range'].includes(form.rule_type)
  const needsCondition = form.rule_type === 'custom_sql'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: 'rgba(0,0,0,0.7)' }}>
      <div className="w-full max-w-lg rounded-2xl p-6 space-y-4"
        style={{ background: 'hsl(var(--card))', border: '1px solid hsl(var(--border))' }}>
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-white">New Quality Rule</h3>
          <button onClick={onClose}><X size={18} style={{ color: 'hsl(var(--muted-foreground))' }} /></button>
        </div>

        <div className="space-y-3">
          <div>
            <label className="text-xs font-medium mb-1 block" style={{ color: 'hsl(var(--muted-foreground))' }}>Rule Name</label>
            <input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
              placeholder="e.g. Orders not null check"
              className="w-full px-3 py-2 rounded-lg text-sm focus:outline-none text-white"
              style={{ background: 'hsl(var(--muted))', border: '1px solid hsl(var(--border))' }} />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium mb-1 block" style={{ color: 'hsl(var(--muted-foreground))' }}>Table</label>
              <select value={form.table_name} onChange={e => setForm(f => ({ ...f, table_name: e.target.value }))}
                className="w-full px-3 py-2 rounded-lg text-sm focus:outline-none text-white"
                style={{ background: 'hsl(var(--muted))', border: '1px solid hsl(var(--border))' }}>
                {tables.map(t => <option key={t.name} value={t.name}>{t.name}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs font-medium mb-1 block" style={{ color: 'hsl(var(--muted-foreground))' }}>Rule Type</label>
              <select value={form.rule_type} onChange={e => setForm(f => ({ ...f, rule_type: e.target.value }))}
                className="w-full px-3 py-2 rounded-lg text-sm focus:outline-none text-white"
                style={{ background: 'hsl(var(--muted))', border: '1px solid hsl(var(--border))' }}>
                {ruleTypes.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
              </select>
            </div>
          </div>

          <p className="text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>
            {ruleTypes.find(r => r.value === form.rule_type)?.desc}
          </p>

          {needsColumn && (
            <div>
              <label className="text-xs font-medium mb-1 block" style={{ color: 'hsl(var(--muted-foreground))' }}>Column Name</label>
              <input value={form.column_name} onChange={e => setForm(f => ({ ...f, column_name: e.target.value }))}
                placeholder="column_name"
                className="w-full px-3 py-2 rounded-lg text-sm focus:outline-none text-white"
                style={{ background: 'hsl(var(--muted))', border: '1px solid hsl(var(--border))' }} />
            </div>
          )}

          {needsCondition && (
            <div>
              <label className="text-xs font-medium mb-1 block" style={{ color: 'hsl(var(--muted-foreground))' }}>SQL Condition</label>
              <textarea value={form.condition} onChange={e => setForm(f => ({ ...f, condition: e.target.value }))}
                placeholder="SELECT COUNT(*) = 0 FROM orders WHERE total < 0"
                rows={3}
                className="w-full px-3 py-2 rounded-lg text-sm focus:outline-none text-white font-mono"
                style={{ background: 'hsl(var(--muted))', border: '1px solid hsl(var(--border))' }} />
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium mb-1 block" style={{ color: 'hsl(var(--muted-foreground))' }}>
                Threshold {form.rule_type === 'not_null' || form.rule_type === 'uniqueness' ? '(%)' : form.rule_type === 'freshness' ? '(hours)' : '(rows)'}
              </label>
              <input type="number" value={form.threshold} onChange={e => setForm(f => ({ ...f, threshold: Number(e.target.value) }))}
                className="w-full px-3 py-2 rounded-lg text-sm focus:outline-none text-white"
                style={{ background: 'hsl(var(--muted))', border: '1px solid hsl(var(--border))' }} />
            </div>
            <div>
              <label className="text-xs font-medium mb-1 block" style={{ color: 'hsl(var(--muted-foreground))' }}>Severity</label>
              <select value={form.severity} onChange={e => setForm(f => ({ ...f, severity: e.target.value }))}
                className="w-full px-3 py-2 rounded-lg text-sm focus:outline-none text-white"
                style={{ background: 'hsl(var(--muted))', border: '1px solid hsl(var(--border))' }}>
                <option value="info">Info</option>
                <option value="warning">Warning</option>
                <option value="critical">Critical</option>
              </select>
            </div>
          </div>
        </div>

        <div className="flex gap-3 pt-2">
          <button onClick={onClose} className="flex-1 py-2 rounded-xl text-sm font-medium transition-colors hover:bg-white/5"
            style={{ border: '1px solid hsl(var(--border))', color: 'hsl(var(--muted-foreground))' }}>
            Cancel
          </button>
          <button onClick={() => onSave(form)} disabled={!form.name || !form.table_name}
            className="flex-1 py-2 rounded-xl text-sm font-semibold text-white transition-all hover:opacity-90 disabled:opacity-40"
            style={{ background: '#0EA5E9' }}>
            Create Rule
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Table Detail Drawer ────────────────────────────────────────────────────────

function TableDetailDrawer({ tableName, onClose }: { tableName: string; onClose: () => void }) {
  const { data, isLoading } = useQuery({
    queryKey: ['quality-table-detail', tableName],
    queryFn: () => apiFetch(`/api/quality/tables/${tableName}`),
  })

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-end p-4" style={{ background: 'rgba(0,0,0,0.5)' }}
      onClick={onClose}>
      <div className="w-full max-w-lg h-full max-h-[90vh] rounded-2xl overflow-hidden flex flex-col"
        style={{ background: 'hsl(var(--card))', border: '1px solid hsl(var(--border))' }}
        onClick={e => e.stopPropagation()}>
        <div className="p-5 flex items-center justify-between" style={{ borderBottom: '1px solid hsl(var(--border))' }}>
          <div>
            <h3 className="font-semibold text-white font-mono">{tableName}</h3>
            {data && <p className="text-xs mt-0.5" style={{ color: 'hsl(var(--muted-foreground))' }}>
              {data.row_count?.toLocaleString()} rows · Health score {data.health_score}
            </p>}
          </div>
          <button onClick={onClose}><X size={18} style={{ color: 'hsl(var(--muted-foreground))' }} /></button>
        </div>

        <div className="flex-1 overflow-y-auto p-5">
          {isLoading ? (
            <div className="space-y-2">
              {[1,2,3,4,5].map(i => (
                <div key={i} className="h-10 rounded-lg animate-pulse" style={{ background: 'hsl(var(--muted))' }} />
              ))}
            </div>
          ) : data?.columns ? (
            <table className="w-full text-sm">
              <thead>
                <tr style={{ borderBottom: '1px solid hsl(var(--border))' }}>
                  {['Column', 'Type', 'Null %', 'Distinct', 'Range'].map(h => (
                    <th key={h} className="text-left py-2 px-2 text-xs font-medium" style={{ color: 'hsl(var(--muted-foreground))' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(data.columns as ColumnStat[]).map((col, i) => (
                  <tr key={i} className="hover:bg-white/5" style={{ borderBottom: '1px solid hsl(var(--border))' }}>
                    <td className="py-2 px-2 font-mono text-white text-xs">{col.name}</td>
                    <td className="py-2 px-2 text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>{col.type}</td>
                    <td className="py-2 px-2">
                      {col.null_pct != null ? (
                        <div className="flex items-center gap-2">
                          <div className="w-16 h-1.5 rounded-full overflow-hidden" style={{ background: 'hsl(var(--muted))' }}>
                            <div className="h-full rounded-full" style={{
                              width: `${col.null_pct}%`,
                              background: col.null_pct > 20 ? '#ef4444' : col.null_pct > 5 ? '#f59e0b' : '#10B981'
                            }} />
                          </div>
                          <span className="text-xs text-white">{col.null_pct}%</span>
                        </div>
                      ) : <span className="text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>—</span>}
                    </td>
                    <td className="py-2 px-2 text-xs text-white">{col.distinct_count?.toLocaleString() ?? '—'}</td>
                    <td className="py-2 px-2 text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>
                      {col.min != null ? `${col.min} – ${col.max}` : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="text-center py-8 text-sm" style={{ color: 'hsl(var(--muted-foreground))' }}>No column data available</p>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Main Page ──────────────────────────────────────────────────────────────────

type TabId = 'tables' | 'rules' | 'drift' | 'pii'

interface PiiResult {
  id: string
  table_name: string
  column_name: string
  pii_type: string
  severity: 'high' | 'medium' | 'low'
  detection_method: string
  confidence: number
  suppressed: boolean
  tagged_at: string | null
}

export default function QualityPage() {
  const qc = useQueryClient()
  const [tab, setTab] = useState<TabId>('tables')
  const [search, setSearch] = useState('')
  const [showAddRule, setShowAddRule] = useState(false)
  const [runningRule, setRunningRule] = useState<string | null>(null)
  const [selectedTable, setSelectedTable] = useState<string | null>(null)
  const [piiScanning, setPiiScanning] = useState(false)

  const { data: summary } = useQuery({
    queryKey: ['quality-summary'],
    queryFn: () => apiFetch('/api/quality/summary'),
    refetchInterval: 30000,
  })

  const { data: tablesData, isLoading: tablesLoading } = useQuery({
    queryKey: ['quality-tables'],
    queryFn: () => apiFetch('/api/quality/tables'),
    refetchInterval: 60000,
  })

  const { data: rulesData, isLoading: rulesLoading } = useQuery({
    queryKey: ['quality-rules'],
    queryFn: () => apiFetch('/api/quality/rules'),
  })

  const { data: driftData, isLoading: driftLoading } = useQuery({
    queryKey: ['quality-drift'],
    queryFn: () => apiFetch('/api/quality/drift'),
  })

  const { data: piiData, isLoading: piiLoading, refetch: refetchPii } = useQuery({
    queryKey: ['quality-pii'],
    queryFn: () => apiFetch('/api/quality/pii-results'),
  })

  const createRule = useMutation({
    mutationFn: (body: Record<string, unknown>) => apiFetch('/api/quality/rules', { method: 'POST', body: JSON.stringify(body) }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['quality-rules'] }); setShowAddRule(false) },
  })

  const deleteRule = useMutation({
    mutationFn: (id: string) => apiFetch(`/api/quality/rules/${id}`, { method: 'DELETE' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['quality-rules'] }),
  })

  const runRule = async (id: string) => {
    setRunningRule(id)
    try {
      await apiFetch(`/api/quality/rules/${id}/run`, { method: 'POST' })
      qc.invalidateQueries({ queryKey: ['quality-rules'] })
    } finally {
      setRunningRule(null)
    }
  }

  const _qualityDown = !tablesLoading && !rulesLoading && !tablesData && !rulesData

  const tables: TableHealth[] = tablesData?.tables?.length ? tablesData.tables : (_qualityDown ? (DEMO_QUALITY_TABLES as unknown as TableHealth[]) : [])
  const rules: QualityRule[] = rulesData?.rules?.length ? rulesData.rules : (_qualityDown ? (DEMO_QUALITY_RULES as unknown as QualityRule[]) : [])
  const driftEvents: DriftEvent[] = driftData?.events?.length ? driftData.events : (_qualityDown ? (DEMO_DRIFT_EVENTS as unknown as DriftEvent[]) : [])
  const piiByTable: Record<string, PiiResult[]> = piiData?.by_table || {}
  const allPiiResults: PiiResult[] = Object.values(piiByTable).flat()

  const _summarySource = summary || (_qualityDown ? DEMO_QUALITY_SUMMARY : null)

  const runPiiScan = async () => {
    setPiiScanning(true)
    try {
      await apiFetch('/api/quality/pii-scan', { method: 'POST' })
      refetchPii()
    } finally {
      setPiiScanning(false)
    }
  }

  const suppressPii = async (id: string) => {
    await apiFetch(`/api/quality/pii-results/${id}/suppress`, { method: 'POST' })
    refetchPii()
  }

  const filteredTables = tables.filter(t => t.name.toLowerCase().includes(search.toLowerCase()))

  const summaryCards = [
    { label: 'Tables Monitored', value: _summarySource?.table_count ?? '—', icon: Database,    color: '#0EA5E9' },
    { label: 'Active Rules',     value: _summarySource?.rule_count ?? '—',  icon: ShieldCheck, color: '#10B981' },
    { label: 'Failing Rules',    value: _summarySource?.failing_rules ?? 0, icon: AlertCircle, color: '#ef4444' },
    { label: 'Open Drift',       value: _summarySource?.open_drift_events ?? 0, icon: GitBranch, color: '#f59e0b' },
  ]

  const driftIcon: Record<string, string> = {
    column_added: '＋', column_dropped: '−', type_changed: '⇄', renamed: '↺',
  }

  const piiHighCount = allPiiResults.filter(r => r.severity === 'high' && !r.suppressed).length

  const TABS: { id: TabId; label: string; badge?: number }[] = [
    { id: 'tables', label: 'Table Health' },
    { id: 'rules',  label: 'Quality Rules' },
    { id: 'drift',  label: 'Schema Drift' },
    { id: 'pii',    label: 'PII Scanner', badge: piiHighCount || undefined },
  ]

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div style={{ marginBottom: 4 }}>
        <div className="flex items-start justify-between flex-wrap gap-3" style={{ marginBottom: 18 }}>
          <div>
            <h1 style={{ fontSize: 22, fontWeight: 800, letterSpacing: '-0.02em', color: 'var(--text-primary)', margin: 0 }}>
              Data Quality
            </h1>
            <p style={{ fontSize: 13, color: 'var(--text-muted)', margin: '4px 0 0' }}>
              Schema health, quality rules, drift detection, and PII scanning
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span style={{
              fontSize: 12, fontWeight: 700, padding: '5px 12px', borderRadius: 20,
              background: summary?.overall_health === 'good' ? 'rgba(16,185,129,0.12)' : summary?.overall_health === 'warning' ? 'rgba(245,158,11,0.12)' : 'rgba(239,68,68,0.12)',
              border: `1px solid ${summary?.overall_health === 'good' ? 'rgba(16,185,129,0.25)' : summary?.overall_health === 'warning' ? 'rgba(245,158,11,0.25)' : 'rgba(239,68,68,0.25)'}`,
              color: summary?.overall_health === 'good' ? '#10B981' : summary?.overall_health === 'warning' ? '#F59E0B' : '#EF4444',
            }}>
              {summary?.overall_health === 'good' ? '✓ Healthy' : summary?.overall_health === 'warning' ? '⚠ Warning' : '✕ Critical'}
            </span>
            {tab === 'rules' && (
              <button onClick={() => setShowAddRule(true)}
                className="btn-primary flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold text-white hover:opacity-90"
                style={{ background: '#0EA5E9' }}>
                <Plus size={14} /> Add Rule
              </button>
            )}
            {tab === 'pii' && allPiiResults.length > 0 && (
              <button onClick={runPiiScan} disabled={piiScanning}
                className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50"
                style={{ background: '#7C3AED', borderRadius: 9 }}>
                <Scan size={14} className={piiScanning ? 'animate-spin' : ''} />
                {piiScanning ? 'Scanning…' : 'Re-scan'}
              </button>
            )}
          </div>
        </div>
        <div style={{ height: 1, background: 'linear-gradient(90deg, var(--border) 0%, transparent 80%)' }} />
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-4 gap-4">
        {summaryCards.map(c => {
          const Icon = c.icon
          return (
            <div key={c.label} className="glass rounded-xl p-4 flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0"
                style={{ background: c.color + '20' }}>
                <Icon size={18} style={{ color: c.color }} />
              </div>
              <div>
                <p className="text-xl font-bold text-white">{String(c.value)}</p>
                <p className="text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>{c.label}</p>
              </div>
            </div>
          )
        })}
      </div>

      {/* Tabs */}
      <div className="flex items-center justify-between">
        <div className="flex gap-1 p-1 rounded-xl w-fit" style={{ background: 'hsl(var(--muted))' }}>
          {TABS.map(t => (
            <button key={t.id} onClick={() => setTab(t.id)}
              className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-sm font-medium transition-all"
              style={{
                background: tab === t.id ? 'hsl(var(--card))' : 'transparent',
                color: tab === t.id ? 'white' : 'hsl(var(--muted-foreground))',
              }}>
              {t.label}
              {t.badge ? (
                <span className="min-w-[18px] h-[18px] rounded-full text-white text-[10px] flex items-center justify-center font-bold px-1"
                  style={{ background: '#EF4444' }}>
                  {t.badge}
                </span>
              ) : null}
            </button>
          ))}
        </div>
        {tab === 'pii' && (
          <button onClick={runPiiScan} disabled={piiScanning}
            className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50"
            style={{ background: '#7C3AED' }}>
            <Scan size={14} className={piiScanning ? 'animate-spin' : ''} />
            {piiScanning ? 'Scanning…' : 'Run PII Scan'}
          </button>
        )}
      </div>

      {/* Tab: Table Health */}
      {tab === 'tables' && (
        <div className="space-y-3">
          <div className="flex items-center gap-2 px-3 py-2 rounded-xl w-80"
            style={{ background: 'hsl(var(--muted))', border: '1px solid hsl(var(--border))' }}>
            <Search size={14} style={{ color: 'hsl(var(--muted-foreground))' }} />
            <input value={search} onChange={e => setSearch(e.target.value)}
              placeholder="Search tables..."
              className="flex-1 bg-transparent text-sm focus:outline-none text-white" />
            {search && <button onClick={() => setSearch('')}><X size={12} style={{ color: 'hsl(var(--muted-foreground))' }} /></button>}
          </div>

          {tablesLoading ? (
            <div className="space-y-2">
              {[1,2,3,4,5].map(i => (
                <div key={i} className="h-16 rounded-xl animate-pulse" style={{ background: 'hsl(var(--muted))' }} />
              ))}
            </div>
          ) : filteredTables.length === 0 ? (
            <div className="rounded-2xl p-12 text-center" style={{ border: '2px dashed hsl(var(--border))' }}>
              <Database size={32} className="mx-auto mb-3" style={{ color: '#4B5563' }} />
              <p className="text-sm text-white font-medium mb-1">No tables found</p>
              <p className="text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>
                Tables from your connected data sources will appear here
              </p>
            </div>
          ) : (
            <div className="glass rounded-xl overflow-hidden">
              <table className="w-full">
                <thead>
                  <tr style={{ borderBottom: '1px solid hsl(var(--border))', background: 'hsl(var(--muted))' }}>
                    {['Table', 'Status', 'Health Score', 'Rows', 'Columns', 'Null %', ''].map(h => (
                      <th key={h} className="text-left px-4 py-3 text-xs font-medium" style={{ color: 'hsl(var(--muted-foreground))' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filteredTables.map(t => (
                    <tr key={t.name} className="hover:bg-white/5 cursor-pointer" style={{ borderBottom: '1px solid hsl(var(--border))' }}
                      onClick={() => setSelectedTable(t.name)}>
                      <td className="px-4 py-3 font-mono text-sm text-white">{t.name}</td>
                      <td className="px-4 py-3"><StatusPill status={t.status} /></td>
                      <td className="px-4 py-3"><ScoreBadge score={t.health_score} /></td>
                      <td className="px-4 py-3 text-sm text-white">{t.row_count.toLocaleString()}</td>
                      <td className="px-4 py-3 text-sm" style={{ color: 'hsl(var(--muted-foreground))' }}>{t.column_count}</td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <div className="w-20 h-1.5 rounded-full overflow-hidden" style={{ background: 'hsl(var(--muted))' }}>
                            <div className="h-full rounded-full" style={{
                              width: `${Math.min(t.null_pct, 100)}%`,
                              background: t.null_pct > 20 ? '#ef4444' : t.null_pct > 5 ? '#f59e0b' : '#10B981'
                            }} />
                          </div>
                          <span className="text-xs text-white">{t.null_pct}%</span>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <button className="flex items-center gap-1 text-xs px-2 py-1 rounded-lg hover:bg-white/10 transition-colors"
                          style={{ color: 'hsl(var(--muted-foreground))' }}>
                          Inspect <ChevronRight size={10} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Tab: Quality Rules */}
      {tab === 'rules' && (
        <div className="space-y-3">
          {rulesLoading ? (
            <div className="space-y-2">
              {[1,2,3].map(i => <div key={i} className="h-20 rounded-xl animate-pulse" style={{ background: 'hsl(var(--muted))' }} />)}
            </div>
          ) : rules.length === 0 ? (
            <div className="rounded-2xl p-12 text-center" style={{ border: '2px dashed hsl(var(--border))' }}>
              <ShieldCheck size={32} className="mx-auto mb-3" style={{ color: '#4B5563' }} />
              <p className="text-sm text-white font-medium mb-1">No quality rules yet</p>
              <p className="text-xs mb-4" style={{ color: 'hsl(var(--muted-foreground))' }}>
                Create rules to monitor null %, row counts, freshness, and more
              </p>
              <button onClick={() => setShowAddRule(true)}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold text-white"
                style={{ background: '#0EA5E9' }}>
                <Plus size={14} /> Add First Rule
              </button>
            </div>
          ) : (
            <div className="glass rounded-xl overflow-hidden">
              <table className="w-full">
                <thead>
                  <tr style={{ borderBottom: '1px solid hsl(var(--border))', background: 'hsl(var(--muted))' }}>
                    {['Rule', 'Table / Column', 'Type', 'Severity', 'Last Run', 'Status', 'Actions'].map(h => (
                      <th key={h} className="text-left px-4 py-3 text-xs font-medium" style={{ color: 'hsl(var(--muted-foreground))' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rules.map(r => (
                    <tr key={r.id} className="hover:bg-white/5" style={{ borderBottom: '1px solid hsl(var(--border))' }}>
                      <td className="px-4 py-3">
                        <p className="text-sm font-medium text-white">{r.name}</p>
                        {r.last_message && (
                          <p className="text-xs mt-0.5 truncate max-w-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>
                            {r.last_message}
                          </p>
                        )}
                      </td>
                      <td className="px-4 py-3 font-mono text-xs text-white">
                        {r.table_name}{r.column_name ? `.${r.column_name}` : ''}
                      </td>
                      <td className="px-4 py-3 text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>{r.rule_type}</td>
                      <td className="px-4 py-3">
                        <span className="text-xs px-2 py-0.5 rounded-full" style={{
                          background: r.severity === 'critical' ? 'rgba(239,68,68,0.15)' : r.severity === 'warning' ? 'rgba(245,158,11,0.15)' : 'rgba(59,130,246,0.15)',
                          color: r.severity === 'critical' ? '#ef4444' : r.severity === 'warning' ? '#f59e0b' : '#38BDF8',
                        }}>{r.severity}</span>
                      </td>
                      <td className="px-4 py-3 text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>
                        {r.last_run_at ? new Date(r.last_run_at).toLocaleString() : 'Never'}
                      </td>
                      <td className="px-4 py-3"><StatusPill status={r.last_status} /></td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-1">
                          <button onClick={() => runRule(r.id)} disabled={runningRule === r.id}
                            className="p-1.5 rounded-lg hover:bg-white/10 transition-colors disabled:opacity-40"
                            title="Run now" style={{ color: '#38BDF8' }}>
                            {runningRule === r.id ? <RefreshCw size={13} className="animate-spin" /> : <Play size={13} />}
                          </button>
                          <button onClick={() => deleteRule.mutate(r.id)}
                            className="p-1.5 rounded-lg hover:bg-red-500/10 transition-colors"
                            title="Delete" style={{ color: '#ef4444' }}>
                            <Trash2 size={13} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Tab: Schema Drift */}
      {tab === 'drift' && (
        <div className="space-y-3">
          {driftLoading ? (
            <div className="space-y-2">
              {[1,2,3].map(i => <div key={i} className="h-16 rounded-xl animate-pulse" style={{ background: 'hsl(var(--muted))' }} />)}
            </div>
          ) : driftEvents.length === 0 ? (
            <div className="rounded-2xl p-12 text-center" style={{ border: '2px dashed hsl(var(--border))' }}>
              <GitBranch size={32} className="mx-auto mb-3" style={{ color: '#4B5563' }} />
              <p className="text-sm text-white font-medium mb-1">No drift events detected</p>
              <p className="text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>
                Schema changes will appear here when detected against saved snapshots
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {driftEvents.map(e => (
                <div key={e.id} className="glass rounded-xl p-4 flex items-start gap-4">
                  <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 text-lg font-bold"
                    style={{
                      background: e.resolved ? 'rgba(34,197,94,0.1)' : 'rgba(245,158,11,0.1)',
                      color: e.resolved ? '#10B981' : '#f59e0b',
                    }}>
                    {driftIcon[e.event_type] || '?'}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs font-semibold uppercase tracking-wider" style={{
                        color: e.event_type === 'column_added' ? '#10B981' :
                          e.event_type === 'column_dropped' ? '#ef4444' :
                          e.event_type === 'type_changed' ? '#f59e0b' : '#94a3b8'
                      }}>
                        {e.event_type.replace('_', ' ')}
                      </span>
                      <span className="text-xs font-mono text-white">{e.table_name}.{e.column_name}</span>
                      {e.resolved && <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: 'rgba(34,197,94,0.1)', color: '#10B981' }}>Resolved</span>}
                    </div>
                    {(e.old_value || e.new_value) && (
                      <p className="text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>
                        {e.old_value && <span className="line-through mr-2" style={{ color: '#EF4444' }}>{e.old_value}</span>}
                        {e.new_value && <span style={{ color: '#4ADE80' }}>{e.new_value}</span>}
                      </p>
                    )}
                    <p className="text-[10px] mt-1" style={{ color: 'hsl(var(--muted-foreground))' }}>
                      {new Date(e.detected_at).toLocaleString()}
                    </p>
                  </div>
                  {!e.resolved && (
                    <button className="text-xs px-3 py-1.5 rounded-lg hover:bg-white/5 transition-colors"
                      style={{ border: '1px solid hsl(var(--border))', color: 'hsl(var(--muted-foreground))' }}>
                      Resolve
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Tab: PII Scanner */}
      {tab === 'pii' && (
        <div className="space-y-4">
          {/* Summary row */}
          <div className="grid grid-cols-4 gap-3">
            {[
              { label: 'Total PII Columns', value: piiData?.total ?? '—', color: '#7C3AED' },
              { label: 'High Severity',     value: piiData?.high ?? '—',  color: '#ef4444' },
              { label: 'Medium Severity',   value: piiData?.medium ?? '—', color: '#f59e0b' },
              { label: 'Low Severity',      value: piiData?.low ?? '—',   color: '#10B981' },
            ].map(c => (
              <div key={c.label} className="glass rounded-xl p-4 text-center">
                <p className="text-2xl font-bold" style={{ color: c.color }}>{String(c.value)}</p>
                <p className="text-xs mt-1" style={{ color: 'hsl(var(--muted-foreground))' }}>{c.label}</p>
              </div>
            ))}
          </div>

          {piiLoading ? (
            <div className="space-y-2">{[1,2,3].map(i => <div key={i} className="h-20 rounded-xl animate-pulse" style={{ background: 'hsl(var(--muted))' }} />)}</div>
          ) : allPiiResults.length === 0 ? (
            <div className="rounded-2xl p-16 text-center" style={{ border: '2px dashed hsl(var(--border))' }}>
              <Scan size={36} className="mx-auto mb-3" style={{ color: 'hsl(var(--muted-foreground))' }} />
              <p className="text-sm text-white font-medium mb-1">No PII scan results yet</p>
              <p className="text-xs mb-4" style={{ color: 'hsl(var(--muted-foreground))' }}>
                Click &quot;Run PII Scan&quot; to scan all database columns for personally identifiable information.
              </p>
              <button onClick={runPiiScan} disabled={piiScanning}
                className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold text-white mx-auto hover:opacity-90"
                style={{ background: '#7C3AED' }}>
                <Scan size={14} className={piiScanning ? 'animate-spin' : ''} />
                {piiScanning ? 'Scanning…' : 'Run PII Scan'}
              </button>
            </div>
          ) : (
            <div className="space-y-4">
              {Object.entries(piiByTable).map(([tableName, cols]) => (
                <div key={tableName} className="glass rounded-xl overflow-hidden">
                  <div className="px-4 py-3 flex items-center justify-between"
                    style={{ background: 'hsl(var(--muted))', borderBottom: '1px solid hsl(var(--border))' }}>
                    <div className="flex items-center gap-2">
                      <Database size={14} style={{ color: '#7C3AED' }} />
                      <span className="font-mono text-sm text-white font-semibold">{tableName}</span>
                    </div>
                    <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: 'rgba(139,92,246,0.15)', color: '#7C3AED' }}>
                      {cols.filter(c => !c.suppressed).length} PII column{cols.length !== 1 ? 's' : ''}
                    </span>
                  </div>
                  <table className="w-full">
                    <thead>
                      <tr style={{ borderBottom: '1px solid hsl(var(--border))' }}>
                        {['Column', 'PII Type', 'Severity', 'Detection', 'Confidence', ''].map(h => (
                          <th key={h} className="text-left px-4 py-2 text-xs font-medium"
                            style={{ color: 'hsl(var(--muted-foreground))' }}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {cols.map(r => (
                        <tr key={r.id}
                          className="hover:bg-white/5 transition-colors"
                          style={{
                            borderBottom: '1px solid hsl(var(--border))',
                            opacity: r.suppressed ? 0.4 : 1,
                          }}>
                          <td className="px-4 py-3 font-mono text-sm text-white">{r.column_name}</td>
                          <td className="px-4 py-3">
                            <span className="text-xs font-medium" style={{ color: '#c084fc' }}>{r.pii_type}</span>
                          </td>
                          <td className="px-4 py-3">
                            <span className="text-xs px-2 py-0.5 rounded-full font-semibold" style={{
                              background: r.severity === 'high' ? 'rgba(239,68,68,0.15)'
                                : r.severity === 'medium' ? 'rgba(245,158,11,0.15)'
                                : 'rgba(34,197,94,0.15)',
                              color: r.severity === 'high' ? '#ef4444'
                                : r.severity === 'medium' ? '#f59e0b'
                                : '#10B981',
                            }}>
                              {r.severity.toUpperCase()}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span className="text-xs px-2 py-0.5 rounded-full"
                              style={{
                                background: r.detection_method === 'llm' ? 'rgba(59,130,246,0.15)' : 'rgba(148,163,184,0.1)',
                                color: r.detection_method === 'llm' ? '#38BDF8' : '#94a3b8',
                              }}>
                              {r.detection_method === 'llm' ? '🤖 LLM' : '⚡ Regex'}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-2">
                              <div className="w-16 h-1.5 rounded-full" style={{ background: 'hsl(var(--muted))' }}>
                                <div className="h-full rounded-full" style={{
                                  width: `${Math.round(r.confidence * 100)}%`,
                                  background: r.confidence > 0.8 ? '#10B981' : '#f59e0b',
                                }} />
                              </div>
                              <span className="text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>
                                {Math.round(r.confidence * 100)}%
                              </span>
                            </div>
                          </td>
                          <td className="px-4 py-3">
                            {!r.suppressed ? (
                              <button onClick={() => suppressPii(r.id)}
                                title="Suppress (false positive)"
                                className="p-1.5 rounded-lg hover:bg-white/5 transition-colors"
                                style={{ color: 'hsl(var(--muted-foreground))' }}>
                                <EyeOff size={13} />
                              </button>
                            ) : (
                              <span className="text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>Suppressed</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Modals */}
      {showAddRule && (
        <AddRuleModal
          tables={tables}
          onClose={() => setShowAddRule(false)}
          onSave={(data) => createRule.mutate(data)}
        />
      )}
      {selectedTable && (
        <TableDetailDrawer tableName={selectedTable} onClose={() => setSelectedTable(null)} />
      )}
    </div>
  )
}
