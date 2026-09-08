'use client'
import { useState, Fragment } from 'react'
import { useRouter } from 'next/navigation'
import { motion } from 'framer-motion'
import {
  Play, FileText, Database, RefreshCw, Plus, ChevronRight,
  ChevronDown, Trash2, Activity, XCircle, Layers, GitBranch,
} from 'lucide-react'
import { EmptyState } from '@/components/ui/EmptyState'
import { DEMO_PIPELINES } from '@/lib/demo'
import { SkeletonTable } from '@/components/ui/Skeleton'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api, { pipelineApi } from '@/lib/api'
import type { PipelineRun, LucideIcon } from '@/lib/types'
import { useToast } from '@/components/ui/Toaster'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { formatDistanceToNow } from 'date-fns'

// ── Design tokens (CSS variables for theme support) ──────────────────────────
const T = {
  card: 'var(--card-bg)',
  border: 'var(--border)',
  textPrimary: 'var(--text-primary)',
  textMuted: 'var(--text-muted)',
  textLabel: 'var(--text-label)',
  sky: 'var(--accent)',
  input: 'var(--input-bg)',
}

const FREQ_OPTIONS = [
  { label: 'Manual', cron: '' },
  { label: 'Every 30 min', cron: '*/30 * * * *' },
  { label: 'Every 1 hour', cron: '0 * * * *' },
  { label: 'Every 3 hours', cron: '0 */3 * * *' },
  { label: 'Every 6 hours', cron: '0 */6 * * *' },
  { label: 'Every 12 hours', cron: '0 */12 * * *' },
  { label: 'Every 24 hours', cron: '0 0 * * *' },
]
const freqLabel = (cron?: string) => (FREQ_OPTIONS.find(o => o.cron === (cron || ''))?.label) || 'Custom'

interface Pipeline {
  id: string
  name: string
  dag_id: string
  source_type: string
  status: string
  schedule?: string
  last_run?: PipelineRun | null
}

/** Validate a 5-part cron expression (basic check) */
function isValidCron(expr: string): boolean {
  if (!expr.trim()) return true  // empty = manual
  const parts = expr.trim().split(/\s+/)
  return parts.length === 5
}

const thStyle: React.CSSProperties = {
  fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.08em',
  color: T.textLabel, fontWeight: 600, padding: '10px 16px', textAlign: 'left',
}
const tdStyle: React.CSSProperties = { padding: '12px 16px', fontSize: 13 }

/** One pipeline as an expandable table row — preserves every mutation from the old card. */
function PipelineRow({ pipeline }: { pipeline: Pipeline }) {
  const [showLogs, setShowLogs] = useState(false)
  const [expanded, setExpanded] = useState(false)
  const [customCron, setCustomCron] = useState('')
  const [showCustom, setShowCustom] = useState(false)
  const router = useRouter()
  const toast = useToast()
  const qc = useQueryClient()

  const setFrequency = useMutation({
    mutationFn: (cron: string) =>
      api.put(`/api/pipelines/${pipeline.id}/schedule`, { schedule: cron }).then(r => r.data),
    onSuccess: (d) => { toast(`Ingestion frequency: ${d.message || 'updated'}`, 'success'); qc.invalidateQueries({ queryKey: ['pipelines'] }) },
    onError: () => toast('Failed to update frequency', 'error'),
  })

  const { data: runsData, refetch: refetchRuns } = useQuery({
    queryKey: ['pipeline-runs', pipeline.id],
    queryFn: () => pipelineApi.getRuns(pipeline.id).then(r => r.data),
    enabled: showLogs || expanded,
  })

  const trigger = useMutation({
    mutationFn: () => pipelineApi.trigger(pipeline.id),
    onSuccess: (res) => {
      const d = res.data
      if (d?.simulated) toast(`Pipeline run simulated — Airflow not reachable`, 'info')
      else toast(`Pipeline "${pipeline.name}" triggered successfully`, 'success')
      refetchRuns()
    },
    onError: () => toast(`Failed to trigger "${pipeline.name}"`, 'error'),
  })

  const remove = useMutation({
    mutationFn: () => pipelineApi.remove(pipeline.id),
    onSuccess: () => {
      toast(`Pipeline "${pipeline.name}" deleted`, 'success')
      qc.invalidateQueries({ queryKey: ['pipelines'] })
    },
    onError: () => toast(`Failed to delete "${pipeline.name}"`, 'error'),
  })

  const handleDelete = () => {
    if (window.confirm(`Delete pipeline "${pipeline.name}"? This removes the pipeline and its run history. The destination table is NOT touched.`)) {
      remove.mutate()
    }
  }

  const runs = runsData?.runs || runsData?.recent_runs || []
  const latest = pipeline.last_run || runs[0]
  const chartData = (runs.length ? runs : (latest ? [latest] : []))
    .slice(0, 10).reverse().map((r: PipelineRun, i: number) => ({
      name: i,
      records: r.records_loaded ?? 0,
    }))

  const health = latest?.status === 'success' ? 'healthy' : latest?.status === 'failed' ? 'failed' : 'healthy'

  return (
    <>
      {/* Main row */}
      <tr
        onClick={() => setExpanded(e => !e)}
        className="cursor-pointer transition-colors hover:bg-white/[0.03]"
        style={{ borderBottom: expanded ? 'none' : `1px solid ${T.border}` }}>
        <td style={tdStyle}>
          <div className="flex items-center gap-2.5">
            {expanded
              ? <ChevronDown size={14} style={{ color: T.textLabel }} className="flex-shrink-0" />
              : <ChevronRight size={14} style={{ color: T.textLabel }} className="flex-shrink-0" />}
            <div className="flex items-center justify-center flex-shrink-0"
              style={{ width: 28, height: 28, borderRadius: 8, background: 'rgba(14,165,233,0.12)' }}>
              <Database size={13} style={{ color: T.sky }} />
            </div>
            <span style={{ fontSize: 14, fontWeight: 700, color: T.textPrimary }}>{pipeline.name}</span>
          </div>
        </td>
        <td style={tdStyle}>
          <span style={{
            fontSize: 11, fontWeight: 500, color: '#38BDF8',
            background: 'rgba(14,165,233,0.10)', borderRadius: 999, padding: '2px 10px',
          }}>
            {pipeline.source_type}
          </span>
        </td>
        {/* Schedule — inline dropdown, click doesn't toggle the row */}
        <td style={tdStyle} onClick={e => e.stopPropagation()}>
          <div className="flex flex-col gap-1.5">
            <select
              value={FREQ_OPTIONS.some(o => o.cron === (pipeline.schedule || '')) ? (pipeline.schedule || '') : '__custom__'}
              onChange={e => {
                if (e.target.value === '__custom__') {
                  setShowCustom(true)
                  setCustomCron(
                    FREQ_OPTIONS.some(o => o.cron === (pipeline.schedule || '')) ? '' : (pipeline.schedule || '')
                  )
                } else {
                  setShowCustom(false)
                  setFrequency.mutate(e.target.value)
                }
              }}
              disabled={setFrequency.isPending}
              title={`Current: ${freqLabel(pipeline.schedule)}${pipeline.schedule ? ` (${pipeline.schedule})` : ''}`}
              className="cursor-pointer focus:ring-1 focus:ring-sky-500"
              style={{
                fontSize: 12, padding: '4px 8px', borderRadius: 8, outline: 'none',
                background: T.input, border: `1px solid ${T.border}`, color: T.textPrimary,
              }}>
              {FREQ_OPTIONS.map(o => <option key={o.cron} value={o.cron}>{o.label}</option>)}
              <option value="__custom__">Custom…</option>
            </select>
            {showCustom && (
              <div className="flex items-center gap-1.5">
                <input
                  type="text"
                  value={customCron}
                  onChange={e => setCustomCron(e.target.value)}
                  placeholder="0 */4 * * *"
                  className="focus:ring-1 focus:ring-sky-500"
                  style={{
                    width: 110, fontSize: 11, padding: '3px 8px', borderRadius: 6, outline: 'none',
                    background: T.input, border: `1px solid ${T.border}`, color: T.textPrimary, fontFamily: 'monospace',
                  }}
                />
                <button
                  onClick={() => {
                    if (!isValidCron(customCron)) { toast('Invalid cron — must have 5 parts (e.g. 0 */4 * * *)', 'error'); return }
                    setFrequency.mutate(customCron)
                    setShowCustom(false)
                  }}
                  disabled={setFrequency.isPending || !customCron.trim()}
                  className="disabled:opacity-40"
                  style={{
                    fontSize: 11, fontWeight: 500, padding: '3px 8px', borderRadius: 6,
                    background: 'rgba(14,165,233,0.15)', color: '#38BDF8',
                  }}>
                  Set
                </button>
                <button
                  onClick={() => setShowCustom(false)}
                  style={{ fontSize: 11, padding: '3px 6px', color: T.textMuted }}>
                  ✕
                </button>
              </div>
            )}
          </div>
        </td>
        <td style={{ ...tdStyle, fontSize: 12, color: T.textMuted, whiteSpace: 'nowrap' }}>
          {latest?.started_at ? formatDistanceToNow(new Date(latest.started_at), { addSuffix: true }) : '—'}
        </td>
        <td style={{ ...tdStyle, color: T.textPrimary, fontVariantNumeric: 'tabular-nums' }}>
          {latest?.records_loaded != null ? latest.records_loaded.toLocaleString() : '—'}
        </td>
        <td style={tdStyle}>
          <StatusBadge status={health} />
        </td>
        <td style={{ ...tdStyle, textAlign: 'right', whiteSpace: 'nowrap' }} onClick={e => e.stopPropagation()}>
          <button
            onClick={() => trigger.mutate()}
            disabled={trigger.isPending}
            title="Run now"
            className="inline-flex items-center gap-1.5 mr-1.5 transition-all hover:bg-sky-500/10 active:scale-95 disabled:opacity-50"
            style={{
              fontSize: 12, fontWeight: 500, color: T.sky,
              border: '1px solid rgba(14,165,233,0.3)', borderRadius: 8, padding: '4px 10px',
            }}>
            {trigger.isPending ? <RefreshCw size={11} className="animate-spin" /> : <Play size={11} />}
            Run
          </button>
          <button
            onClick={() => setShowLogs(true)}
            title="Run history"
            className="p-1.5 mr-0.5 rounded-lg transition-colors hover:bg-white/10"
            style={{ color: T.textMuted }}>
            <FileText size={14} />
          </button>
          <button
            onClick={() => router.push('/pipelines/' + pipeline.id)}
            title="Details"
            className="p-1.5 mr-0.5 rounded-lg transition-colors hover:bg-white/10"
            style={{ color: T.textMuted }}>
            <ChevronRight size={14} />
          </button>
          <button
            onClick={handleDelete}
            disabled={remove.isPending}
            title="Delete pipeline"
            className="p-1.5 rounded-lg transition-colors hover:bg-red-500/10 disabled:opacity-50"
            style={{ color: '#EF4444' }}>
            {remove.isPending
              ? <RefreshCw size={14} className="animate-spin" />
              : <Trash2 size={14} className="opacity-60 hover:opacity-100" />}
          </button>
        </td>
      </tr>

      {/* Expanded row — run history trend + latest run stats */}
      {expanded && (
        <tr style={{ borderBottom: `1px solid ${T.border}` }}>
          <td colSpan={7} style={{ padding: 0 }}>
            <div style={{ background: 'rgba(8,15,28,0.5)', padding: '16px 24px' }}>
              <div className="grid grid-cols-3 gap-6 items-start">
                {/* Trend */}
                <div className="col-span-2">
                  <p className="section-header mb-2" style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.08em', color: T.textLabel, fontWeight: 600 }}>
                    Records loaded — last {chartData.length} runs
                  </p>
                  <div style={{ height: 110 }}>
                    {chartData.length >= 2 ? (
                      <div role="img" aria-label={`Area chart showing records loaded trend for pipeline ${pipeline.name}`}>
                      <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={chartData} margin={{ top: 4, right: 4, bottom: 0, left: 4 }}>
                          <defs>
                            <linearGradient id={`grad-${pipeline.id}`} x1="0" y1="0" x2="0" y2="1">
                              <stop offset="5%" stopColor="#0EA5E9" stopOpacity={0.3} />
                              <stop offset="95%" stopColor="#0EA5E9" stopOpacity={0} />
                            </linearGradient>
                          </defs>
                          <XAxis dataKey="name" hide />
                          <YAxis hide />
                          <Tooltip
                            contentStyle={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 8, fontSize: 12 }}
                            labelStyle={{ display: 'none' }}
                            formatter={(v: unknown) => [Number(v).toLocaleString(), 'records']}
                          />
                          <Area type="monotone" dataKey="records" stroke="#0EA5E9" strokeWidth={1.5}
                            fill={`url(#grad-${pipeline.id})`} dot={false} />
                        </AreaChart>
                      </ResponsiveContainer>
                      </div>
                    ) : (
                      <div className="h-full flex items-center justify-center" style={{ fontSize: 12, color: T.textMuted }}>
                        Not enough run history for a trend
                      </div>
                    )}
                  </div>
                </div>
                {/* Latest run stats */}
                <div>
                  <p className="section-header mb-2" style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.08em', color: T.textLabel, fontWeight: 600 }}>
                    Latest run
                  </p>
                  <div className="grid grid-cols-2 gap-2">
                    {[
                      { label: 'Ingested', value: latest?.records_ingested ?? '—' },
                      { label: 'Loaded',   value: latest?.records_loaded ?? '—' },
                      { label: 'Failed',   value: latest?.records_failed ?? 0 },
                      { label: 'Duration', value: latest?.duration_seconds != null ? `${latest.duration_seconds}s` : '—' },
                    ].map(s => (
                      <div key={s.label} className="rounded-lg text-center"
                        style={{ background: T.card, border: `1px solid ${T.border}`, padding: '8px 6px' }}>
                        <p style={{ fontSize: 14, fontWeight: 700, color: T.textPrimary }}>
                          {s.value?.toLocaleString?.() ?? s.value}
                        </p>
                        <p style={{ fontSize: 10, color: T.textLabel, textTransform: 'uppercase', letterSpacing: '0.06em' }}>{s.label}</p>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </td>
        </tr>
      )}

      {/* Logs Dialog */}
      <Dialog open={showLogs} onOpenChange={setShowLogs}>
        <DialogContent className="max-w-2xl" style={{ background: T.card, border: `1px solid ${T.border}` }}>
          <DialogHeader>
            <DialogTitle style={{ color: T.textPrimary }}>Run History — {pipeline.name}</DialogTitle>
          </DialogHeader>
          <div className="overflow-auto max-h-96">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ borderBottom: `1px solid ${T.border}` }}>
                  {['Status', 'Ingested', 'Loaded', 'Failed', 'Duration', 'Started'].map(h => (
                    <th key={h} className="text-left py-2 px-3"
                      style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.08em', color: T.textLabel, fontWeight: 600 }}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {runs.slice(0, 20).map((r: PipelineRun, i: number) => (
                  <tr key={i} className="hover:bg-white/5" style={{ borderBottom: `1px solid ${T.border}` }}>
                    <td className="py-2 px-3"><StatusBadge status={r.status === 'success' ? 'healthy' : r.status || 'pending'} /></td>
                    <td className="py-2 px-3" style={{ color: T.textPrimary }}>{(r.records_ingested || 0).toLocaleString()}</td>
                    <td className="py-2 px-3" style={{ color: T.textPrimary }}>{(r.records_loaded || 0).toLocaleString()}</td>
                    <td className="py-2 px-3" style={{ color: '#EF4444' }}>{r.records_failed || 0}</td>
                    <td className="py-2 px-3" style={{ color: T.textMuted }}>{r.duration_seconds ? `${r.duration_seconds}s` : '—'}</td>
                    <td className="py-2 px-3 text-xs" style={{ color: T.textMuted }}>
                      {r.started_at ? formatDistanceToNow(new Date(r.started_at), { addSuffix: true }) : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {runs.length === 0 && (
              <p className="text-center py-8" style={{ fontSize: 13, color: T.textMuted }}>No run history available</p>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}

// ── Mini summary stat ──────────────────────────────────────────────────────────
function MiniStat({ icon: Icon, label, value, color }: { icon: LucideIcon; label: string; value: string | number; color: string }) {
  return (
    <div className="flex items-center gap-3 card"
      style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 12, padding: '14px 18px' }}>
      <div className="flex items-center justify-center flex-shrink-0"
        style={{ width: 34, height: 34, borderRadius: 9, background: `${color}1f` }}>
        <Icon size={15} style={{ color }} />
      </div>
      <div>
        <p style={{ fontSize: 18, fontWeight: 700, color: T.textPrimary, lineHeight: '22px' }}>{value}</p>
        <p style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.08em', color: T.textLabel, fontWeight: 600 }}>{label}</p>
      </div>
    </div>
  )
}

export default function PipelinesPage() {
  const router = useRouter()
  const { data, isLoading } = useQuery({
    queryKey: ['pipelines'],
    queryFn: () => pipelineApi.getAll().then(r => r.data),
    refetchInterval: 30000,
  })
  // Fall back to demo pipelines when backend is unreachable
  const rawPipelines: Pipeline[] = data?.pipelines || (Array.isArray(data) ? data : [])
  const pipelines: Pipeline[] = rawPipelines.length > 0 ? rawPipelines : (!isLoading ? DEMO_PIPELINES as Pipeline[] : [])

  const runningNow = pipelines.filter(p => p.last_run?.status === 'running').length
  const failed24h = pipelines.filter(p => {
    const lr = p.last_run
    if (!lr || lr.status !== 'failed') return false
    if (!lr.started_at) return true
    return Date.now() - new Date(lr.started_at).getTime() < 24 * 60 * 60 * 1000
  }).length

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: 'easeOut' }}
      style={{ padding: 24 }}
      className="space-y-6">

      {/* ── Header ───────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 style={{ fontSize: 24, fontWeight: 700, color: T.textPrimary, letterSpacing: '-0.02em' }}>
            Pipelines
          </h1>
          <span style={{
            fontSize: 12, fontWeight: 600, color: '#38BDF8',
            background: 'rgba(14,165,233,0.12)', borderRadius: 999, padding: '2px 10px',
          }}>
            {pipelines.length}
          </span>
        </div>
        <button
          onClick={() => router.push('/pipelines/new')}
          className="btn-primary inline-flex items-center gap-2 transition-all hover:opacity-90 active:scale-[0.98]"
          style={{ background: T.sky, color: '#fff', borderRadius: 8, padding: '8px 16px', fontSize: 13, fontWeight: 600 }}>
          <Plus size={15} /> New Pipeline
        </button>
      </div>

      {/* ── Summary stats ────────────────────────────────────────────────── */}
      <div className="grid grid-cols-3 gap-4">
        <MiniStat icon={Layers}   label="Total Pipelines" value={pipelines.length} color="#0EA5E9" />
        <MiniStat icon={Activity} label="Running Now"     value={runningNow}       color="#10B981" />
        <MiniStat icon={XCircle}  label="Failed (24h)"    value={failed24h}        color={failed24h > 0 ? '#EF4444' : '#64748B'} />
      </div>

      {/* ── Table ────────────────────────────────────────────────────────── */}
      {isLoading ? (
        <SkeletonTable rows={4} cols={5} />
      ) : pipelines.length === 0 ? (
        <div className="rounded-xl" style={{ border: `1px solid ${T.border}` }}>
          <EmptyState
            icon={GitBranch}
            title="No pipelines yet"
            description="Create your first pipeline to start moving data from your sources to your destination."
            action={{ label: '+ New Pipeline', onClick: () => router.push('/pipelines/new') }}
          />
        </div>
      ) : (
        <div className="card overflow-hidden" style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 12 }}>
          <table className="w-full data-table">
            <thead>
              <tr style={{ borderBottom: `1px solid ${T.border}` }}>
                <th style={thStyle}>Name</th>
                <th style={thStyle}>Source</th>
                <th style={thStyle}>Schedule</th>
                <th style={thStyle}>Last Run</th>
                <th style={thStyle}>Records</th>
                <th style={thStyle}>Status</th>
                <th style={{ ...thStyle, textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {pipelines.map(p => (
                <Fragment key={p.id}>
                  <PipelineRow pipeline={p} />
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Legend footnote */}
      {pipelines.length > 0 && (
        <p style={{ fontSize: 11, color: T.textLabel }}>
          Click a row to expand run history · Schedule changes apply immediately
        </p>
      )}
    </motion.div>
  )
}
