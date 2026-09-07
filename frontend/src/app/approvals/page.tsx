'use client'
import { useState, useCallback, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Shield, CheckCircle, XCircle, Clock,
  Wifi, ChevronDown, ChevronRight, ShieldCheck,
} from 'lucide-react'
import { EmptyState } from '@/components/ui/EmptyState'
import { SkeletonList } from '@/components/ui/Skeleton'
import { useIncidents } from '@/lib/queries'
import type { Incident } from '@/lib/types'
import { healingApi } from '@/lib/api'
import { useToast } from '@/components/ui/Toaster'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { CodeBlock } from '@/components/ui/CodeBlock'
import { formatDistanceToNow } from 'date-fns'
import { Progress } from '@/components/ui/progress'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useWebSocket, WSEvent } from '@/hooks/useWebSocket'
import { useQueryClient } from '@tanstack/react-query'

const C = {
  bg: 'var(--bg)', card: 'var(--card-bg)', border: 'var(--border)',
  accent: 'var(--accent)', emerald: 'var(--emerald)', amber: 'var(--amber)', red: 'var(--red)', violet: 'var(--violet)',
  textPrimary: 'var(--text-primary)', textMuted: 'var(--text-muted)', textLabel: 'var(--text-label)',
}

const anomalyMeta: Record<string, { label: string; color: string; bg: string }> = {
  ZERO_LOAD:            { label: 'Zero Load',     color: C.red,    bg: 'rgba(239,68,68,0.12)' },
  ROW_COUNT_DROP:       { label: 'Row Drop',       color: C.amber,  bg: 'rgba(245,158,11,0.12)' },
  ML_ANOMALY:           { label: 'ML Anomaly',     color: C.accent, bg: 'rgba(14,165,233,0.12)' },
  NULL_SPIKE:           { label: 'Null Spike',     color: C.violet, bg: 'rgba(124,58,237,0.12)' },
  CONSECUTIVE_FAILURES: { label: 'Repeat Fail',    color: C.red,    bg: 'rgba(239,68,68,0.12)' },
  PIPELINE_DELAY:       { label: 'Pipeline Delay', color: C.amber,  bg: 'rgba(245,158,11,0.12)' },
}

function getAnomalyMeta(type: string | undefined) {
  return anomalyMeta[(type || '').toUpperCase()] ?? { label: type || 'Unknown', color: C.textMuted, bg: 'rgba(100,116,139,0.12)' }
}

const PIPELINE_DISPLAY: Record<string, string> = {
  pipeline_csv_to_snowflake: 'CSV Files → Snowflake',
  pipeline_postgresql_to_snowflake: 'PostgreSQL → Snowflake',
  pipeline_rest_api_to_snowflake: 'REST API (Weather) → Snowflake',
  pipeline_google_sheets_to_snowflake: 'Google Sheets → Snowflake',
}

function displayPipeline(name: string | undefined): string {
  return name ? (PIPELINE_DISPLAY[name] || name) : '—'
}

function statusBorderColor(status: string | undefined) {
  if (status === 'pending') return C.amber
  if (status === 'approved') return C.emerald
  if (status === 'rejected') return C.red
  return C.border
}

const PAGE_SIZE = 50

function MiniStat({ label, value, color }: { label: string; value: number | string; color: string }) {
  return (
    <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 10, padding: '12px 16px', flex: 1 }}>
      <p style={{ fontSize: 11, letterSpacing: '0.08em', textTransform: 'uppercase' as const, color: C.textLabel, marginBottom: 4, margin: '0 0 4px' }}>{label}</p>
      <p style={{ fontSize: 22, fontWeight: 700, color, margin: 0 }}>{value}</p>
    </div>
  )
}

function CollapsibleCode({ code, language }: { code: string; language: string }) {
  const [open, setOpen] = useState(false)
  return (
    <div>
      <button
        onClick={() => setOpen(o => !o)}
        style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: C.textMuted, marginBottom: open ? 8 : 0, background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
      >
        {open ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
        {open ? 'Hide healing plan' : 'Show healing plan'}
      </button>
      <AnimatePresence>
        {open && (
          <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }} style={{ overflow: 'hidden' }}>
            <CodeBlock code={code} language={language} maxLines={20} />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

export default function ApprovalsPage() {
  const toast = useToast()
  const queryClient = useQueryClient()
  const [pageOffset, setPageOffset] = useState(0)
  const { data: incidentsPage, isLoading, refetch } = useIncidents({ limit: PAGE_SIZE, offset: pageOffset })
  const [allFetched, setAllFetched] = useState<Incident[]>([])
  const [selected, setSelected] = useState<Incident | null>(null)

  useEffect(() => {
    if (!incidentsPage?.incidents) return
    setAllFetched(prev => {
      if (pageOffset === 0) return incidentsPage.incidents
      const existingIds = new Set(prev.map((i: Incident) => i.id))
      const newOnes = incidentsPage.incidents.filter((i: Incident) => !existingIds.has(i.id))
      return [...prev, ...newOnes]
    })
  }, [incidentsPage, pageOffset])

  const hasMore = incidentsPage?.has_more ?? false

  const handleWSEvent = useCallback((event: WSEvent) => {
    if (event.type === 'incident_update') {
      queryClient.invalidateQueries({ queryKey: ['incidents'] })
      setPageOffset(0)
      if (event.data.status === 'pending_approval') {
        toast(`New fix ready for review — ${event.data.incident_id}`, 'info')
      }
    }
  }, [queryClient, toast])

  const { status: wsStatus } = useWebSocket({ onEvent: handleWSEvent })
  const [filter, setFilter] = useState<'all' | 'pending' | 'resolved'>('all')
  const [rejectReason, setRejectReason] = useState('')
  const [showReject, setShowReject] = useState(false)
  const [actionResult, setActionResult] = useState<null | 'approved' | 'rejected'>(null)
  const [loading, setLoading] = useState(false)

  const allIncidents = allFetched.filter((i: Incident) => {
    const name = i.pipeline_name || ''
    const isOldName = name.startsWith('ingest_') || name.startsWith('kafka_') || name === 'dbt_run'
    return i.anomaly_type && !isOldName
  })

  const filtered = allIncidents.filter((i: Incident) => {
    if (filter === 'pending') return i.approval_status === 'pending'
    if (filter === 'resolved') return i.approval_status !== 'pending'
    return true
  })

  const pendingCount  = allIncidents.filter((i: Incident) => i.approval_status === 'pending').length
  const approvedCount = allIncidents.filter((i: Incident) => i.approval_status === 'approved').length

  const handleApprove = async () => {
    if (!selected?.id) return
    setLoading(true)
    try {
      await healingApi.approve(String(selected.id), selected.approval_token || 'approve')
      setActionResult('approved')
      toast('Fix approved — deploying to pipeline', 'success')
      refetch()
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } }; message?: string }
      const msg = e?.response?.data?.detail || e?.message || 'Request failed'
      toast(`Approval failed: ${msg}`, 'error')
    }
    setLoading(false)
  }

  const handleReject = async () => {
    if (!selected?.id) return
    setLoading(true)
    try {
      await healingApi.reject(String(selected.id), selected.approval_token || 'reject', rejectReason)
      setActionResult('rejected')
      toast('Fix rejected — incident remains open', 'info')
      refetch()
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } }; message?: string }
      const msg = e?.response?.data?.detail || e?.message || 'Request failed'
      toast(`Rejection failed: ${msg}`, 'error')
    }
    setLoading(false)
    setShowReject(false)
  }

  const sandboxResults = selected?.sandbox_results || {}
  const testEntries = Object.entries(sandboxResults)
  const testsPassed = selected?.tests_passed ?? 0

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}
      style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 56px)', background: C.bg }}
    >
      {/* Page header */}
      <div style={{ padding: '20px 24px 16px', borderBottom: `1px solid ${C.border}`, background: C.card }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{ width: 36, height: 36, borderRadius: 10, background: 'rgba(245,158,11,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Shield size={18} style={{ color: C.amber }} />
            </div>
            <div>
              <h1 style={{ fontSize: 18, fontWeight: 700, color: C.textPrimary, margin: 0 }}>Approval Panel</h1>
              <p style={{ fontSize: 12, color: C.textMuted, margin: 0 }}>Review and deploy AI-generated pipeline fixes</p>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {(['all', 'pending', 'resolved'] as const).map(f => (
              <button key={f} onClick={() => setFilter(f)} style={{
                padding: '4px 12px', borderRadius: 20, fontSize: 12, fontWeight: 600, cursor: 'pointer',
                border: filter === f ? `1px solid ${C.accent}` : `1px solid ${C.border}`,
                background: filter === f ? 'rgba(14,165,233,0.15)' : 'transparent',
                color: filter === f ? C.accent : C.textMuted, textTransform: 'capitalize' as const,
              }}>
                {f === 'all' ? `All ${allIncidents.length}` : f === 'pending' ? `Pending ${pendingCount}` : `Resolved ${approvedCount}`}
              </button>
            ))}
            <div style={{ width: 1, height: 20, background: C.border, margin: '0 4px' }} />
            {wsStatus === 'connected' ? (
              <span style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 11, color: C.emerald, fontWeight: 600 }}>
                <Wifi size={11} /> Live
              </span>
            ) : wsStatus === 'connecting' ? (
              <span style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 11, color: C.amber }}>
                <Wifi size={11} /> Connecting…
              </span>
            ) : null}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <MiniStat label="Pending Approval" value={pendingCount}         color={C.amber} />
          <MiniStat label="Auto-Healed 24h"  value={approvedCount}        color={C.emerald} />
          <MiniStat label="Total Incidents"   value={allIncidents.length}  color={C.accent} />
        </div>
      </div>

      {/* Body */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        {/* Left panel */}
        <div style={{ width: 320, borderRight: `1px solid ${C.border}`, display: 'flex', flexDirection: 'column', background: '#09111E', overflowY: 'auto' }}>
          {isLoading && pageOffset === 0 ? (
            <div style={{ padding: 12 }}>
              <SkeletonList items={4} />
            </div>
          ) : filtered.length === 0 ? (
            <div style={{ flex: 1 }}>
              <EmptyState
                icon={ShieldCheck}
                title="All clear — no pending approvals"
                description="OrchestrAI hasn't detected any anomalies requiring human review. Your pipelines are running healthy."
                size="lg"
              />
            </div>
          ) : (
            <div style={{ padding: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>
              {filtered.map((inc: Incident) => {
                const meta = getAnomalyMeta(inc.anomaly_type)
                const isPending = inc.approval_status === 'pending'
                const isActive = selected?.id === inc.id
                return (
                  <button key={inc.id}
                    onClick={() => { setSelected(inc); setActionResult(null); setShowReject(false) }}
                    style={{
                      display: 'block', width: '100%', textAlign: 'left', borderRadius: 10, padding: '10px 12px', cursor: 'pointer',
                      background: isActive ? 'rgba(14,165,233,0.1)' : 'transparent',
                      border: `1px solid ${isActive ? C.accent : statusBorderColor(inc.approval_status)}`,
                      borderLeft: `3px solid ${statusBorderColor(inc.approval_status)}`,
                    }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
                      <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.06em', padding: '2px 7px', borderRadius: 5, background: meta.bg, color: meta.color }}>
                        {meta.label.toUpperCase()}
                      </span>
                      {isPending && <span style={{ fontSize: 10, color: C.amber, fontWeight: 600 }}>● PENDING</span>}
                    </div>
                    <p style={{ fontSize: 13, fontWeight: 600, color: C.textPrimary, margin: '0 0 2px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {displayPipeline(inc.pipeline_name)}
                    </p>
                    <p style={{ fontSize: 11, color: C.textMuted, margin: 0 }}>
                      {inc.created_at ? formatDistanceToNow(new Date(inc.created_at), { addSuffix: true }) : 'recently'}
                    </p>
                  </button>
                )
              })}
              {hasMore && (
                <button onClick={() => setPageOffset(o => o + PAGE_SIZE)} disabled={isLoading}
                  style={{ width: '100%', padding: '8px 0', borderRadius: 8, fontSize: 12, color: C.textMuted, border: `1px solid ${C.border}`, background: 'transparent', cursor: 'pointer', opacity: isLoading ? 0.5 : 1 }}>
                  {isLoading ? 'Loading…' : `Load more (${(incidentsPage?.total ?? 0) - allFetched.length} remaining)`}
                </button>
              )}
            </div>
          )}
        </div>

        {/* Right panel */}
        <div style={{ flex: 1, overflowY: 'auto', padding: 24, background: C.bg }}>
          {!selected ? (
            <div style={{ height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 16 }}>
              <div style={{ width: 80, height: 80, borderRadius: 24, background: 'rgba(14,165,233,0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <Shield size={40} style={{ color: C.accent }} />
              </div>
              <p style={{ fontSize: 17, fontWeight: 600, color: C.textPrimary, margin: 0 }}>Select an incident</p>
              <p style={{ fontSize: 13, color: C.textMuted, margin: 0 }}>Choose from the left panel to review the healing plan</p>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16, maxWidth: 760 }}>
              {/* Incident header */}
              <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, padding: 20 }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
                  <div>
                    <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.06em', padding: '3px 10px', borderRadius: 6, background: getAnomalyMeta(selected.anomaly_type).bg, color: getAnomalyMeta(selected.anomaly_type).color }}>
                      {getAnomalyMeta(selected.anomaly_type).label.toUpperCase()}
                    </span>
                    <h2 style={{ fontSize: 20, fontWeight: 700, color: C.textPrimary, margin: '10px 0 4px' }}>
                      {displayPipeline(selected.pipeline_name)}
                    </h2>
                    <p style={{ fontSize: 12, color: C.textMuted, margin: 0, display: 'flex', alignItems: 'center', gap: 4 }}>
                      <Clock size={12} />
                      {selected.created_at ? formatDistanceToNow(new Date(selected.created_at), { addSuffix: true }) : ''}
                    </p>
                  </div>
                  <StatusBadge status={selected.approval_status === 'pending' ? 'pending' : selected.approval_status === 'approved' ? 'healthy' : 'warning'} />
                </div>
              </div>

              {/* Root cause */}
              <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, padding: 20 }}>
                <p style={{ fontSize: 11, letterSpacing: '0.08em', textTransform: 'uppercase' as const, color: C.textLabel, marginBottom: 12, fontWeight: 600, margin: '0 0 12px' }}>Root Cause Analysis</p>
                {selected.root_cause && (
                  <blockquote style={{ borderLeft: `2px solid ${C.accent}`, paddingLeft: 14, paddingTop: 8, paddingBottom: 8, marginBottom: 14, fontStyle: 'italic', fontSize: 13, color: C.textPrimary, background: 'rgba(14,165,233,0.05)', borderRadius: '0 6px 6px 0', margin: '0 0 14px' }}>
                    {selected.root_cause}
                  </blockquote>
                )}
                {selected.root_cause_confidence !== undefined && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: C.textMuted }}>
                      <span>Confidence</span>
                      <span style={{ color: selected.root_cause_confidence > 0.8 ? C.emerald : C.amber, fontWeight: 600 }}>
                        {Math.round(selected.root_cause_confidence * 100)}%
                      </span>
                    </div>
                    <Progress value={selected.root_cause_confidence * 100} className="h-2" />
                  </div>
                )}
              </div>

              {/* Sandbox results */}
              {testEntries.length > 0 && (
                <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, padding: 20 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
                    <p style={{ fontSize: 11, letterSpacing: '0.08em', textTransform: 'uppercase' as const, color: C.textLabel, fontWeight: 600, margin: 0 }}>Sandbox Results</p>
                    <span style={{ fontSize: 12, fontWeight: 600, color: testsPassed >= 9 ? C.emerald : C.amber }}>{testsPassed}/12 tests passed</span>
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
                    {testEntries.map(([name, passed]) => (
                      <div key={name} style={{ padding: '8px 6px', borderRadius: 8, textAlign: 'center', background: passed ? 'rgba(16,185,129,0.1)' : 'rgba(239,68,68,0.1)' }}>
                        <div style={{ fontSize: 16, marginBottom: 4 }}>{passed ? '✅' : '❌'}</div>
                        <p style={{ fontSize: 10, color: C.textMuted, lineHeight: 1.3, margin: 0 }}>
                          {String(name).replace('T0','').replace('T1','').replace(/_/g,' ')}
                        </p>
                      </div>
                    ))}
                  </div>
                  <div style={{ marginTop: 12 }}>
                    <Progress value={selected.confidence_score ? selected.confidence_score * 100 : 0} className="h-1.5" />
                    <p style={{ fontSize: 11, color: C.textMuted, marginTop: 4 }}>
                      Confidence: {selected.confidence_score ? Math.round(selected.confidence_score * 100) : 0}%
                    </p>
                  </div>
                </div>
              )}

              {/* Fix code */}
              {selected.fix_code && (
                <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, padding: 20 }}>
                  <p style={{ fontSize: 11, letterSpacing: '0.08em', textTransform: 'uppercase' as const, color: C.textLabel, marginBottom: 12, fontWeight: 600, margin: '0 0 12px' }}>Healing Plan</p>
                  <CollapsibleCode code={selected.fix_code} language={selected.fix_language || 'python'} />
                </div>
              )}

              {/* Actions */}
              {actionResult === 'approved' ? (
                <div style={{ background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.3)', borderRadius: 12, padding: 20, display: 'flex', alignItems: 'center', gap: 12 }}>
                  <CheckCircle size={20} style={{ color: C.emerald, flexShrink: 0 }} />
                  <div>
                    <p style={{ fontWeight: 600, color: C.textPrimary, margin: '0 0 2px' }}>Fix Deployed</p>
                    <p style={{ fontSize: 13, color: C.textMuted, margin: 0 }}>Pipeline has been restarted with the fix applied.</p>
                  </div>
                </div>
              ) : actionResult === 'rejected' ? (
                <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, padding: 20, display: 'flex', alignItems: 'center', gap: 12 }}>
                  <XCircle size={20} style={{ color: C.textMuted }} />
                  <p style={{ color: C.textPrimary, margin: 0 }}>Fix rejected — incident remains open for manual review.</p>
                </div>
              ) : selected.approval_status === 'pending' ? (
                <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, padding: 20 }}>
                  <p style={{ fontSize: 11, letterSpacing: '0.08em', textTransform: 'uppercase' as const, color: C.textLabel, marginBottom: 14, fontWeight: 600, margin: '0 0 14px' }}>Action Required</p>
                  {showReject ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                      <textarea
                        value={rejectReason} onChange={e => setRejectReason(e.target.value)}
                        placeholder="Reason for rejection..."
                        style={{ width: '100%', height: 80, padding: '10px 12px', borderRadius: 8, resize: 'none', fontSize: 13, background: '#060D18', border: `1px solid ${C.border}`, color: C.textPrimary, boxSizing: 'border-box' }}
                      />
                      <div style={{ display: 'flex', gap: 8 }}>
                        <button onClick={handleReject} disabled={loading}
                          style={{ flex: 1, padding: '10px 0', borderRadius: 8, fontSize: 13, fontWeight: 600, cursor: 'pointer', background: 'rgba(239,68,68,0.15)', color: C.red, border: '1px solid rgba(239,68,68,0.3)', opacity: loading ? 0.6 : 1 }}>
                          Confirm Reject
                        </button>
                        <button onClick={() => setShowReject(false)}
                          style={{ padding: '10px 16px', borderRadius: 8, fontSize: 13, fontWeight: 600, cursor: 'pointer', background: 'transparent', color: C.textMuted, border: `1px solid ${C.border}` }}>
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div style={{ display: 'flex', gap: 10 }}>
                      <button onClick={handleApprove} disabled={loading}
                        style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, padding: '12px 0', borderRadius: 8, fontSize: 13, fontWeight: 600, cursor: 'pointer', background: 'rgba(16,185,129,0.15)', color: C.emerald, border: '1px solid rgba(16,185,129,0.35)', opacity: loading ? 0.6 : 1 }}>
                        <CheckCircle size={15} /> Approve &amp; Deploy
                      </button>
                      <button onClick={() => setShowReject(true)}
                        style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, padding: '12px 0', borderRadius: 8, fontSize: 13, fontWeight: 600, cursor: 'pointer', background: 'transparent', color: C.red, border: '1px solid rgba(239,68,68,0.35)' }}>
                        <XCircle size={15} /> Reject Fix
                      </button>
                    </div>
                  )}
                </div>
              ) : null}
            </div>
          )}
        </div>
      </div>
    </motion.div>
  )
}
