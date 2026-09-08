'use client'
import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { motion } from 'framer-motion'
import {
  Activity, AlertTriangle, CheckCircle2, Clock, Database,
  TrendingUp, Zap, Shield, ArrowRight, Brain, GitBranch,
  Cpu, Eye, RefreshCw, BarChart3, ChevronRight,
  CircleDot, Layers, FlaskConical,
} from 'lucide-react'
import { useIncidents, usePipelines, useOverviewStats } from '@/lib/queries'
import { DEMO_PIPELINES, DEMO_INCIDENTS, DEMO_STATS } from '@/lib/demo'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { StatCard } from '@/components/ui/StatCard'
import { formatDistanceToNow } from 'date-fns'
import { useWebSocket, WSEvent } from '@/hooks/useWebSocket'
import { useQueryClient } from '@tanstack/react-query'
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer,
  BarChart, Bar, Cell, LineChart, Line, CartesianGrid,
} from 'recharts'

const fadeUp = (delay = 0) => ({
  initial: { opacity: 0, y: 16 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.38, delay, ease: [0.25, 0.46, 0.45, 0.94] },
})

// ── Demo data ──────────────────────────────────────────────────────────────
const DEMO_THROUGHPUT = [
  { t: '00', v: 12400 }, { t: '02', v: 9800 },  { t: '04', v: 11200 },
  { t: '06', v: 19600 }, { t: '08', v: 31200 }, { t: '10', v: 38900 },
  { t: '12', v: 42800 }, { t: '14', v: 45100 }, { t: '16', v: 38100 },
  { t: '18', v: 33700 }, { t: '20', v: 29400 }, { t: '22', v: 24800 },
  { t: '24', v: 33700 },
]
const DEMO_HEAL_TREND = [
  { d: 'Mon', mttr: 18.7 }, { d: 'Tue', mttr: 14.2 }, { d: 'Wed', mttr: 11.1 },
  { d: 'Thu', mttr: 8.3 },  { d: 'Fri', mttr: 5.9 },  { d: 'Sat', mttr: 4.8 },
  { d: 'Sun', mttr: 4.2 },
]
const DEMO_PIPELINE_HEALTH = [
  { name: 'NYC Taxi',  health: 98, records: '2.1M', status: 'healthy' },
  { name: 'eCommerce', health: 91, records: '840K', status: 'healthy' },
  { name: 'dbt Runs',  health: 85, records: '—',    status: 'degraded' },
  { name: 'Kafka CDC', health: 74, records: '5.3M', status: 'degraded' },
]
const RECENT_ACTIVITY = [
  { time: '2m ago',  color: '#10B981', icon: 'fix',  msg: 'MonitoringAgent detected NULL_SPIKE in ecommerce_orders — auto-healing triggered' },
  { time: '11m ago', color: '#0EA5E9', icon: 'info', msg: 'CostOptimizer saved $142 by rewriting 3 inefficient Snowflake queries' },
  { time: '28m ago', color: '#F59E0B', icon: 'warn', msg: 'CDC lag threshold exceeded on kafka_consumer_v2 (1420s > 1200s)' },
  { time: '1h ago',  color: '#10B981', icon: 'fix',  msg: 'SandboxAgent validated fix for SCHEMA_DRIFT: 20/20 tests passed' },
  { time: '2h ago',  color: '#7C3AED', icon: 'info', msg: 'LearningAgent stored 3 new fix patterns; MTTR improved by 12%' },
  { time: '3h ago',  color: '#10B981', icon: 'fix',  msg: 'DiagnosisAgent resolved INCREMENTAL_SYNC_FAILURE on nyc_taxi_ingest (MTTR: 4.2 min)' },
]
const AGENTS = [
  { name: 'MonitoringAgent', sub: 'IsolationForest · 50+ error signatures', icon: Eye,         color: '#10B981', state: 'running' },
  { name: 'DiagnosisAgent',  sub: 'Groq llama-3.3-70b · 13 anomaly types',  icon: Brain,       color: '#0EA5E9', state: 'idle'    },
  { name: 'FixWriterAgent',  sub: '18 fix templates · RAG-backed',           icon: Zap,         color: '#7C3AED', state: 'idle'    },
  { name: 'SandboxAgent',    sub: 'Docker · 20-point test suite',            icon: FlaskConical,color: '#F59E0B', state: 'running' },
  { name: 'CostOptimizer',   sub: '18 anti-patterns · Snowflake/BQ/PG',     icon: TrendingUp,  color: '#0EA5E9', state: 'idle'    },
  { name: 'LearningAgent',   sub: 'ChromaDB · fix recall & MTTR tracking',   icon: Cpu,         color: '#10B981', state: 'idle'    },
]

function MiniTooltip({ active, payload, label, unit = '' }: { active?: boolean; payload?: { value: number }[]; label?: string; unit?: string }) {
  if (!active || !payload?.length) return null
  return (
    <div style={{ background: '#112B47', border: '1px solid #1A3A5C', borderRadius: 7, padding: '5px 11px', fontSize: 11 }}>
      <p style={{ color: 'var(--text-muted)', margin: 0 }}>{label}</p>
      <p style={{ color: '#F1F5F9', fontWeight: 700, margin: '2px 0 0' }}>{payload[0].value.toLocaleString()}{unit}</p>
    </div>
  )
}

function SectionHead({ title, action, onClick }: { title: string; action?: string; onClick?: () => void }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
      <h2 style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.09em', textTransform: 'uppercase', color: 'var(--text-label)', margin: 0 }}>{title}</h2>
      {action && (
        <button onClick={onClick} style={{ fontSize: 12, color: '#0EA5E9', fontWeight: 500, background: 'none', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4, padding: 0 }}>
          {action} <ChevronRight size={12} />
        </button>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
export default function OverviewPage() {
  const router = useRouter()
  const qc = useQueryClient()
  const { data: statsData } = useOverviewStats()
  const { data: incidentsData } = useIncidents({ limit: 10 })
  const { data: pipelinesData } = usePipelines()

  const backendDown = !statsData && !pipelinesData
  const stats = statsData ?? (backendDown ? DEMO_STATS : {})
  const rawIncidents = (incidentsData as { incidents?: unknown[] })?.incidents ?? incidentsData ?? []
  const incidents: any[] = (Array.isArray(rawIncidents) && rawIncidents.length > 0)
    ? rawIncidents : (backendDown ? DEMO_INCIDENTS : [])
  const pipelines: any[] = (Array.isArray(pipelinesData) && (pipelinesData as unknown[]).length > 0)
    ? pipelinesData as any[]
    : (backendDown ? DEMO_PIPELINES : [])
  const activeIncidents = incidents.filter((i: any) => i.status === 'open' || i.status === 'healing')

  useWebSocket((evt: WSEvent) => {
    if (['incident.created', 'incident.updated', 'pipeline.run_completed', 'healing.completed'].includes(evt.type)) {
      qc.invalidateQueries()
    }
  })

  const mttr = stats.avg_mttr_seconds ? (stats.avg_mttr_seconds / 60).toFixed(1) : '4.2'
  const healRate = stats.healing_success_rate ? Math.round(stats.healing_success_rate * 100) : 94
  const totalPipelines = stats.total_pipelines ?? pipelines.length
  const totalIncidents = stats.total_incidents ?? incidents.length
  const ok = activeIncidents.length === 0

  return (
    <div style={{ padding: '28px 32px', maxWidth: 1600, margin: '0 auto' }}>

      {/* ── Hero header ── */}
      <motion.div {...fadeUp(0)} style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 10 }}>
          <div>
            <h1 style={{ fontSize: 24, fontWeight: 800, letterSpacing: '-0.03em', color: 'var(--text-primary)', margin: 0 }}>
              Platform Overview
            </h1>
            <p style={{ fontSize: 13, color: 'var(--text-muted)', margin: '4px 0 0' }}>
              Self-healing data pipeline intelligence · 11 LangGraph agents active
            </p>
          </div>
          {/* System status pill */}
          <div style={{
            display: 'flex', alignItems: 'center', gap: 8, padding: '8px 14px',
            borderRadius: 40, flexShrink: 0,
            background: ok ? 'rgba(16,185,129,0.08)' : 'rgba(245,158,11,0.08)',
            border: `1px solid ${ok ? 'rgba(16,185,129,0.22)' : 'rgba(245,158,11,0.22)'}`,
          }}>
            <span style={{
              width: 7, height: 7, borderRadius: '50%', display: 'block',
              background: ok ? '#10B981' : '#F59E0B',
              animation: ok ? 'pulse-green 2s infinite' : 'pulse-amber 2.8s infinite',
            }} />
            <span style={{ fontSize: 12.5, fontWeight: 600, color: ok ? '#10B981' : '#F59E0B' }}>
              {ok ? 'All Systems Operational' : `${activeIncidents.length} Active Incident${activeIncidents.length > 1 ? 's' : ''}`}
            </span>
            {/* Sub-status dots */}
            <div style={{ display: 'flex', gap: 10, marginLeft: 8, paddingLeft: 12, borderLeft: '1px solid var(--border)' }}>
              {['Pipelines', 'Agents', 'Monitoring'].map(s => (
                <div key={s} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11, color: 'var(--text-muted)' }}>
                  <span style={{ width: 5, height: 5, borderRadius: '50%', background: '#10B981', display: 'inline-block' }} />
                  {s}
                </div>
              ))}
            </div>
          </div>
        </div>
        <div style={{ height: 1, background: 'linear-gradient(90deg, var(--border) 0%, transparent 80%)' }} />
      </motion.div>

      {/* ── KPI row ── */}
      <div className="stat-grid-4" style={{ marginBottom: 24 }}>
        <StatCard title="Active Pipelines" value={totalPipelines} sub="Running in production" icon={GitBranch} color="blue" delay={0} delta={{ value: '2 this week', positive: true }} live />
        <StatCard title="Avg MTTR" value={mttr} unit="min" sub="vs 18.7 min manual baseline" icon={Clock} color="green" delay={0.06} delta={{ value: '78%', positive: false }} />
        <StatCard title="Heal Rate" value={healRate} unit="%" sub="Autonomous healing success" icon={Shield} color="violet" delay={0.12} delta={{ value: '6% MoM', positive: true }} />
        <StatCard title="Anomalies (30d)" value={totalIncidents || 0} sub="Auto-detected by agents" icon={AlertTriangle} color="amber" delay={0.18} />
      </div>

      {/* ── Main content: throughput + incidents ── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 360px', gap: 18, marginBottom: 18 }}>

        {/* Throughput chart */}
        <motion.div {...fadeUp(0.22)} className="card" style={{ padding: 24 }}>
          <SectionHead title="Pipeline Throughput — Last 24h" action="View Pipelines" onClick={() => router.push('/pipelines')} />
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 20 }}>
            <span style={{ fontSize: 30, fontWeight: 800, letterSpacing: '-0.03em', color: 'var(--text-primary)' }}>
              {(stats.total_records_loaded || 168_400).toLocaleString()}
            </span>
            <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>records today</span>
            <span style={{ fontSize: 11.5, fontWeight: 700, color: '#10B981', marginLeft: 2 }}>↑ 23% vs yesterday</span>
          </div>
          <ResponsiveContainer width="100%" height={155}>
            <AreaChart data={DEMO_THROUGHPUT} margin={{ top: 0, right: 0, left: -24, bottom: 0 }}>
              <defs>
                <linearGradient id="thrGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#0EA5E9" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#0EA5E9" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="t" tick={{ fontSize: 10, fill: '#4B6B8E' }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 10, fill: '#4B6B8E' }} axisLine={false} tickLine={false} tickFormatter={v => `${(v / 1000).toFixed(0)}k`} />
              <Tooltip content={<MiniTooltip unit=" records" />} />
              <Area type="monotone" dataKey="v" stroke="#0EA5E9" strokeWidth={2} fill="url(#thrGrad)" dot={false} activeDot={{ r: 4, fill: '#0EA5E9' }} />
            </AreaChart>
          </ResponsiveContainer>
        </motion.div>

        {/* Active incidents / healing queue */}
        <motion.div {...fadeUp(0.27)} className="card" style={{ padding: 24, display: 'flex', flexDirection: 'column' }}>
          <SectionHead title="Healing Queue" action="Approvals" onClick={() => router.push('/approvals')} />
          {activeIncidents.length === 0 ? (
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 10, padding: '16px 0' }}>
              <div style={{ width: 48, height: 48, borderRadius: 12, background: 'rgba(16,185,129,0.1)', border: '1px solid rgba(16,185,129,0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <CheckCircle2 size={22} style={{ color: '#10B981' }} />
              </div>
              <p style={{ fontSize: 13.5, fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>Queue empty</p>
              <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: 0, textAlign: 'center' }}>All anomalies healed autonomously</p>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {activeIncidents.slice(0, 5).map((inc: any) => (
                <div key={inc.id} onClick={() => router.push('/approvals')}
                  style={{
                    padding: '10px 14px', borderRadius: 9, cursor: 'pointer',
                    background: 'rgba(245,158,11,0.06)', border: '1px solid rgba(245,158,11,0.15)',
                    transition: 'all 0.15s',
                  }}
                  onMouseEnter={e => { (e.currentTarget as HTMLElement).style.borderColor = 'rgba(245,158,11,0.35)' }}
                  onMouseLeave={e => { (e.currentTarget as HTMLElement).style.borderColor = 'rgba(245,158,11,0.15)' }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 3 }}>
                    <span style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--text-primary)' }}>
                      {inc.anomaly_type?.replace(/_/g, ' ')}
                    </span>
                    <StatusBadge status={inc.severity} />
                  </div>
                  <p style={{ fontSize: 11, color: 'var(--text-muted)', margin: 0 }}>
                    {inc.pipeline_name ?? 'Unknown pipeline'} · {formatDistanceToNow(new Date(inc.detected_at), { addSuffix: true })}
                  </p>
                </div>
              ))}
            </div>
          )}
        </motion.div>
      </div>

      {/* ── Second row: MTTR trend + Pipeline health + AI Agents ── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1.1fr', gap: 18, marginBottom: 18 }}>

        {/* MTTR Trend */}
        <motion.div {...fadeUp(0.3)} className="card" style={{ padding: 24 }}>
          <SectionHead title="MTTR Trend (7d)" action="Observability" onClick={() => router.push('/observability')} />
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 4 }}>
            <span style={{ fontSize: 28, fontWeight: 800, color: '#10B981', letterSpacing: '-0.03em' }}>{mttr}</span>
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>min avg</span>
          </div>
          <p style={{ fontSize: 11.5, color: 'var(--text-muted)', margin: '0 0 14px' }}>
            −78% vs 18.7 min manual baseline
          </p>
          <ResponsiveContainer width="100%" height={95}>
            <AreaChart data={DEMO_HEAL_TREND} margin={{ top: 0, right: 0, left: -34, bottom: 0 }}>
              <defs>
                <linearGradient id="mttrGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#10B981" stopOpacity={0.22} />
                  <stop offset="95%" stopColor="#10B981" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="d" tick={{ fontSize: 9.5, fill: '#4B6B8E' }} axisLine={false} tickLine={false} />
              <YAxis hide />
              <Tooltip content={<MiniTooltip unit=" min" />} />
              <Area type="monotone" dataKey="mttr" stroke="#10B981" strokeWidth={2} fill="url(#mttrGrad)" dot={false} activeDot={{ r: 3, fill: '#10B981' }} />
            </AreaChart>
          </ResponsiveContainer>
        </motion.div>

        {/* Pipeline Health */}
        <motion.div {...fadeUp(0.35)} className="card" style={{ padding: 24 }}>
          <SectionHead title="Pipeline Health" action="Pipelines" onClick={() => router.push('/pipelines')} />
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {DEMO_PIPELINE_HEALTH.map(({ name, health, records, status }) => (
              <div key={name}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                    <span style={{
                      width: 6, height: 6, borderRadius: '50%', display: 'block',
                      background: status === 'healthy' ? '#10B981' : '#F59E0B',
                    }} />
                    <span style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--text-primary)' }}>{name}</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{records}</span>
                    <span style={{ fontSize: 12, fontWeight: 700, color: health >= 90 ? '#10B981' : health >= 75 ? '#F59E0B' : '#EF4444' }}>
                      {health}%
                    </span>
                  </div>
                </div>
                <div className="progress-track">
                  <div className="progress-fill" style={{
                    width: `${health}%`,
                    background: health >= 90 ? '#10B981' : health >= 75 ? 'linear-gradient(90deg,#F59E0B,#FBBF24)' : '#EF4444',
                  }} />
                </div>
              </div>
            ))}
          </div>
        </motion.div>

        {/* AI Agent Status */}
        <motion.div {...fadeUp(0.4)} className="card" style={{ padding: 24 }}>
          <SectionHead title="AI Agent Status" action="Observability" onClick={() => router.push('/observability')} />
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {AGENTS.map(({ name, sub, icon: Icon, color, state }) => (
              <div key={name} style={{
                display: 'flex', alignItems: 'center', gap: 11, padding: '7px 0',
                borderBottom: '1px solid var(--border-light)',
              }}>
                <div style={{
                  width: 28, height: 28, borderRadius: 8, flexShrink: 0,
                  background: `${color}15`, border: `1px solid ${color}25`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  <Icon size={13} style={{ color }} />
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <p style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', margin: 0, lineHeight: 1.2 }}>{name}</p>
                  <p style={{ fontSize: 10.5, color: 'var(--text-muted)', margin: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{sub}</p>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 5, flexShrink: 0 }}>
                  <span style={{
                    width: 6, height: 6, borderRadius: '50%', display: 'block',
                    background: state === 'running' ? '#10B981' : '#4B6B8E',
                    animation: state === 'running' ? 'pulse-green 2s infinite' : 'none',
                  }} />
                  <span style={{ fontSize: 10.5, color: state === 'running' ? '#10B981' : 'var(--text-muted)', fontWeight: 500 }}>
                    {state}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </motion.div>
      </div>

      {/* ── Bottom row: Recent Activity ── */}
      <motion.div {...fadeUp(0.44)} className="card" style={{ padding: 24 }}>
        <SectionHead title="Recent Activity" action="Observability" onClick={() => router.push('/observability')} />
        <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
          {RECENT_ACTIVITY.map((item, i) => (
            <div key={i} style={{
              display: 'flex', alignItems: 'flex-start', gap: 12, padding: '9px 0',
              borderBottom: i < RECENT_ACTIVITY.length - 1 ? '1px solid var(--border-light)' : 'none',
            }}>
              {/* Colored dot */}
              <div style={{ flexShrink: 0, marginTop: 4 }}>
                <span style={{ width: 7, height: 7, borderRadius: '50%', background: item.color, display: 'block' }} />
              </div>
              {/* Message */}
              <p style={{ fontSize: 12.5, color: 'var(--text-secondary)', margin: 0, lineHeight: 1.5, flex: 1 }}>
                {item.msg}
              </p>
              {/* Time */}
              <span style={{ fontSize: 11, color: 'var(--text-label)', flexShrink: 0, paddingTop: 2 }}>
                {item.time}
              </span>
            </div>
          ))}
        </div>
      </motion.div>
    </div>
  )
}
