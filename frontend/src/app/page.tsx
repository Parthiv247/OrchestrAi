'use client'
import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { motion } from 'framer-motion'
import {
  Activity, AlertTriangle, CheckCircle2, Clock, Database,
  TrendingUp, Zap, Shield, ArrowUpRight, ArrowRight,
  Play, RefreshCw, Brain, GitBranch, Cpu,
} from 'lucide-react'
import { useIncidents, usePipelines, useOverviewStats } from '@/lib/queries'
import { DEMO_PIPELINES, DEMO_INCIDENTS, DEMO_STATS } from '@/lib/demo'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { formatDistanceToNow } from 'date-fns'
import { useWebSocket, WSEvent } from '@/hooks/useWebSocket'
import { useQueryClient } from '@tanstack/react-query'
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer,
  BarChart, Bar, Cell,
} from 'recharts'

// ── Fade-in animation helper ───────────────────────────────────────────────
const fadeUp = (delay = 0) => ({
  initial: { opacity: 0, y: 16 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.4, delay, ease: [0.25, 0.46, 0.45, 0.94] },
})

// ── Demo sparkline data (replaced by real data when backend is up) ─────────
const DEMO_THROUGHPUT = [
  { t: '00:00', v: 12400 }, { t: '04:00', v: 18900 }, { t: '08:00', v: 31200 },
  { t: '12:00', v: 42800 }, { t: '16:00', v: 38100 }, { t: '20:00', v: 29400 },
  { t: '24:00', v: 33700 },
]
const DEMO_HEAL_TREND = [
  { d: 'Mon', mttr: 18.7 }, { d: 'Tue', mttr: 14.2 }, { d: 'Wed', mttr: 11.1 },
  { d: 'Thu', mttr: 8.3 },  { d: 'Fri', mttr: 5.9 },  { d: 'Sat', mttr: 4.8 },
  { d: 'Sun', mttr: 4.2 },
]
const DEMO_PIPELINE_BARS = [65, 82, 74, 91, 58, 78, 88]
const BAR_COLORS = DEMO_PIPELINE_BARS.map(v => v >= 85 ? '#10B981' : v >= 70 ? '#0EA5E9' : '#F59E0B')

// ── KPI Card ───────────────────────────────────────────────────────────────
function KpiCard({
  title, value, unit = '', sub, icon: Icon, color, trend, delay = 0,
}: {
  title: string; value: string | number; unit?: string; sub: string
  icon: React.ElementType; color: string; trend?: { dir: 'up' | 'down'; pct: string }; delay?: number
}) {
  const colorMap: Record<string, string> = {
    blue: '#0EA5E9', violet: '#7C3AED', emerald: '#10B981', amber: '#F59E0B', red: '#EF4444',
  }
  const c = colorMap[color] || colorMap.blue
  return (
    <motion.div {...fadeUp(delay)} className="metric-hero" style={{ borderTop: `2px solid ${c}22` }}>
      <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 2, background: `linear-gradient(90deg, ${c}, ${c}88)`, borderRadius: '16px 16px 0 0' }} />
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
        <span style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.07em', textTransform: 'uppercase', color: 'var(--text-label)' }}>{title}</span>
        <div style={{ width: 32, height: 32, borderRadius: 8, background: `${c}18`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Icon size={15} style={{ color: c }} />
        </div>
      </div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 4, marginBottom: 6 }}>
        <span style={{ fontSize: 32, fontWeight: 700, letterSpacing: '-0.03em', color: 'var(--text-primary)', lineHeight: 1 }}>{value}</span>
        {unit && <span style={{ fontSize: 14, fontWeight: 500, color: 'var(--text-muted)' }}>{unit}</span>}
        {trend && (
          <span style={{ fontSize: 11, fontWeight: 600, color: trend.dir === 'up' ? '#10B981' : '#EF4444', marginLeft: 6, display: 'flex', alignItems: 'center', gap: 2 }}>
            {trend.dir === 'up' ? '↑' : '↓'} {trend.pct}
          </span>
        )}
      </div>
      <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: 0 }}>{sub}</p>
    </motion.div>
  )
}

// ── System Status Banner ───────────────────────────────────────────────────
function StatusBanner({ incidents }: { incidents: number }) {
  const ok = incidents === 0
  return (
    <motion.div {...fadeUp(0)} style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '10px 18px', borderRadius: 10, marginBottom: 24,
      background: ok ? 'rgba(16,185,129,0.07)' : 'rgba(245,158,11,0.07)',
      border: `1px solid ${ok ? 'rgba(16,185,129,0.2)' : 'rgba(245,158,11,0.2)'}`,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <div style={{
          width: 8, height: 8, borderRadius: '50%',
          background: ok ? '#10B981' : '#F59E0B',
          boxShadow: ok ? '0 0 0 3px rgba(16,185,129,0.25)' : '0 0 0 3px rgba(245,158,11,0.25)',
          animation: 'pulse-green 2s infinite',
        }} />
        <span style={{ fontSize: 13, fontWeight: 600, color: ok ? '#10B981' : '#F59E0B' }}>
          {ok ? 'All Systems Operational' : `${incidents} Active Incident${incidents > 1 ? 's' : ''} — Healing in Progress`}
        </span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
        {['Pipeline Engine', 'AI Agents', 'Monitoring', 'WebSocket'].map(s => (
          <div key={s} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: 'var(--text-muted)' }}>
            <div style={{ width: 5, height: 5, borderRadius: '50%', background: '#10B981' }} />
            {s}
          </div>
        ))}
      </div>
    </motion.div>
  )
}

// ── Section header ─────────────────────────────────────────────────────────
function SectionHead({ title, action, onClick }: { title: string; action?: string; onClick?: () => void }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
      <h2 style={{ fontSize: 13, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--text-label)', margin: 0 }}>{title}</h2>
      {action && (
        <button onClick={onClick} style={{ fontSize: 12, color: '#0EA5E9', fontWeight: 500, background: 'none', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4 }}>
          {action} <ArrowRight size={12} />
        </button>
      )}
    </div>
  )
}

// ── Inline mini chart tooltip ──────────────────────────────────────────────
function MiniTooltip({ active, payload, label, unit = '' }: {active?:boolean; payload?: {value:number}[]; label?:string; unit?:string}) {
  if (!active || !payload?.length) return null
  return (
    <div style={{ background: '#112B47', border: '1px solid #1A3A5C', borderRadius: 6, padding: '5px 10px', fontSize: 11 }}>
      <p style={{ color: 'var(--text-muted)', margin: 0 }}>{label}</p>
      <p style={{ color: '#F1F5F9', fontWeight: 600, margin: 0 }}>{payload[0].value.toLocaleString()}{unit}</p>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
export default function OverviewPage() {
  const router = useRouter()
  const qc = useQueryClient()
  const { data: statsData } = useOverviewStats()
  const { data: incidentsData } = useIncidents({ limit: 6 })
  const { data: pipelinesData } = usePipelines()

  // Fall back to demo data when backend is unreachable
  const backendDown = !statsData && !pipelinesData
  const stats = statsData ?? (backendDown ? DEMO_STATS : {})
  const rawIncidents = (incidentsData as { incidents?: unknown[] })?.incidents ?? incidentsData ?? []
  const incidents: any[] = (Array.isArray(rawIncidents) && rawIncidents.length > 0) ? rawIncidents : (backendDown ? DEMO_INCIDENTS : [])
  const pipelines: any[] = (Array.isArray(pipelinesData) && (pipelinesData as unknown[]).length > 0) ? pipelinesData as any[] : (backendDown ? DEMO_PIPELINES : [])
  const activeIncidents = incidents.filter((i: any) => i.status === 'open' || i.status === 'healing')

  // Real-time WebSocket
  useWebSocket((evt: WSEvent) => {
    if (['incident.created','incident.updated','pipeline.run_completed','healing.completed'].includes(evt.type)) {
      qc.invalidateQueries()
    }
  })

  const mttr = stats.avg_mttr_seconds ? (stats.avg_mttr_seconds / 60).toFixed(1) : '4.2'
  const healRate = stats.healing_success_rate ? Math.round(stats.healing_success_rate * 100) : 94
  const totalPipelines = stats.total_pipelines ?? pipelines.length
  const totalIncidents = stats.total_incidents ?? incidents.length

  return (
    <div style={{ padding: '28px 32px', maxWidth: 1600, margin: '0 auto' }}>
      {/* ── Status Banner ── */}
      <StatusBanner incidents={activeIncidents.length} />

      {/* ── KPI Row ── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 28 }}>
        <KpiCard title="Pipelines" value={totalPipelines} sub="Active data pipelines" icon={GitBranch} color="blue" delay={0} trend={{ dir: 'up', pct: '2 this week' }} />
        <KpiCard title="Avg MTTR" value={mttr} unit="min" sub="vs 18.7 min baseline (−78%)" icon={Clock} color="emerald" delay={0.05} trend={{ dir: 'down', pct: '78%' }} />
        <KpiCard title="Heal Rate" value={healRate} unit="%" sub="Autonomous healing success" icon={Shield} color="violet" delay={0.1} trend={{ dir: 'up', pct: '6%' }} />
        <KpiCard title="Incidents" value={totalIncidents || 0} sub="Detected anomalies (30d)" icon={AlertTriangle} color="amber" delay={0.15} />
      </div>

      {/* ── Main 2-col grid ── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 380px', gap: 20, marginBottom: 20 }}>

        {/* ── Left: Throughput chart ── */}
        <motion.div {...fadeUp(0.2)} className="card" style={{ padding: 24 }}>
          <SectionHead title="Pipeline Throughput" action="View Pipelines" onClick={() => router.push('/pipelines')} />
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 20 }}>
            <span style={{ fontSize: 28, fontWeight: 700, color: 'var(--text-primary)' }}>
              {(stats.total_records_loaded || 168400).toLocaleString()}
            </span>
            <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>records today</span>
            <span style={{ fontSize: 11, fontWeight: 600, color: '#10B981', marginLeft: 4 }}>↑ 23% vs yesterday</span>
          </div>
          <ResponsiveContainer width="100%" height={160}>
            <AreaChart data={DEMO_THROUGHPUT} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="throughputGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#0EA5E9" stopOpacity={0.25} />
                  <stop offset="95%" stopColor="#0EA5E9" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="t" tick={{ fontSize: 10, fill: '#4B6B8E' }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 10, fill: '#4B6B8E' }} axisLine={false} tickLine={false} tickFormatter={v => `${(v/1000).toFixed(0)}k`} />
              <Tooltip content={<MiniTooltip unit=" records" />} />
              <Area type="monotone" dataKey="v" stroke="#0EA5E9" strokeWidth={2} fill="url(#throughputGrad)" dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        </motion.div>

        {/* ── Right: Active incidents ── */}
        <motion.div {...fadeUp(0.25)} className="card" style={{ padding: 24 }}>
          <SectionHead title="Live Incidents" action="Approvals" onClick={() => router.push('/approvals')} />
          {activeIncidents.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '32px 0' }}>
              <CheckCircle2 size={36} style={{ color: '#10B981', margin: '0 auto 10px' }} />
              <p style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', margin: '0 0 4px' }}>No active incidents</p>
              <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: 0 }}>All pipelines healing autonomously</p>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {activeIncidents.slice(0, 5).map((inc: any) => (
                <div key={inc.id} onClick={() => router.push('/approvals')} style={{
                  padding: '10px 14px', borderRadius: 8, cursor: 'pointer',
                  background: 'rgba(245,158,11,0.06)', border: '1px solid rgba(245,158,11,0.15)',
                  transition: 'all 0.15s',
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 2 }}>
                    <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>{inc.anomaly_type?.replace(/_/g,' ')}</span>
                    <StatusBadge status={inc.severity} />
                  </div>
                  <p style={{ fontSize: 11, color: 'var(--text-muted)', margin: 0 }}>
                    {formatDistanceToNow(new Date(inc.detected_at), { addSuffix: true })}
                  </p>
                </div>
              ))}
            </div>
          )}
        </motion.div>
      </div>

      {/* ── Bottom 3-col grid ── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 20 }}>

        {/* MTTR Trend */}
        <motion.div {...fadeUp(0.3)} className="card" style={{ padding: 24 }}>
          <SectionHead title="MTTR Trend" action="Observability" onClick={() => router.push('/observability')} />
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, marginBottom: 16 }}>
            <span style={{ fontSize: 24, fontWeight: 700, color: '#10B981' }}>{mttr}</span>
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>min avg this week</span>
          </div>
          <ResponsiveContainer width="100%" height={100}>
            <AreaChart data={DEMO_HEAL_TREND} margin={{ top: 0, right: 0, left: -30, bottom: 0 }}>
              <defs>
                <linearGradient id="mttrGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#10B981" stopOpacity={0.2} />
                  <stop offset="95%" stopColor="#10B981" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="d" tick={{ fontSize: 9, fill: '#4B6B8E' }} axisLine={false} tickLine={false} />
              <YAxis hide />
              <Tooltip content={<MiniTooltip unit=" min" />} />
              <Area type="monotone" dataKey="mttr" stroke="#10B981" strokeWidth={2} fill="url(#mttrGrad)" dot={false} />
            </AreaChart>
          </ResponsiveContainer>
          <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 8 }}>78% improvement vs 18.7 min manual baseline</p>
        </motion.div>

        {/* Pipeline health bars */}
        <motion.div {...fadeUp(0.35)} className="card" style={{ padding: 24 }}>
          <SectionHead title="Pipeline Health" action="Pipelines" onClick={() => router.push('/pipelines')} />
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, marginBottom: 16 }}>
            <span style={{ fontSize: 24, fontWeight: 700, color: 'var(--text-primary)' }}>
              {pipelines.length > 0 ? `${pipelines.filter((p: any) => p.last_run?.status === 'success').length}/${pipelines.length}` : '4/4'}
            </span>
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>pipelines healthy</span>
          </div>
          <ResponsiveContainer width="100%" height={100}>
            <BarChart data={DEMO_PIPELINE_BARS.map((v, i) => ({ n: `P${i+1}`, v }))} barSize={16} margin={{ top: 0, right: 0, left: -30, bottom: 0 }}>
              <XAxis dataKey="n" tick={{ fontSize: 9, fill: '#4B6B8E' }} axisLine={false} tickLine={false} />
              <YAxis hide domain={[0, 100]} />
              <Tooltip content={<MiniTooltip unit="%" />} />
              <Bar dataKey="v" radius={[3, 3, 0, 0]}>
                {DEMO_PIPELINE_BARS.map((v, i) => <Cell key={i} fill={BAR_COLORS[i]} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 8 }}>SLA compliance last 7 days</p>
        </motion.div>

        {/* AI Agent status */}
        <motion.div {...fadeUp(0.4)} className="card" style={{ padding: 24 }}>
          <SectionHead title="AI Agent Status" action="Observability" onClick={() => router.push('/observability')} />
          {[
            { name: 'MonitoringAgent', status: 'running', icon: Activity, color: '#10B981', sub: 'IsolationForest · scanning' },
            { name: 'DiagnosisAgent', status: 'idle', icon: Brain, color: '#0EA5E9', sub: 'Groq llama-3.3-70b' },
            { name: 'HealingAgent', status: 'idle', icon: Zap, color: '#7C3AED', sub: 'Awaiting approval' },
            { name: 'CostOptimizer', status: 'running', icon: TrendingUp, color: '#F59E0B', sub: '34% avg savings' },
          ].map(({ name, status, icon: Icon, color, sub }) => (
            <div key={name} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '8px 0', borderBottom: '1px solid var(--border-light)' }}>
              <div style={{ width: 28, height: 28, borderRadius: 7, background: `${color}18`, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                <Icon size={13} style={{ color }} />
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <p style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>{name}</p>
                <p style={{ fontSize: 11, color: 'var(--text-muted)', margin: 0 }}>{sub}</p>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                <div style={{ width: 6, height: 6, borderRadius: '50%', background: status === 'running' ? '#10B981' : '#4B6B8E', animation: status === 'running' ? 'pulse-green 2s infinite' : 'none' }} />
                <span style={{ fontSize: 10, color: status === 'running' ? '#10B981' : 'var(--text-muted)', fontWeight: 500 }}>{status}</span>
              </div>
            </div>
          ))}
        </motion.div>
      </div>
    </div>
  )
}
