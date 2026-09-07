'use client'
import { useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import {
  Play, RefreshCw, CheckCircle2, XCircle, ChevronRight,
  Clock, Database, ArrowRight, Layers,
  TrendingUp, Activity, AlertTriangle,
} from 'lucide-react'
import { formatDistanceToNow, format } from 'date-fns'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'
import { MetricCard } from '@/components/ui/MetricCard'

import api from '@/lib/api'
import type { PipelineRun, LucideIcon } from '@/lib/types'

interface PipelineDetail {
  id: string | number
  name: string
  status?: string
  source_type?: string
  dest_type?: string
  schedule?: string
  dag_id?: string
  created_at?: string
  source_config?: string | Record<string, unknown>
  dest_config?: string | Record<string, unknown>
  runs?: PipelineRun[]
  stats?: {
    total_runs?: number
    success_rate?: number
    total_rows_synced?: number
    avg_duration_s?: number
    last_run_at?: string
  }
}

// ── Design tokens ──────────────────────────────────────────────────────────────
const T = {
  card: '#0F2540',
  border: '#1A3A5C',
  textPrimary: '#F1F5F9',
  textMuted: '#64748B',
  textLabel: '#4B6B8E',
  sky: '#0EA5E9',
}

const fetchPipeline = (id: string) =>
  api.get(`/api/pipelines/${id}`).then(r => r.data)

const triggerRun = (id: string) =>
  api.post(`/api/pipelines/${id}/trigger`).then(r => r.data)

// ── Status badge ───────────────────────────────────────────────────────────────
function RunStatus({ status }: { status: string }) {
  const map: Record<string, { label: string; color: string; bg: string; icon: LucideIcon }> = {
    success: { label: 'Success', color: '#4ADE80', bg: 'rgba(74,222,128,0.15)',   icon: CheckCircle2 },
    failed:  { label: 'Failed',  color: '#EF4444', bg: 'rgba(239,68,68,0.15)',    icon: XCircle      },
    running: { label: 'Running', color: '#60A5FA', bg: 'rgba(96,165,250,0.15)',   icon: RefreshCw    },
    skipped: { label: 'Skipped', color: '#9CA3AF', bg: 'rgba(156,163,175,0.15)',  icon: Clock        },
  }
  const s = map[status] || map['skipped']
  const Icon = s.icon
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium"
      style={{ color: s.color, background: s.bg }}>
      <Icon size={9} className={status === 'running' ? 'animate-spin' : ''} />
      {s.label}
    </span>
  )
}

// ── Run history chart (full width) ─────────────────────────────────────────────
function RunHistoryChart({ runs }: { runs: PipelineRun[] }) {
  const data = runs.slice(0, 20).reverse().map((r: PipelineRun, i: number) => ({
    idx: i + 1,
    records: r.records_loaded ?? 0,
    status: r.status,
    started: r.started_at ? format(new Date(r.started_at), 'MMM d, HH:mm') : `Run ${i + 1}`,
  }))

  return (
    <div className="card" style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 12, padding: 20 }}>
      <div className="flex items-center justify-between mb-4">
        <h2 style={{ fontSize: 14, fontWeight: 600, color: T.textPrimary }}>Records Loaded Over Time</h2>
        <span style={{ fontSize: 11, color: T.textLabel }}>Last {data.length} runs</span>
      </div>
      {data.length >= 2 ? (
        <div style={{ height: 220 }}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
              <defs>
                <linearGradient id="detail-grad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#0EA5E9" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#0EA5E9" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke={T.border} strokeDasharray="3 3" vertical={false} />
              <XAxis
                dataKey="started"
                tick={{ fontSize: 10, fill: T.textLabel }}
                axisLine={{ stroke: T.border }}
                tickLine={false}
                minTickGap={40}
              />
              <YAxis
                tick={{ fontSize: 10, fill: T.textLabel }}
                axisLine={false}
                tickLine={false}
                width={48}
                tickFormatter={(v: number | string) => Number(v) >= 1000 ? `${(Number(v) / 1000).toFixed(1)}K` : String(v)}
              />
              <Tooltip
                contentStyle={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 8, fontSize: 12 }}
                labelStyle={{ color: T.textMuted, fontSize: 11 }}
                formatter={(v: unknown) => [Number(v).toLocaleString(), 'records']}
              />
              <Area type="monotone" dataKey="records" stroke="#0EA5E9" strokeWidth={2}
                fill="url(#detail-grad)" dot={{ r: 2, fill: '#0EA5E9' }} activeDot={{ r: 4 }} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <div className="flex items-center justify-center" style={{ height: 160 }}>
          <p style={{ fontSize: 12, color: T.textMuted }}>Not enough run history to chart — trigger a few syncs first</p>
        </div>
      )}
    </div>
  )
}

// ── Run log table ──────────────────────────────────────────────────────────────
function RunsTable({ runs }: { runs: PipelineRun[] }) {
  if (!runs.length) {
    return (
      <div className="text-center py-12">
        <Activity size={32} className="mx-auto mb-3" style={{ color: T.textLabel }} />
        <p style={{ fontSize: 13, color: T.textMuted }}>No runs yet — trigger the first sync above</p>
      </div>
    )
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full data-table">
        <thead>
          <tr style={{ borderBottom: `1px solid ${T.border}` }}>
            {['Run ID', 'Started', 'Duration', 'Rows In', 'Records', 'Status', 'Errors'].map(h => (
              <th key={h} className="text-left"
                style={{
                  fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.08em',
                  color: T.textLabel, fontWeight: 600, padding: '10px 16px',
                }}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {runs.map((r: PipelineRun) => (
            <tr key={r.id || r.run_id}
              className="hover:bg-white/[0.03] transition-colors"
              style={{ borderBottom: `1px solid ${T.border}` }}>
              <td className="font-mono" style={{ padding: '12px 16px', fontSize: 11, color: T.textMuted }}>
                {String(r.run_id || r.id || '').slice(0, 12)}…
              </td>
              <td style={{ padding: '12px 16px', fontSize: 12, color: T.textPrimary, whiteSpace: 'nowrap' }}>
                {r.started_at
                  ? formatDistanceToNow(new Date(r.started_at), { addSuffix: true })
                  : '—'}
              </td>
              <td style={{ padding: '12px 16px', fontSize: 12, color: T.textMuted }}>
                {r.duration_seconds != null ? `${r.duration_seconds}s` : '—'}
              </td>
              <td style={{ padding: '12px 16px', fontSize: 12, color: T.textPrimary, fontVariantNumeric: 'tabular-nums' }}>
                {r.records_ingested?.toLocaleString() ?? '—'}
              </td>
              <td style={{ padding: '12px 16px', fontSize: 12, color: T.textPrimary, fontVariantNumeric: 'tabular-nums' }}>
                {r.records_loaded?.toLocaleString() ?? '—'}
              </td>
              <td style={{ padding: '12px 16px' }}>
                <RunStatus status={r.status} />
              </td>
              <td style={{ padding: '12px 16px', fontSize: 12, color: (r.records_failed ?? 0) > 0 ? '#EF4444' : T.textMuted }}>
                {r.records_failed ?? 0}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ── Pipeline config card ───────────────────────────────────────────────────────
type FieldMapping = { src: string; dst: string; type: string }
type RowFilter = { field: string; op: string; value: string }

function ConfigCard({ pipeline }: { pipeline: PipelineDetail }) {
  const srcConfig: Record<string, unknown> = typeof pipeline.source_config === 'string'
    ? JSON.parse(pipeline.source_config || '{}')
    : (pipeline.source_config || {})
  const dstConfig: Record<string, unknown> = typeof pipeline.dest_config === 'string'
    ? JSON.parse(pipeline.dest_config || '{}')
    : (pipeline.dest_config || {})

  const mappings: FieldMapping[] = (srcConfig.field_mappings as FieldMapping[]) || []
  const filters: RowFilter[] = (srcConfig.filters as RowFilter[]) || []

  return (
    <div className="card" style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 12, padding: 20 }}>
      <h2 style={{ fontSize: 14, fontWeight: 600, color: T.textPrimary, marginBottom: 16 }}>Pipeline Configuration</h2>

      {/* Source → Destination flow */}
      <div className="grid grid-cols-[1fr_auto_1fr] gap-4 items-stretch mb-4">
        <div className="rounded-xl" style={{ border: `1px solid ${T.border}`, padding: 14 }}>
          <p className="flex items-center gap-1.5 mb-2" style={{ fontSize: 12, fontWeight: 600, color: T.textPrimary }}>
            <Database size={12} style={{ color: T.sky }} /> Source
          </p>
          <p className="font-mono" style={{ fontSize: 12, color: T.textMuted }}>{pipeline.source_type}</p>
          {!!srcConfig.table && (
            <p className="font-mono" style={{ fontSize: 12, color: T.textPrimary, marginTop: 4 }}>{srcConfig.table as string}</p>
          )}
          {!!srcConfig.query && (
            <p className="font-mono truncate" style={{ fontSize: 10, color: '#7DD3FC', marginTop: 4 }}>
              {(srcConfig.query as string).slice(0, 60)}…
            </p>
          )}
          <div style={{ marginTop: 8, paddingTop: 8, borderTop: `1px solid ${T.border}` }}>
            <p style={{ fontSize: 10, color: T.textMuted }}>
              Sync: <span style={{ color: T.textPrimary }}>{(srcConfig.sync_mode as string) || 'full_refresh'}</span>
            </p>
            {!!srcConfig.cursor_field && (
              <p style={{ fontSize: 10, color: T.textMuted }}>
                Cursor: <span style={{ color: T.textPrimary }}>{srcConfig.cursor_field as string}</span>
              </p>
            )}
          </div>
        </div>

        <div className="flex flex-col items-center justify-center gap-1">
          <ArrowRight size={18} style={{ color: T.sky }} />
          <span style={{ fontSize: 9, color: T.textLabel }}>ETL</span>
        </div>

        <div className="rounded-xl" style={{ border: `1px solid ${T.border}`, padding: 14 }}>
          <p className="flex items-center gap-1.5 mb-2" style={{ fontSize: 12, fontWeight: 600, color: T.textPrimary }}>
            <Layers size={12} style={{ color: '#34D399' }} /> Destination
          </p>
          <p className="font-mono" style={{ fontSize: 12, color: T.textMuted }}>{pipeline.dest_type}</p>
          {!!dstConfig.table && (
            <p className="font-mono" style={{ fontSize: 12, color: T.textPrimary, marginTop: 4 }}>{dstConfig.table as string}</p>
          )}
        </div>
      </div>

      {/* Mappings */}
      {mappings.length > 0 && (
        <div className="rounded-xl mb-4" style={{ border: `1px solid ${T.border}`, padding: 14 }}>
          <p style={{ fontSize: 12, fontWeight: 600, color: T.textPrimary, marginBottom: 10 }}>Field Mappings</p>
          <div className="space-y-1.5">
            {mappings.map((m: FieldMapping, i: number) => (
              <div key={i} className="flex items-center gap-3 font-mono" style={{ fontSize: 12 }}>
                <span style={{ color: '#7DD3FC' }}>{m.src}</span>
                <ArrowRight size={10} style={{ color: T.textLabel }} />
                <span style={{ color: '#6EE7B7' }}>{m.dst}</span>
                <span style={{ color: T.textLabel, fontSize: 10 }}>:{m.type}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Filters */}
      {filters.length > 0 && (
        <div className="rounded-xl mb-4" style={{ border: `1px solid ${T.border}`, padding: 14 }}>
          <p style={{ fontSize: 12, fontWeight: 600, color: T.textPrimary, marginBottom: 10 }}>Active Filters</p>
          <div className="space-y-1.5">
            {filters.map((f: RowFilter, i: number) => (
              <div key={i} className="flex items-center gap-2 font-mono" style={{ fontSize: 12 }}>
                <span style={{ color: '#FCD34D' }}>{f.field}</span>
                <span style={{ color: T.textLabel }}>{f.op}</span>
                <span style={{ color: T.textPrimary }}>&apos;{f.value}&apos;</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Meta row */}
      <div className="flex flex-wrap gap-x-6 gap-y-2" style={{ fontSize: 12, color: T.textMuted, paddingTop: 4 }}>
        <span>Source Type: <span className="font-mono" style={{ color: T.textPrimary }}>{pipeline.source_type}</span></span>
        <span>Schedule: <span style={{ color: T.textPrimary }}>{pipeline.schedule || 'Manual only'}</span></span>
        <span>DAG ID: <span className="font-mono" style={{ color: T.textPrimary }}>{pipeline.dag_id}</span></span>
        {pipeline.created_at && (
          <span>Created: <span style={{ color: T.textPrimary }}>{format(new Date(pipeline.created_at), 'MMM d, yyyy')}</span></span>
        )}
      </div>
    </div>
  )
}

// ── Main Page ──────────────────────────────────────────────────────────────────
export default function PipelineDetailPage() {
  const params = useParams()
  const router = useRouter()
  const qc = useQueryClient()
  const id = params?.id as string
  const [triggering, setTriggering] = useState(false)
  const [triggerMsg, setTriggerMsg] = useState('')

  const { data: pipeline, isLoading, error } = useQuery({
    queryKey: ['pipeline', id],
    queryFn: () => fetchPipeline(id),
    refetchInterval: 15_000,
    enabled: !!id,
  })

  const handleTrigger = async () => {
    setTriggering(true)
    setTriggerMsg('')
    try {
      const res = await triggerRun(id)
      setTriggerMsg(res.simulated ? 'Run simulated ✓' : 'Triggered ✓')
      qc.invalidateQueries({ queryKey: ['pipeline', id] })
    } catch {
      setTriggerMsg('Trigger failed')
    } finally {
      setTriggering(false)
    }
  }

  if (isLoading) return (
    <div className="flex items-center justify-center h-64">
      <RefreshCw size={24} className="animate-spin" style={{ color: T.sky }} />
    </div>
  )

  if (error || !pipeline) return (
    <div className="flex flex-col items-center justify-center h-64 gap-3">
      <AlertTriangle size={32} style={{ color: '#EF4444' }} />
      <p style={{ fontSize: 13, color: T.textPrimary }}>Pipeline not found</p>
      <button onClick={() => router.push('/pipelines')} className="hover:underline" style={{ fontSize: 12, color: '#38BDF8' }}>
        ← Back to Pipelines
      </button>
    </div>
  )

  const runs: PipelineRun[] = pipeline.runs || []
  const stats = pipeline.stats || {}
  const scheduleLabel = pipeline.schedule ? pipeline.schedule : 'Manual only'

  const avgRecords = stats.total_rows_synced != null && (stats.total_runs ?? runs.length) > 0
    ? Math.round(stats.total_rows_synced / Math.max(stats.total_runs ?? runs.length, 1))
    : runs.length > 0
      ? Math.round(runs.reduce((a, r) => a + (r.records_loaded || 0), 0) / runs.length)
      : null

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: 'easeOut' }}
      style={{ padding: 24 }}
      className="min-h-full space-y-6">

      {/* ── Breadcrumb + header ──────────────────────────────────────────── */}
      <div>
        <div className="flex items-center gap-1.5 mb-2" style={{ fontSize: 12 }}>
          <button
            onClick={() => router.push('/pipelines')}
            className="hover:underline transition-colors"
            style={{ color: T.textLabel }}>
            Pipelines
          </button>
          <ChevronRight size={12} style={{ color: T.textLabel }} />
          <span style={{ color: T.textMuted }}>{pipeline.name}</span>
        </div>

        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-3 flex-wrap">
              <h1 style={{ fontSize: 24, fontWeight: 700, color: T.textPrimary, letterSpacing: '-0.02em' }}>
                {pipeline.name}
              </h1>
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium"
                style={{
                  background: pipeline.status === 'active' ? 'rgba(74,222,128,0.15)' : 'rgba(156,163,175,0.15)',
                  color: pipeline.status === 'active' ? '#4ADE80' : '#9CA3AF',
                }}>
                <span className={pipeline.status === 'active' ? 'animate-pulse' : ''}
                  style={{ width: 6, height: 6, borderRadius: '50%', background: pipeline.status === 'active' ? '#4ADE80' : '#9CA3AF', display: 'inline-block' }} />
                {pipeline.status}
              </span>
            </div>
            <div className="flex items-center gap-3 mt-1.5" style={{ fontSize: 12, color: T.textMuted }}>
              <span className="flex items-center gap-1">
                <Database size={10} /> {pipeline.source_type}
              </span>
              <ArrowRight size={10} />
              <span className="flex items-center gap-1">
                <Layers size={10} /> {pipeline.dest_type}
              </span>
              <span>·</span>
              <span className="flex items-center gap-1">
                <Clock size={10} /> {scheduleLabel}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-3 flex-shrink-0">
            {triggerMsg && (
              <span style={{ fontSize: 12, color: '#34D399' }}>{triggerMsg}</span>
            )}
            <button
              onClick={handleTrigger}
              disabled={triggering}
              className="btn-primary flex items-center gap-2 transition-all hover:opacity-90 active:scale-[0.98] disabled:opacity-60"
              style={{ background: T.sky, color: '#fff', borderRadius: 8, padding: '8px 16px', fontSize: 13, fontWeight: 600 }}>
              {triggering
                ? <><RefreshCw size={14} className="animate-spin" /> Running…</>
                : <><Play size={14} /> Run Now</>}
            </button>
          </div>
        </div>
      </div>

      {/* ── Stat cards ───────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Total Runs"
          value={stats.total_runs ?? runs.length}
          subtitle="all-time syncs"
          icon={Activity} color="blue" />
        <MetricCard
          title="Success Rate"
          value={stats.success_rate != null ? `${stats.success_rate}%` : '—'}
          subtitle="of completed runs"
          icon={CheckCircle2} color="green" />
        <MetricCard
          title="Avg Records"
          value={avgRecords != null ? avgRecords.toLocaleString() : '—'}
          subtitle="per run"
          icon={TrendingUp} color="purple" />
        <MetricCard
          title="Avg Duration"
          value={stats.avg_duration_s != null ? `${stats.avg_duration_s}s` : '—'}
          subtitle="per run"
          icon={Clock} color="amber" />
      </div>

      {/* ── Run history chart ────────────────────────────────────────────── */}
      <RunHistoryChart runs={runs} />

      {/* ── Run log ──────────────────────────────────────────────────────── */}
      <div className="card overflow-hidden" style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 12 }}>
        <div className="flex items-center justify-between" style={{ padding: '16px 20px', borderBottom: `1px solid ${T.border}` }}>
          <h2 style={{ fontSize: 14, fontWeight: 600, color: T.textPrimary }}>Run Log</h2>
          <span style={{ fontSize: 11, color: T.textLabel }}>{runs.length} runs</span>
        </div>
        <RunsTable runs={runs} />
      </div>

      {/* ── Pipeline config ──────────────────────────────────────────────── */}
      <ConfigCard pipeline={pipeline} />

      {/* Meta footer */}
      <div className="flex flex-wrap gap-x-6 gap-y-1 rounded-xl"
        style={{ background: T.card, border: `1px solid ${T.border}`, padding: '12px 16px', fontSize: 12, color: T.textMuted }}>
        <span>ID: <span className="font-mono" style={{ color: T.textPrimary }}>{pipeline.id}</span></span>
        {stats.last_run_at && (
          <span>Last run: <span style={{ color: T.textPrimary }}>{formatDistanceToNow(new Date(stats.last_run_at), { addSuffix: true })}</span></span>
        )}
        {stats.total_rows_synced != null && (
          <span>Total rows synced: <span style={{ color: T.textPrimary }}>{Number(stats.total_rows_synced).toLocaleString()}</span></span>
        )}
      </div>
    </motion.div>
  )
}
