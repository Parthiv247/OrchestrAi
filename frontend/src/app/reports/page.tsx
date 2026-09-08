'use client'
import { useState } from 'react'
import { motion } from 'framer-motion'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Mail, Calendar, Play, Trash2, Plus, X, CheckCircle2,
  AlertCircle, Clock, Send, FileText, BarChart2, Shield,
  RefreshCw, ChevronDown, ChevronUp,
} from 'lucide-react'
import { EmptyState } from '@/components/ui/EmptyState'
import { DEMO_REPORTS, DEMO_DELIVERIES } from '@/lib/demo'
import api from '@/lib/api'
import { useToast } from '@/components/ui/Toaster'
import { formatDistanceToNow } from 'date-fns'

const C = {
  bg: '#080F1C', card: '#0F2540', border: '#1A3A5C',
  accent: '#0EA5E9', emerald: '#10B981', amber: '#F59E0B', red: '#EF4444', violet: '#7C3AED',
  textPrimary: '#F1F5F9', textMuted: '#64748B', textLabel: '#4B6B8E',
}

async function apiFetch(path: string, opts?: RequestInit) {
  const method = ((opts?.method ?? 'GET') as string).toUpperCase()
  let body: unknown
  if (opts?.body) {
    try { body = JSON.parse(opts.body as string) } catch { body = opts.body }
  }
  const r = await api.request({ method, url: path, data: body })
  return r.data
}

interface ScheduledReport {
  id: string; name: string; report_type: string; description: string;
  schedule_cron: string; recipients: string[]; enabled: boolean;
  format: string; last_sent_at: string | null; last_status: string;
  next_run_at: string | null; created_at: string;
}

interface Delivery {
  id: string; report_id: string; report_name?: string; report_type?: string;
  sent_at: string; status: string; recipients: string[];
  subject: string; body_preview: string; error_message: string;
}

const CRON_PRESETS = [
  { label: 'Daily at 9am',    value: '0 9 * * *' },
  { label: 'Daily at 6pm',    value: '0 18 * * *' },
  { label: 'Weekly (Monday)', value: '0 9 * * 1' },
  { label: 'Weekly (Friday)', value: '0 17 * * 5' },
  { label: 'Monthly (1st)',   value: '0 7 1 * *' },
  { label: 'Every 6 hours',   value: '0 */6 * * *' },
]

const REPORT_TYPES = [
  { value: 'pipeline_digest', label: 'Pipeline Summary',  icon: BarChart2, color: C.accent,  desc: 'Daily summary of pipeline runs, success rates, and row counts' },
  { value: 'quality_summary', label: 'Quality Report',    icon: Shield,    color: C.emerald, desc: 'Weekly data quality scores, failing rules, and schema drift' },
  { value: 'cost_analysis',   label: 'Cost Analysis',     icon: Mail,      color: C.amber,   desc: 'Monthly cost savings from query optimization' },
  { value: 'custom',          label: 'Incident Report',   icon: FileText,  color: C.violet,  desc: 'Custom report with configurable content and SQL queries' },
]

function cronHuman(cron: string): string {
  return CRON_PRESETS.find(p => p.value === cron)?.label ?? cron
}

function DeliveryStatus({ status }: { status: string }) {
  const map: Record<string, { color: string; bg: string }> = {
    sent:    { color: C.emerald, bg: 'rgba(16,185,129,0.12)' },
    failed:  { color: C.red,     bg: 'rgba(239,68,68,0.12)' },
    pending: { color: C.textMuted, bg: 'rgba(100,116,139,0.1)' },
    queued:  { color: C.amber,   bg: 'rgba(245,158,11,0.12)' },
  }
  const s = map[status] || map.pending
  return (
    <span style={{ fontSize: 10, fontWeight: 700, padding: '2px 7px', borderRadius: 5, background: s.bg, color: s.color, letterSpacing: '0.05em', textTransform: 'uppercase' as const }}>
      {status}
    </span>
  )
}

function Toggle({ value, onChange }: { value: boolean; onChange: () => void }) {
  return (
    <button onClick={onChange} style={{ width: 40, height: 22, borderRadius: 11, background: value ? C.accent : C.border, position: 'relative', border: 'none', cursor: 'pointer', transition: 'background 0.2s', flexShrink: 0 }}>
      <span style={{ position: 'absolute', top: 3, left: value ? 21 : 3, width: 16, height: 16, borderRadius: '50%', background: 'white', transition: 'left 0.2s', boxShadow: '0 1px 3px rgba(0,0,0,0.3)' }} />
    </button>
  )
}

function CreateReportModal({ onClose, onSave }: { onClose: () => void; onSave: (data: Record<string, unknown>) => void }) {
  const [form, setForm] = useState({
    name: '', report_type: 'pipeline_digest', description: '',
    schedule_cron: '0 9 * * *', recipients: 'admin@orchestrai.io',
    format: 'html', enabled: true,
  })

  const selectedType = REPORT_TYPES.find(t => t.value === form.report_type)

  const handleSave = () => {
    const recipientList = form.recipients.split(',').map(r => r.trim()).filter(Boolean)
    if (!form.name || recipientList.length === 0) return
    onSave({ ...form, recipients: recipientList })
  }

  const inputStyle = { width: '100%', padding: '9px 12px', borderRadius: 8, fontSize: 13, background: '#09111E', border: `1px solid ${C.border}`, color: C.textPrimary, outline: 'none', boxSizing: 'border-box' as const }
  const labelStyle = { fontSize: 11, color: C.textLabel, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase' as const, display: 'block', marginBottom: 6 }

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 50, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16, background: 'rgba(0,0,0,0.75)' }}>
      <motion.div
        initial={{ opacity: 0, scale: 0.97, y: 10 }} animate={{ opacity: 1, scale: 1, y: 0 }} transition={{ duration: 0.2 }}
        style={{ width: '100%', maxWidth: 520, background: C.card, border: `1px solid ${C.border}`, borderRadius: 16, padding: 24, display: 'flex', flexDirection: 'column', gap: 18 }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <h3 style={{ fontSize: 16, fontWeight: 700, color: C.textPrimary, margin: 0 }}>New Scheduled Report</h3>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: C.textMuted }}><X size={18} /></button>
        </div>

        {/* Type picker */}
        <div>
          <label style={labelStyle}>Report Type</label>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8 }}>
            {REPORT_TYPES.map(t => {
              const Icon = t.icon
              const sel = form.report_type === t.value
              return (
                <button key={t.value} onClick={() => setForm(f => ({ ...f, report_type: t.value }))}
                  style={{ padding: '12px', borderRadius: 10, textAlign: 'left', cursor: 'pointer', background: sel ? t.color + '15' : '#09111E', border: `1px solid ${sel ? t.color : C.border}`, transition: 'all 0.15s' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                    <Icon size={13} style={{ color: t.color }} />
                    <span style={{ fontSize: 12, fontWeight: 600, color: C.textPrimary }}>{t.label}</span>
                  </div>
                  <p style={{ fontSize: 11, color: C.textMuted, margin: 0, lineHeight: 1.4 }}>{t.desc}</p>
                </button>
              )
            })}
          </div>
        </div>

        {/* Name */}
        <div>
          <label style={labelStyle}>Report Name</label>
          <input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
            placeholder="e.g. Morning Pipeline Status" style={inputStyle} />
        </div>

        {/* Schedule */}
        <div>
          <label style={labelStyle}>Schedule</label>
          <select value={form.schedule_cron} onChange={e => setForm(f => ({ ...f, schedule_cron: e.target.value }))} style={{ ...inputStyle, cursor: 'pointer' }}>
            {CRON_PRESETS.map(p => <option key={p.value} value={p.value}>{p.label}</option>)}
          </select>
        </div>

        {/* Recipients */}
        <div>
          <label style={labelStyle}>Recipients <span style={{ color: C.textMuted, textTransform: 'none', letterSpacing: 0, fontWeight: 400 }}>(comma-separated)</span></label>
          <textarea value={form.recipients} onChange={e => setForm(f => ({ ...f, recipients: e.target.value }))}
            placeholder="user@company.com, team@company.com"
            style={{ ...inputStyle, height: 72, resize: 'none' }} />
        </div>

        {/* Format */}
        <div>
          <label style={labelStyle}>Format</label>
          <div style={{ display: 'flex', gap: 10 }}>
            {['html', 'pdf', 'csv'].map(fmt => (
              <label key={fmt} style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', fontSize: 13, color: form.format === fmt ? C.textPrimary : C.textMuted }}>
                <input type="radio" value={fmt} checked={form.format === fmt} onChange={() => setForm(f => ({ ...f, format: fmt }))} />
                {fmt.toUpperCase()}
              </label>
            ))}
          </div>
        </div>

        {/* Enable toggle */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <Toggle value={form.enabled} onChange={() => setForm(f => ({ ...f, enabled: !f.enabled }))} />
          <span style={{ fontSize: 13, color: C.textPrimary }}>Enable immediately</span>
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, paddingTop: 4 }}>
          <button onClick={onClose}
            style={{ padding: '9px 18px', borderRadius: 8, fontSize: 13, background: 'transparent', border: `1px solid ${C.border}`, color: C.textMuted, cursor: 'pointer' }}>
            Cancel
          </button>
          <button onClick={handleSave}
            style={{ padding: '9px 20px', borderRadius: 8, fontSize: 13, fontWeight: 600, background: C.accent, color: 'white', border: 'none', cursor: 'pointer' }}>
            Create Report
          </button>
        </div>
      </motion.div>
    </div>
  )
}

export default function ReportsPage() {
  const qc = useQueryClient()
  const toast = useToast()
  const [showCreate, setShowCreate] = useState(false)
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [sendingId, setSendingId] = useState<string | null>(null)

  const { data: reportsData, isLoading } = useQuery({
    queryKey: ['reports'],
    queryFn: () => apiFetch('/api/reports'),
    refetchInterval: 30000,
  })

  const { data: deliveriesData } = useQuery({
    queryKey: ['reports-deliveries'],
    queryFn: () => apiFetch('/api/reports/deliveries/recent'),
    refetchInterval: 60000,
  })

  const { data: expandedDeliveries } = useQuery({
    queryKey: ['report-deliveries', expandedId],
    queryFn: () => apiFetch(`/api/reports/${expandedId}/deliveries`),
    enabled: !!expandedId,
  })

  const createMutation = useMutation({
    mutationFn: (body: Record<string, unknown>) => apiFetch('/api/reports', { method: 'POST', body: JSON.stringify(body) }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['reports'] }); setShowCreate(false); toast('Report created', 'success') },
    onError: () => toast('Failed to create report', 'error'),
  })

  const toggleMutation = useMutation({
    mutationFn: (id: string) => apiFetch(`/api/reports/${id}/toggle`, { method: 'PATCH' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['reports'] }),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => apiFetch(`/api/reports/${id}`, { method: 'DELETE' }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['reports'] }); toast('Report deleted', 'info') },
  })

  const sendNow = async (id: string) => {
    setSendingId(id)
    try {
      await apiFetch(`/api/reports/${id}/send-now`, { method: 'POST' })
      qc.invalidateQueries({ queryKey: ['reports-deliveries'] })
      toast('Report queued for delivery', 'success')
    } catch { toast('Send failed', 'error') }
    finally { setSendingId(null) }
  }

  const _reportsDown = !isLoading && !reportsData
  const reports: ScheduledReport[] = reportsData?.reports?.length ? reportsData.reports : (_reportsDown ? (DEMO_REPORTS as unknown as ScheduledReport[]) : [])
  const deliveries: Delivery[] = deliveriesData?.deliveries?.length ? deliveriesData.deliveries : (_reportsDown ? (DEMO_DELIVERIES as unknown as Delivery[]) : [])
  const enabledCount = reports.filter(r => r.enabled).length
  const sentCount    = deliveries.filter(d => d.status === 'sent').length
  const failedCount  = deliveries.filter(d => d.status === 'failed').length

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}
      style={{ padding: 24, background: C.bg, minHeight: '100%', display: 'flex', flexDirection: 'column', gap: 24 }}
    >
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700, color: C.textPrimary, margin: '0 0 4px' }}>Scheduled Reports</h1>
          <p style={{ fontSize: 13, color: C.textMuted, margin: 0 }}>Configure automated email reports delivered on a schedule</p>
        </div>
        <button onClick={() => setShowCreate(true)}
          style={{ display: 'flex', alignItems: 'center', gap: 7, padding: '9px 18px', borderRadius: 8, fontSize: 13, fontWeight: 600, background: C.accent, color: 'white', border: 'none', cursor: 'pointer' }}>
          <Plus size={14} /> New Report
        </button>
      </div>

      {/* Stat cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
        {[
          { label: 'Total Reports', value: reports.length, icon: FileText,     color: C.accent },
          { label: 'Active',        value: enabledCount,   icon: CheckCircle2, color: C.emerald },
          { label: 'Sent (recent)', value: sentCount,      icon: Send,         color: C.violet },
          { label: 'Failed',        value: failedCount,    icon: AlertCircle,  color: C.red },
        ].map(c => {
          const Icon = c.icon
          return (
            <div key={c.label} style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, padding: '14px 16px', display: 'flex', alignItems: 'center', gap: 12 }}>
              <div style={{ width: 38, height: 38, borderRadius: 10, background: c.color + '20', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                <Icon size={16} style={{ color: c.color }} />
              </div>
              <div>
                <p style={{ fontSize: 22, fontWeight: 700, color: C.textPrimary, margin: 0 }}>{c.value}</p>
                <p style={{ fontSize: 11, color: C.textMuted, margin: 0 }}>{c.label}</p>
              </div>
            </div>
          )
        })}
      </div>

      {/* Main content */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: 20, alignItems: 'start' }}>
        {/* Active Reports table */}
        <div>
          <p style={{ fontSize: 11, letterSpacing: '0.08em', textTransform: 'uppercase' as const, color: C.textLabel, fontWeight: 600, margin: '0 0 12px' }}>Active Reports</p>

          {isLoading ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {[1,2,3].map(i => <div key={i} style={{ height: 88, borderRadius: 12, background: C.card, opacity: 0.6 }} />)}
            </div>
          ) : reports.length === 0 ? (
            <div style={{ borderRadius: 16, border: `1px solid ${C.border}` }}>
              <EmptyState
                icon={Mail}
                title="No scheduled reports"
                description="Set up automated reports to receive pipeline health summaries, anomaly digests, and cost breakdowns by email."
                action={{ label: 'Schedule Report', onClick: () => setShowCreate(true) }}
              />
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {reports.map(r => {
                const typeInfo = REPORT_TYPES.find(t => t.value === r.report_type)
                const Icon = typeInfo?.icon || FileText
                const isExpanded = expandedId === r.id
                const rowDeliveries: Delivery[] = isExpanded ? (expandedDeliveries?.deliveries || []) : []

                return (
                  <div key={r.id} style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, overflow: 'hidden' }}>
                    <div style={{ padding: '14px 16px', display: 'flex', alignItems: 'flex-start', gap: 14 }}>
                      <div style={{ width: 38, height: 38, borderRadius: 10, background: (typeInfo?.color || C.accent) + '20', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                        <Icon size={16} style={{ color: typeInfo?.color || C.accent }} />
                      </div>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                          <span style={{ fontSize: 14, fontWeight: 600, color: C.textPrimary, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.name}</span>
                          <DeliveryStatus status={r.last_status} />
                          {!r.enabled && (
                            <span style={{ fontSize: 10, fontWeight: 600, padding: '2px 7px', borderRadius: 5, background: 'rgba(100,116,139,0.1)', color: C.textMuted }}>Disabled</span>
                          )}
                        </div>
                        {r.description && <p style={{ fontSize: 12, color: C.textMuted, margin: '0 0 6px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.description}</p>}
                        <div style={{ display: 'flex', alignItems: 'center', gap: 16, fontSize: 11, color: C.textMuted }}>
                          <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}><Calendar size={10} />{cronHuman(r.schedule_cron)}</span>
                          <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}><Mail size={10} />{r.recipients.length} recipient{r.recipients.length !== 1 ? 's' : ''}</span>
                          {r.last_sent_at && (
                            <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}><Clock size={10} />Last: {new Date(r.last_sent_at).toLocaleDateString()}</span>
                          )}
                        </div>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 4, flexShrink: 0 }}>
                        <button onClick={() => sendNow(r.id)} disabled={sendingId === r.id} title="Send now"
                          style={{ padding: 6, borderRadius: 7, background: 'transparent', border: 'none', cursor: 'pointer', color: C.accent, opacity: sendingId === r.id ? 0.5 : 1 }}>
                          {sendingId === r.id ? <RefreshCw size={13} style={{ animation: 'spin 1s linear infinite' }} /> : <Send size={13} />}
                        </button>
                        <Toggle value={r.enabled} onChange={() => toggleMutation.mutate(r.id)} />
                        <button onClick={() => setExpandedId(isExpanded ? null : r.id)}
                          style={{ padding: 6, borderRadius: 7, background: 'transparent', border: 'none', cursor: 'pointer', color: C.textMuted }}>
                          {isExpanded ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                        </button>
                        <button onClick={() => deleteMutation.mutate(r.id)} title="Delete"
                          style={{ padding: 6, borderRadius: 7, background: 'transparent', border: 'none', cursor: 'pointer', color: C.red }}>
                          <Trash2 size={13} />
                        </button>
                      </div>
                    </div>

                    {/* Delivery history (expanded) */}
                    {isExpanded && (
                      <div style={{ borderTop: `1px solid ${C.border}` }}>
                        <div style={{ padding: '8px 16px', background: 'rgba(0,0,0,0.2)' }}>
                          <p style={{ fontSize: 11, letterSpacing: '0.06em', textTransform: 'uppercase' as const, color: C.textLabel, fontWeight: 600, margin: 0 }}>Delivery History</p>
                        </div>
                        {rowDeliveries.length === 0 ? (
                          <p style={{ padding: '12px 16px', fontSize: 12, color: C.textMuted }}>No deliveries yet</p>
                        ) : rowDeliveries.slice(0, 5).map(d => (
                          <div key={d.id} style={{ padding: '10px 16px', display: 'flex', alignItems: 'center', gap: 10, borderBottom: `1px solid ${C.border}` }}>
                            <DeliveryStatus status={d.status} />
                            <span style={{ fontSize: 12, color: C.textPrimary, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{d.subject}</span>
                            <span style={{ fontSize: 11, color: C.textMuted, flexShrink: 0 }}>{d.sent_at ? new Date(d.sent_at).toLocaleString() : '—'}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* Recent deliveries sidebar */}
        <div>
          <p style={{ fontSize: 11, letterSpacing: '0.08em', textTransform: 'uppercase' as const, color: C.textLabel, fontWeight: 600, margin: '0 0 12px' }}>Recent Deliveries</p>
          <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, overflow: 'hidden' }}>
            {deliveries.length === 0 ? (
              <p style={{ padding: '24px', textAlign: 'center', fontSize: 12, color: C.textMuted }}>No deliveries yet</p>
            ) : deliveries.slice(0, 12).map(d => (
              <div key={d.id} style={{ padding: '10px 14px', display: 'flex', alignItems: 'flex-start', gap: 10, borderBottom: `1px solid ${C.border}` }}>
                <div style={{ width: 24, height: 24, borderRadius: '50%', background: d.status === 'sent' ? 'rgba(16,185,129,0.15)' : 'rgba(239,68,68,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, marginTop: 2 }}>
                  {d.status === 'sent' ? <CheckCircle2 size={12} style={{ color: C.emerald }} /> : <AlertCircle size={12} style={{ color: C.red }} />}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <p style={{ fontSize: 12, fontWeight: 500, color: C.textPrimary, margin: '0 0 2px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{d.report_name || d.subject}</p>
                  {d.sent_at && <p style={{ fontSize: 10, color: C.textMuted, margin: 0 }}>{new Date(d.sent_at).toLocaleString()}</p>}
                  {d.error_message && <p style={{ fontSize: 10, color: C.red, margin: '2px 0 0', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{d.error_message}</p>}
                </div>
              </div>
            ))}
          </div>

          <div style={{ marginTop: 12, padding: 14, borderRadius: 12, background: 'rgba(14,165,233,0.06)', border: `1px solid rgba(14,165,233,0.2)` }}>
            <p style={{ fontSize: 12, fontWeight: 600, color: C.accent, margin: '0 0 4px' }}>SMTP Configuration</p>
            <p style={{ fontSize: 11, color: C.textMuted, margin: '0 0 8px', lineHeight: 1.5 }}>Configure SMTP in Settings → Notifications to enable real email delivery.</p>
            <a href="/settings" style={{ fontSize: 12, color: C.accent, textDecoration: 'none' }}>Open Settings →</a>
          </div>
        </div>
      </div>

      {showCreate && (
        <CreateReportModal onClose={() => setShowCreate(false)} onSave={(data) => createMutation.mutate(data)} />
      )}
    </motion.div>
  )
}
