'use client'
import { useState, useCallback, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { motion } from 'framer-motion'
import {
  Database, AlertTriangle, DollarSign, Play, Globe, FileSpreadsheet,
  FileText, Wifi, RefreshCw, CheckCircle2, Zap, Calendar,
  Brain, TrendingUp, Activity, Shield, ArrowUpRight,
} from 'lucide-react'
import { useIncidents, useSavings, usePipelines, useTriggerHealing, useOverviewStats, useHealingStatus } from '@/lib/queries'
import { mlApi } from '@/lib/api'
import type { Pipeline, Incident, LucideIcon } from '@/lib/types'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { SkeletonMetricCard, SkeletonList } from '@/components/ui/Skeleton'
import { EmptyState } from '@/components/ui/EmptyState'
import { formatDistanceToNow, format } from 'date-fns'
import { useToast } from '@/components/ui/Toaster'
import { useWebSocket, WSEvent } from '@/hooks/useWebSocket'
import { useQueryClient, useQuery } from '@tanstack/react-query'

// ── Design tokens ──────────────────────────────────────────────────────────────
const T = {
  card: 'var(--card-bg)',
  border: 'var(--border)',
  borderLight: 'var(--border-light)',
  textPrimary: 'var(--text-primary)',
  textMuted: 'var(--text-muted)',
  textLabel: 'var(--text-label)',
  sky: '#0EA5E9',
}

const sourceIcon: Record<string, LucideIcon> = {
  postgresql: Database,
  rest_api: Globe,
  google_sheets: FileSpreadsheet,
  csv: FileText,
}

function pipelineHealth(p: Pipeline): 'healthy' | 'failed' | 'warning' {
  const st = p.last_run?.status
  if (st === 'failed') return 'failed'
  if (st == null) return 'warning'
  if ((p.last_run?.records_loaded ?? 0) === 0 && st === 'success') return 'warning'
  return 'healthy'
}

const anomalyColor: Record<string, string> = {
  ZERO_LOAD: '#EF4444',
  ROW_COUNT_DROP: '#F59E0B',
  ML_ANOMALY: '#0EA5E9',
  NULL_SPIKE: '#7C3AED',
  CONSECUTIVE_FAILURES: '#EF4444',
  PIPELINE_DELAY: '#F59E0B',
}

const PIPELINE_DISPLAY: Record<string, string> = {
  pipeline_csv_to_snowflake: 'CSV Files → Snowflake',
  pipeline_postgresql_to_snowflake: 'PostgreSQL → Snowflake',
  pipeline_rest_api_to_snowflake: 'REST API → Snowflake',
  pipeline_google_sheets_to_snowflake: 'Sheets → Snowflake',
}

function displayPipeline(name: string | undefined): string {
  if (!name) return '—'
  return PIPELINE_DISPLAY[name] || name
}

function formatRecords(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return String(n)
}

// ── Metric Hero Card ───────────────────────────────────────────────────────────
function HeroCard({
  title, value, subtitle, icon: Icon, color, trend, delay = 0,
}: {
  title: string
  value: string | number
  subtitle: string
  icon: LucideIcon
  color: 'blue' | 'violet' | 'emerald' | 'amber' | 'red'
  trend?: { value: string; up: boolean }
  delay?: number
}) {
  const colors = {
    blue:    { accent: '#0EA5E9', bg: 'rgba(14,165,233,0.08)',   iconBg: 'rgba(14,165,233,0.12)'   },
    violet:  { accent: '#7C3AED', bg: 'rgba(124,58,237,0.06)',  iconBg: 'rgba(124,58,237,0.12)'  },
    emerald: { accent: '#10B981', bg: 'rgba(16,185,129,0.06)',  iconBg: 'rgba(16,185,129,0.12)'  },
    amber:   { accent: '#F59E0B', bg: 'rgba(245,158,11,0.06)',  iconBg: 'rgba(245,158,11,0.12)'  },
    red:     { accent: '#EF4444', bg: 'rgba(239,68,68,0.06)',   iconBg: 'rgba(239,68,68,0.12)'   },
  }
  const c = colors[color]
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay, ease: 'easeOut' }}
      className={`metric-hero metric-hero-${color}`}
      style={{ cursor: 'default' }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 16 }}>
        <div style={{
          width: 40, height: 40, borderRadius: 10,
          background: c.iconBg,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          border: `1px solid ${c.accent}22`,
        }}>
          <Icon size={18} style={{ color: c.accent }} />
        </div>
        {trend && (
          <span style={{
            fontSize: 11, fontWeight: 600,
            color: trend.up ? '#10B981' : '#EF4444',
            background: trend.up ? 'rgba(16,185,129,0.1)' : 'rgba(239,68,68,0.1)',
            padding: '3px 8px', borderRadius: 20,
            display: 'flex', alignItems: 'center', gap: 3,
          }}>
            <ArrowUpRight size={10} style={{ transform: trend.up ? 'none' : 'rotate(90deg)' }} />
            {trend.value}
          </span>
        )}
      </div>
      <div style={{ fontSize: 32, fontWeight: 800, color: T.textPrimary, lineHeight: 1, marginBottom: 6, fontVariantNumeric: 'tabular-nums', letterSpacing: '-0.02em' }}>
        {value}
      </div>
      <div style={{ fontSize: 12, fontWeight: 600, color: T.textLabel, letterSpacing: '0.01em', marginBottom: 2 }}>
        {title}
      </div>
      <div style={{ fontSize: 11.5, color: T.textMuted }}>{subtitle}</div>
    </motion.div>
  )
}

// ── Main Page ──────────────────────────────────────────────────────────────────
export default function OverviewPage() {
  const router = useRouter()
  const toast = useToast()
  const queryClient = useQueryClient()

  useEffect(() => {
    try {
      if (!localStorage.getItem('onboarding_complete')) {
        router.replace('/onboarding')
      }
    } catch { /* ignore */ }
  }, [router])

  const { data: incidents, isLoading: incLoading } = useIncidents()
  const { data: savings, isLoading: savLoading } = useSavings()
  const { data: pipelinesData, isLoading: healthLoading } = usePipelines()
  const { data: overviewStats } = useOverviewStats()
  const { data: healingStatus } = useHealingStatus()
  const { data: mlMetrics } = useQuery({
    queryKey: ['ml-metrics'],
    queryFn: () => mlApi.getMetrics().then(r => r.data),
    staleTime: 60_000,
  })
  const triggerHealing = useTriggerHealing()
  const [triggeringId, setTriggeringId] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)

  const handleWSEvent = useCallback((event: WSEvent) => {
    if (event.type === 'pipeline_status') {
      queryClient.invalidateQueries({ queryKey: ['pipelines'] })
      if (event.data.status === 'failed') {
        toast(`Pipeline alert: ${event.data.pipeline_id} — ${event.data.status}`, 'error')
      }
    }
    if (event.type === 'incident_update') {
      queryClient.invalidateQueries({ queryKey: ['incidents'] })
      if (event.data.status === 'pending_approval') {
        toast(`New incident needs approval — ${event.data.incident_id}`, 'info')
      }
    }
  }, [queryClient, toast])

  const { status: wsStatus } = useWebSocket({ onEvent: handleWSEvent })

  const incidentList = (incidents?.incidents || []).filter((i: Incident) => {
    const name = i.pipeline_name || ''
    return i.anomaly_type && !name.startsWith('ingest_') && !name.startsWith('kafka_') && name !== 'dbt_run'
  })
  const pending = incidentList.filter((i: Incident) => i.approval_status === 'pending').length
  const recentIncidents = incidentList.slice(0, 8)

  const healthList: Pipeline[] = pipelinesData?.pipelines || []
  const totalRecords = overviewStats?.total_records_loaded ?? null
  const healthyCount = healthList.filter(p => pipelineHealth(p) === 'healthy').length
  const successRate = overviewStats?.success_rate != null
    ? Math.round(overviewStats.success_rate)
    : healthList.length > 0 ? Math.round((healthyCount / healthList.length) * 100) : null
  const costSaved = savings?.total_saved_usd ?? savings?.total_dollar_saved ?? 0
  const lastHealed = incidentList.find((i: Incident) => i.approval_status === 'approved')

  const handleTrigger = (p: Pipeline) => {
    const dagId = p.dag_id ?? p.name ?? String(p.id)
    setTriggeringId(dagId)
    triggerHealing.mutate(dagId, {
      onSuccess: () => { toast(`Healing triggered for ${p.name}`, 'success'); setTriggeringId(null) },
      onError: () => { toast(`Failed to trigger healing for ${p.name}`, 'error'); setTriggeringId(null) },
    })
  }

  const handleHealIncident = (inc: Incident) => {
    const name = inc.pipeline_name ?? String(inc.id)
    setTriggeringId(`inc-${inc.id}`)
    triggerHealing.mutate(name, {
      onSuccess: () => { toast(`Healing triggered`, 'success'); setTriggeringId(null) },
      onError: () => { toast(`Failed to trigger healing`, 'error'); setTriggeringId(null) },
    })
  }

  const handleRefresh = () => {
    setRefreshing(true)
    Promise.all([
      queryClient.invalidateQueries({ queryKey: ['pipelines'] }),
      queryClient.invalidateQueries({ queryKey: ['incidents'] }),
      queryClient.invalidateQueries({ queryKey: ['savings'] }),
      queryClient.invalidateQueries({ queryKey: ['overview-stats'] }),
      queryClient.invalidateQueries({ queryKey: ['healing-status'] }),
    ]).finally(() => setTimeout(() => setRefreshing(false), 600))
  }

  const isLoading = savLoading || healthLoading

  return (
    <div style={{ padding: 24 }} className="space-y-6">

      {/* ── Page header ────────────────────────────────────────────────────── */}
      <motion.div
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}
      >
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 800, letterSpacing: '-0.03em', lineHeight: 1.2 }}>
            <span className="gradient-text">OrchestrAI</span>
            <span style={{ color: T.textPrimary }}> Overview</span>
          </h1>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4 }}>
            <Calendar size={11} style={{ color: T.textLabel }} />
            <span style={{ fontSize: 12, color: T.textLabel }}>
              {format(new Date(), 'EEEE, MMMM d, yyyy')}
            </span>
            <span style={{ color: T.border, fontSize: 12 }}>·</span>
            {wsStatus === 'connected' ? (
              <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11, color: '#10B981', fontWeight: 500 }}>
                <span className="status-dot pulse-green" style={{ background: '#10B981', width: 5, height: 5 }} />
                Live feed active
              </span>
            ) : wsStatus === 'connecting' ? (
              <span style={{ fontSize: 11, color: '#F59E0B', fontWeight: 500 }}>Connecting…</span>
            ) : null}
          </div>
        </div>
        <button
          onClick={handleRefresh}
          className="btn-ghost"
          style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12 }}
        >
          <RefreshCw size={12} className={refreshing ? 'animate-spin' : ''} />
          Refresh
        </button>
      </motion.div>

      {/* ── Hero metric cards ───────────────────────────────────────────────── */}
      {isLoading ? (
        <div className="metrics-grid">
          {[0,1,2,3,4].map(i => <SkeletonMetricCard key={i} />)}
        </div>
      ) : (
        <div className="metrics-grid" style={{ gridTemplateColumns: 'repeat(5, 1fr)' }}>
          <HeroCard
            title="Pipelines" icon={Database} color="blue" delay={0}
            value={healthList.length}
            subtitle={totalRecords !== null ? `${formatRecords(totalRecords)} records` : `${healthyCount} healthy`}
            trend={{ value: `${healthyCount}/${healthList.length}`, up: healthyCount === healthList.length }}
          />
          <HeroCard
            title="Active Incidents" icon={AlertTriangle} color={pending > 0 ? 'amber' : 'emerald'} delay={0.05}
            value={pending}
            subtitle={pending === 0 ? 'All systems clear' : 'need attention'}
          />
          <HeroCard
            title="Cost Saved" icon={DollarSign} color="emerald" delay={0.1}
            value={`$${Number(costSaved).toFixed(2)}`}
            subtitle="from query rewrites"
            trend={{ value: 'this week', up: true }}
          />
          <HeroCard
            title="Success Rate" icon={TrendingUp} color="violet" delay={0.15}
            value={successRate !== null ? `${successRate}%` : '—'}
            subtitle="pipeline runs healthy"
          />
          <HeroCard
            title="ML Models" icon={Brain} color="blue" delay={0.2}
            value={mlMetrics?.isolation_forest?.roc_auc != null
              ? mlMetrics.isolation_forest.roc_auc.toFixed(3)
              : '—'}
            subtitle="IsolationForest ROC-AUC"
            trend={{ value: 'healthy', up: true }}
          />
        </div>
      )}

      {/* ── Pipeline table + Incident feed ─────────────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: '3fr 2fr', gap: 16, alignItems: 'start' }}>

        {/* Pipeline Status */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.25 }}
          className="card overflow-hidden"
        >
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '14px 20px', borderBottom: `1px solid ${T.border}`,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Activity size={14} style={{ color: T.sky }} />
              <span style={{ fontSize: 13.5, fontWeight: 700, color: T.textPrimary }}>Pipeline Status</span>
              {healthList.length > 0 && (
                <span style={{
                  fontSize: 11, color: '#10B981', background: 'rgba(16,185,129,0.1)',
                  padding: '2px 7px', borderRadius: 20, fontWeight: 600,
                }}>
                  {healthyCount} healthy
                </span>
              )}
            </div>
            <button
              onClick={() => router.push('/pipelines/new')}
              className="btn-primary"
              style={{ fontSize: 11.5, padding: '5px 12px', display: 'flex', alignItems: 'center', gap: 5 }}
            >
              + New Pipeline
            </button>
          </div>

          {healthLoading ? (
            <div style={{ padding: 16 }}>
              <SkeletonList items={4} />
            </div>
          ) : healthList.length === 0 ? (
            <EmptyState
              icon={Database}
              title="No pipelines yet"
              description="Create your first pipeline to start ingesting data automatically."
              action={{ label: '+ Create Pipeline', onClick: () => router.push('/pipelines/new') }}
              size="md"
            />
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  {['Pipeline', 'Last Run', 'Records', 'Status', ''].map((h, i) => (
                    <th key={i}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {healthList.map((p: Pipeline, idx: number) => {
                  const Icon = sourceIcon[p.source_type] || Database
                  const lr = p.last_run
                  const health = pipelineHealth(p)
                  return (
                    <motion.tr
                      key={p.dag_id || p.id}
                      initial={{ opacity: 0, x: -8 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: idx * 0.04 }}
                      style={{ cursor: 'pointer', borderBottom: `1px solid ${T.borderLight}` }}
                      onClick={() => router.push('/pipelines/' + p.id)}
                      className="transition-colors"
                    >
                      <td style={{ padding: '12px 16px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                          <div style={{
                            width: 30, height: 30, borderRadius: 8,
                            background: 'rgba(14,165,233,0.1)',
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            flexShrink: 0,
                            border: '1px solid rgba(14,165,233,0.15)',
                          }}>
                            <Icon size={13} style={{ color: T.sky }} />
                          </div>
                          <div>
                            <div style={{ fontSize: 13.5, fontWeight: 600, color: T.textPrimary }}>{p.name}</div>
                            {p.source_type && (
                              <div style={{ fontSize: 11, color: T.textLabel, marginTop: 1 }}>{p.source_type}</div>
                            )}
                          </div>
                        </div>
                      </td>
                      <td style={{ fontSize: 12, color: T.textMuted, whiteSpace: 'nowrap' }}>
                        {lr?.started_at ? formatDistanceToNow(new Date(lr.started_at), { addSuffix: true }) : '—'}
                      </td>
                      <td style={{ fontSize: 12.5, color: T.textPrimary, fontVariantNumeric: 'tabular-nums', fontWeight: health === 'healthy' ? 600 : 400 }}>
                        {lr?.records_loaded != null ? formatRecords(lr.records_loaded!) : '—'}
                      </td>
                      <td><StatusBadge status={health} /></td>
                      <td style={{ textAlign: 'right' }}>
                        <button
                          onClick={(e) => { e.stopPropagation(); handleTrigger(p) }}
                          disabled={triggeringId === (p.dag_id ?? p.name)}
                          style={{
                            display: 'inline-flex', alignItems: 'center', gap: 5,
                            fontSize: 11.5, fontWeight: 500, color: T.sky,
                            border: '1px solid rgba(14,165,233,0.25)', borderRadius: 7, padding: '4px 10px',
                            background: 'transparent', cursor: 'pointer', transition: 'all 0.15s',
                          }}
                          onMouseOver={e => { (e.currentTarget as HTMLButtonElement).style.background = 'rgba(14,165,233,0.08)' }}
                          onMouseOut={e => { (e.currentTarget as HTMLButtonElement).style.background = 'transparent' }}
                        >
                          {triggeringId === (p.dag_id ?? p.name)
                            ? <RefreshCw size={10} className="animate-spin" />
                            : <Play size={10} />}
                          Run
                        </button>
                      </td>
                    </motion.tr>
                  )
                })}
              </tbody>
            </table>
          )}
        </motion.div>

        {/* Incident Feed */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.3 }}
          className="card overflow-hidden"
        >
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '14px 20px', borderBottom: `1px solid ${T.border}`,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Shield size={14} style={{ color: pending > 0 ? '#F59E0B' : '#10B981' }} />
              <span style={{ fontSize: 13.5, fontWeight: 700, color: T.textPrimary }}>Incidents</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              {pending > 0 && (
                <span style={{
                  fontSize: 11, fontWeight: 700, color: '#F59E0B',
                  background: 'rgba(245,158,11,0.12)', borderRadius: 20, padding: '2px 8px',
                  border: '1px solid rgba(245,158,11,0.2)',
                }}>
                  {pending} pending
                </span>
              )}
              <button
                onClick={() => router.push('/approvals')}
                style={{ fontSize: 11, color: T.sky, background: 'none', border: 'none', cursor: 'pointer', fontWeight: 500 }}
              >
                View all →
              </button>
            </div>
          </div>

          {incLoading ? (
            <div style={{ padding: 16 }}><SkeletonList items={4} /></div>
          ) : recentIncidents.length === 0 ? (
            <EmptyState
              icon={CheckCircle2}
              title="All systems healthy"
              description="The healing agent is monitoring all your pipelines in real-time."
              accent="emerald"
              size="md"
            />
          ) : (
            <div style={{ overflowY: 'auto', maxHeight: 480 }}>
              {recentIncidents.map((inc: Incident, idx: number) => {
                const type = (inc.anomaly_type || 'UNKNOWN').toUpperCase()
                const dot = anomalyColor[type] || '#94A3B8'
                const isPending = inc.approval_status === 'pending'
                return (
                  <motion.div
                    key={inc.id}
                    initial={{ opacity: 0, x: 8 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: idx * 0.04 }}
                    style={{
                      display: 'flex', alignItems: 'flex-start', gap: 12,
                      padding: '12px 20px',
                      borderBottom: `1px solid ${T.borderLight}`,
                      borderLeft: `3px solid ${isPending ? dot : 'transparent'}`,
                      transition: 'background 0.15s',
                      cursor: 'pointer',
                    }}
                    onClick={() => router.push('/approvals')}
                    onMouseOver={e => { (e.currentTarget as HTMLDivElement).style.background = 'rgba(255,255,255,0.025)' }}
                    onMouseOut={e => { (e.currentTarget as HTMLDivElement).style.background = 'transparent' }}
                  >
                    <div style={{
                      width: 7, height: 7, borderRadius: '50%',
                      background: dot, flexShrink: 0, marginTop: 4,
                    }} />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
                        <span style={{ fontSize: 11, fontWeight: 700, color: dot,
                          background: `${dot}18`, padding: '1px 6px', borderRadius: 4 }}>
                          {type.replace(/_/g, ' ')}
                        </span>
                        <span style={{ fontSize: 10.5, color: T.textLabel, textTransform: 'capitalize' }}>
                          {inc.approval_status || 'pending'}
                        </span>
                      </div>
                      <p style={{ fontSize: 12.5, color: T.textPrimary, fontWeight: 500, marginBottom: 2 }} className="truncate">
                        {displayPipeline(inc.pipeline_name)}
                      </p>
                      <p style={{ fontSize: 11, color: T.textMuted }}>
                        {inc.created_at ? formatDistanceToNow(new Date(inc.created_at), { addSuffix: true }) : 'recently'}
                      </p>
                    </div>
                    {isPending && (
                      <button
                        onClick={e => { e.stopPropagation(); handleHealIncident(inc) }}
                        disabled={triggeringId === `inc-${inc.id}`}
                        style={{
                          display: 'flex', alignItems: 'center', gap: 4,
                          fontSize: 11, fontWeight: 600, color: T.sky,
                          border: '1px solid rgba(14,165,233,0.25)', borderRadius: 6, padding: '3px 8px',
                          background: 'rgba(14,165,233,0.06)', cursor: 'pointer', flexShrink: 0,
                          transition: 'all 0.15s',
                        }}
                      >
                        {triggeringId === `inc-${inc.id}`
                          ? <RefreshCw size={9} className="animate-spin" />
                          : <Zap size={9} />}
                        Heal
                      </button>
                    )}
                  </motion.div>
                )
              })}
            </div>
          )}
        </motion.div>
      </div>

      {/* ── ML Models ──────────────────────────────────────────────────────── */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.35 }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
          <Brain size={15} style={{ color: T.sky }} />
          <h2 style={{ fontSize: 13.5, fontWeight: 700, color: T.textPrimary }}>ML Model Health</h2>
          <span style={{ fontSize: 11, color: T.textLabel }}>Anomaly detection &amp; classification</span>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          {/* IsolationForest */}
          <div className="card" style={{ padding: 20, position: 'relative', overflow: 'hidden' }}>
            <div style={{
              position: 'absolute', top: 0, left: 0, right: 0, height: 2,
              background: 'linear-gradient(90deg, #0EA5E9, #38BDF8)',
            }} />
            {((mlMetrics?.isolation_forest?.roc_auc ?? 0) > 0.8) && (
              <span style={{
                position: 'absolute', top: 16, right: 16,
                fontSize: 10.5, fontWeight: 700, color: '#10B981',
                background: 'rgba(16,185,129,0.1)', borderRadius: 20, padding: '2px 8px',
                border: '1px solid rgba(16,185,129,0.2)',
              }}>✓ Healthy</span>
            )}
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
              <div style={{ width: 6, height: 6, borderRadius: '50%', background: T.sky }} />
              <span style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.1em', color: T.textLabel, fontWeight: 700 }}>
                Anomaly Detector
              </span>
            </div>
            <p style={{ fontSize: 13, fontWeight: 700, color: T.textPrimary, marginBottom: 2 }}>IsolationForest</p>
            <p style={{ fontSize: 38, fontWeight: 800, color: T.sky, lineHeight: 1.1, marginBottom: 4, fontVariantNumeric: 'tabular-nums' }}>
              {mlMetrics?.isolation_forest?.roc_auc?.toFixed(3) ?? '—'}
            </p>
            <p style={{ fontSize: 11, color: T.textLabel, marginBottom: 14 }}>ROC-AUC Score</p>
            <div style={{ display: 'flex', gap: 20 }}>
              {[['F1', 'f1'], ['Precision', 'precision'], ['Recall', 'recall']].map(([label, key]) => (
                <div key={key}>
                  <div style={{ fontSize: 16, fontWeight: 700, color: T.textPrimary, fontVariantNumeric: 'tabular-nums' }}>
                    {mlMetrics?.isolation_forest?.[key]?.toFixed(3) ?? '—'}
                  </div>
                  <div style={{ fontSize: 10, color: T.textLabel, textTransform: 'uppercase', letterSpacing: '0.07em' }}>{label}</div>
                </div>
              ))}
            </div>
            <div style={{ marginTop: 16, paddingTop: 12, borderTop: `1px solid ${T.border}`, fontSize: 11, color: T.textMuted }}>
              Trained on <strong style={{ color: T.textPrimary }}>
                {mlMetrics?.isolation_forest?.n_samples?.toLocaleString() ?? '2,000'}
              </strong> samples
            </div>
          </div>

          {/* RandomForest */}
          <div className="card" style={{ padding: 20, position: 'relative', overflow: 'hidden' }}>
            <div style={{
              position: 'absolute', top: 0, left: 0, right: 0, height: 2,
              background: 'linear-gradient(90deg, #7C3AED, #A78BFA)',
            }} />
            {((mlMetrics?.random_forest?.weighted_f1 ?? 0) > 0.8) && (
              <span style={{
                position: 'absolute', top: 16, right: 16,
                fontSize: 10.5, fontWeight: 700, color: '#10B981',
                background: 'rgba(16,185,129,0.1)', borderRadius: 20, padding: '2px 8px',
                border: '1px solid rgba(16,185,129,0.2)',
              }}>✓ Healthy</span>
            )}
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
              <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#7C3AED' }} />
              <span style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.1em', color: T.textLabel, fontWeight: 700 }}>
                Anomaly Classifier
              </span>
            </div>
            <p style={{ fontSize: 13, fontWeight: 700, color: T.textPrimary, marginBottom: 2 }}>RandomForest</p>
            <p style={{ fontSize: 38, fontWeight: 800, color: '#7C3AED', lineHeight: 1.1, marginBottom: 4, fontVariantNumeric: 'tabular-nums' }}>
              {mlMetrics?.random_forest?.weighted_f1?.toFixed(3) ?? '—'}
            </p>
            <p style={{ fontSize: 11, color: T.textLabel, marginBottom: 14 }}>Weighted F1</p>
            <div style={{ display: 'flex', gap: 20, marginBottom: 14 }}>
              <div>
                <div style={{ fontSize: 16, fontWeight: 700, color: T.textPrimary }}>
                  {mlMetrics?.random_forest?.accuracy != null
                    ? `${(mlMetrics.random_forest.accuracy * 100).toFixed(1)}%` : '—'}
                </div>
                <div style={{ fontSize: 10, color: T.textLabel, textTransform: 'uppercase', letterSpacing: '0.07em' }}>Accuracy</div>
              </div>
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px 12px' }}>
              {(['ZERO_LOAD', 'ROW_COUNT_DROP', 'ML_ANOMALY', 'NULL_SPIKE', 'CONSECUTIVE_FAILURES', 'PIPELINE_DELAY'] as string[]).map((cls: string) => (
                <span key={cls} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11, color: T.textMuted }}>
                  <span style={{ width: 5, height: 5, borderRadius: '50%', background: anomalyColor[cls] || '#94A3B8', flexShrink: 0, display: 'inline-block' }} />
                  {cls.replace(/_/g, ' ')}
                </span>
              ))}
            </div>
            <div style={{ marginTop: 16, paddingTop: 12, borderTop: `1px solid ${T.border}`, fontSize: 11, color: T.textMuted }}>
              Trained on <strong style={{ color: T.textPrimary }}>
                {mlMetrics?.random_forest?.n_samples?.toLocaleString() ?? '2,000'}
              </strong> samples
            </div>
          </div>
        </div>
      </motion.div>

      {/* ── System status bar ───────────────────────────────────────────────── */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.45 }}
        className="card"
        style={{ padding: '12px 20px', display: 'flex', alignItems: 'center', gap: 20, flexWrap: 'wrap' }}
      >
        {[
          {
            label: 'Healing Agent',
            content: healingStatus ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <StatusBadge status="running" />
                <span style={{ fontSize: 12, color: T.textMuted }}>
                  {healingStatus.pending ?? 0} pending · {healingStatus.approved ?? 0} approved
                </span>
              </div>
            ) : <StatusBadge status="idle" />,
          },
          {
            label: 'WebSocket',
            content: (
              <span style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 12,
                color: wsStatus === 'connected' ? '#10B981' : T.textMuted, fontWeight: 500 }}>
                {wsStatus === 'connected' ? <><Wifi size={11} /> Connected</> : wsStatus === 'connecting' ? <>Connecting…</> : <>Standby</>}
              </span>
            ),
          },
          {
            label: 'Last Healed',
            content: (
              <span style={{ fontSize: 12, color: T.textMuted }}>
                {lastHealed?.created_at
                  ? `${displayPipeline(lastHealed.pipeline_name)} — ${formatDistanceToNow(new Date(lastHealed.created_at), { addSuffix: true })}`
                  : 'No heals yet'}
              </span>
            ),
          },
        ].map((item, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            {i > 0 && <div style={{ width: 1, height: 16, background: T.border, flexShrink: 0 }} />}
            <span style={{ fontSize: 10.5, textTransform: 'uppercase', letterSpacing: '0.09em', color: T.textLabel, fontWeight: 700, whiteSpace: 'nowrap' }}>
              {item.label}
            </span>
            {item.content}
          </div>
        ))}
      </motion.div>
    </div>
  )
}
