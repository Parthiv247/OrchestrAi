'use client'
import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  User, Bell, Database, Key, Save, CheckCircle2,
  Users, Plus, Trash2, Copy, RefreshCw, ExternalLink, Activity, Mail,
  Check, X, Plug, FileText, Shield,
} from 'lucide-react'
import { useToast } from '@/components/ui/Toaster'
import { formatDistanceToNow } from 'date-fns'
import { useRouter } from 'next/navigation'
import api from '@/lib/api'
import type { TeamMember, ApiToken, AlertRule, NotificationHistory, AuditLogEntry, LucideIcon } from '@/lib/types'

const C = {
  bg: '#080F1C', card: '#0F2540', border: '#1A3A5C',
  accent: '#0EA5E9', emerald: '#10B981', amber: '#F59E0B', red: '#EF4444', violet: '#7C3AED',
  textPrimary: '#F1F5F9', textMuted: '#64748B', textLabel: '#4B6B8E',
}

const API = '/api/settings'
const NOTIF_API = '/api/notifications'

const TABS = ['General', 'Team', 'API Tokens', 'Notifications', 'Integrations', 'Audit Log'] as const
type Tab = typeof TABS[number]

const TAB_META: Record<Tab, { icon: LucideIcon; desc: string }> = {
  General:       { icon: User,     desc: 'Profile and workspace settings' },
  Team:          { icon: Users,    desc: 'Manage team members and roles' },
  'API Tokens':  { icon: Key,      desc: 'Manage API access tokens' },
  Notifications: { icon: Bell,     desc: 'Alert channels and rules' },
  Integrations:  { icon: Plug,     desc: 'Connected services' },
  'Audit Log':   { icon: FileText, desc: 'Activity history' },
}

const inputStyle = (extra?: React.CSSProperties) => ({
  width: '100%', padding: '9px 12px', borderRadius: 8, fontSize: 13,
  background: '#09111E', border: `1px solid ${C.border}`, color: C.textPrimary,
  outline: 'none', boxSizing: 'border-box' as const, ...extra,
})

const labelStyle: React.CSSProperties = {
  fontSize: 11, color: C.textLabel, fontWeight: 600, letterSpacing: '0.06em',
  textTransform: 'uppercase', display: 'block', marginBottom: 6,
}

function Toggle({ value, onChange }: { value: boolean; onChange: (v: boolean) => void }) {
  return (
    <button onClick={() => onChange(!value)}
      style={{ width: 40, height: 22, borderRadius: 11, background: value ? C.accent : C.border, position: 'relative', border: 'none', cursor: 'pointer', transition: 'background 0.2s', flexShrink: 0 }}>
      <span style={{ position: 'absolute', top: 3, left: value ? 21 : 3, width: 16, height: 16, borderRadius: '50%', background: 'white', transition: 'left 0.2s', boxShadow: '0 1px 3px rgba(0,0,0,0.3)' }} />
    </button>
  )
}

function RoleBadge({ role }: { role: string }) {
  const map: Record<string, { color: string; bg: string }> = {
    admin:  { color: C.violet, bg: 'rgba(124,58,237,0.15)' },
    editor: { color: C.accent, bg: 'rgba(14,165,233,0.15)' },
    viewer: { color: C.textMuted, bg: 'rgba(100,116,139,0.1)' },
  }
  const s = map[role] || map.viewer
  return (
    <span style={{ fontSize: 10, fontWeight: 700, padding: '2px 7px', borderRadius: 5, background: s.bg, color: s.color, letterSpacing: '0.05em', textTransform: 'uppercase' as const }}>{role}</span>
  )
}

function SaveBtn({ onClick, loading }: { onClick: () => void; loading?: boolean }) {
  const [saved, setSaved] = useState(false)
  return (
    <div style={{ display: 'flex', justifyContent: 'flex-end', paddingTop: 8 }}>
      <button onClick={() => { onClick(); setSaved(true); setTimeout(() => setSaved(false), 2000) }} disabled={loading}
        style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '9px 20px', borderRadius: 8, fontSize: 13, fontWeight: 600, color: 'white', cursor: 'pointer', border: 'none', background: 'linear-gradient(135deg, #0EA5E9, #7C3AED)', opacity: loading ? 0.6 : 1 }}>
        {loading ? <RefreshCw size={14} style={{ animation: 'spin 1s linear infinite' }} />
          : saved ? <><CheckCircle2 size={14} /> Saved</>
          : <><Save size={14} /> Save Changes</>}
      </button>
    </div>
  )
}

// ── GENERAL TAB ───────────────────────────────────────────────────────────────
function GeneralTab({ onSave }: { onSave: () => void }) {
  const [form, setForm] = useState({
    name: 'Admin User', email: 'admin@orchestrai.io', org: 'OrchestrAI', timezone: 'UTC',
  })
  useEffect(() => {
    try {
      setForm({
        name:     localStorage.getItem('profile_name')     || 'Admin User',
        email:    localStorage.getItem('profile_email')    || 'admin@orchestrai.io',
        org:      localStorage.getItem('profile_org')      || 'OrchestrAI',
        timezone: localStorage.getItem('profile_timezone') || 'UTC',
      })
    } catch {}
  }, [])
  const [deleteConfirm, setDeleteConfirm] = useState('')

  const initials = form.name.split(' ').map((p: string) => p[0]).join('').toUpperCase().slice(0, 2) || 'A'

  const handleSave = () => {
    try {
      localStorage.setItem('profile_name', form.name)
      localStorage.setItem('profile_email', form.email)
      localStorage.setItem('profile_org', form.org)
      localStorage.setItem('profile_timezone', form.timezone)
    } catch {}
    onSave()
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Avatar + identity */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, padding: 16, borderRadius: 12, background: '#09111E', border: `1px solid ${C.border}` }}>
        <div style={{ width: 56, height: 56, borderRadius: '50%', background: 'linear-gradient(135deg, #0EA5E9, #7C3AED)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 20, fontWeight: 700, color: 'white', flexShrink: 0 }}>
          {initials}
        </div>
        <div>
          <p style={{ fontWeight: 600, color: C.textPrimary, margin: '0 0 2px' }}>{form.name}</p>
          <p style={{ fontSize: 12, color: C.textMuted, margin: '0 0 6px' }}>{form.email}</p>
          <RoleBadge role="admin" />
        </div>
      </div>

      {[{ key: 'name', label: 'Full Name', type: 'text' }, { key: 'email', label: 'Email', type: 'email' }, { key: 'org', label: 'Organization', type: 'text' }].map(f => (
        <div key={f.key}>
          <label style={labelStyle}>{f.label}</label>
          <input type={f.type} value={(form as Record<string, string>)[f.key]} onChange={e => setForm(p => ({ ...p, [f.key]: e.target.value }))} style={inputStyle()} />
        </div>
      ))}

      <div>
        <label style={labelStyle}>Timezone</label>
        <select value={form.timezone} onChange={e => setForm(p => ({ ...p, timezone: e.target.value }))} style={{ ...inputStyle(), cursor: 'pointer' }}>
          {['UTC','America/New_York','America/Los_Angeles','Europe/London','Asia/Kolkata','Asia/Tokyo'].map(tz => <option key={tz}>{tz}</option>)}
        </select>
      </div>

      <SaveBtn onClick={handleSave} />

      {/* Danger zone */}
      <div style={{ borderRadius: 12, padding: 16, border: `1px solid rgba(239,68,68,0.35)`, background: 'rgba(239,68,68,0.05)', marginTop: 8 }}>
        <p style={{ fontSize: 13, fontWeight: 700, color: C.red, margin: '0 0 6px' }}>Danger Zone</p>
        <p style={{ fontSize: 12, color: C.textMuted, margin: '0 0 12px' }}>Permanently delete this workspace and all its data. This cannot be undone.</p>
        <label style={{ ...labelStyle, textTransform: 'none', letterSpacing: 0, fontWeight: 400, color: C.textMuted }}>
          Type <strong style={{ color: C.textPrimary }}>OrchestrAI</strong> to confirm
        </label>
        <div style={{ display: 'flex', gap: 10 }}>
          <input value={deleteConfirm} onChange={e => setDeleteConfirm(e.target.value)} placeholder="OrchestrAI" style={inputStyle()} />
          <button disabled={deleteConfirm !== 'OrchestrAI'}
            style={{ padding: '9px 16px', borderRadius: 8, fontSize: 13, fontWeight: 600, background: deleteConfirm === 'OrchestrAI' ? C.red : 'rgba(239,68,68,0.1)', color: deleteConfirm === 'OrchestrAI' ? 'white' : C.red, border: `1px solid rgba(239,68,68,0.3)`, cursor: deleteConfirm === 'OrchestrAI' ? 'pointer' : 'not-allowed', whiteSpace: 'nowrap', flexShrink: 0 }}>
            Delete Workspace
          </button>
        </div>
      </div>
    </div>
  )
}

// ── TEAM TAB ──────────────────────────────────────────────────────────────────
function TeamTab() {
  const qc = useQueryClient()
  const toast = useToast()
  const [showInvite, setShowInvite] = useState(false)
  const [inv, setInv] = useState({ name: '', email: '', role: 'viewer' })
  const [inviting, setInviting] = useState(false)
  const { data, isLoading } = useQuery({ queryKey: ['team'], queryFn: () => api.get(`${API}/team`).then(r => r.data), staleTime: 30_000 })
  const members = data?.members || []

  const handleInvite = async () => {
    setInviting(true)
    try {
      const res = await api.post(`${API}/team/invite`, inv)
      if (!res.data) throw new Error('Invite failed')
      qc.invalidateQueries({ queryKey: ['team'] }); toast('Invited ' + inv.email, 'success')
      setShowInvite(false); setInv({ name: '', email: '', role: 'viewer' })
    } catch (e: unknown) { toast((e as Error).message || 'Invite failed', 'error') } finally { setInviting(false) }
  }

  const handleRemove = async (id: string, email: string) => {
    await api.delete(`${API}/team/${id}`)
    qc.invalidateQueries({ queryKey: ['team'] }); toast('Removed ' + email, 'info')
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <p style={{ fontSize: 14, fontWeight: 600, color: C.textPrimary, margin: 0 }}>
          Team Members <span style={{ color: C.textMuted, fontWeight: 400 }}>({members.length})</span>
        </p>
        <button onClick={() => setShowInvite(v => !v)}
          style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '7px 14px', borderRadius: 8, fontSize: 12, fontWeight: 600, background: C.accent, color: 'white', border: 'none', cursor: 'pointer' }}>
          <Plus size={12} /> Invite Member
        </button>
      </div>

      {showInvite && (
        <div style={{ borderRadius: 12, padding: 16, background: '#09111E', border: `1px solid ${C.border}`, display: 'flex', flexDirection: 'column', gap: 12 }}>
          <p style={{ fontSize: 13, fontWeight: 600, color: C.textPrimary, margin: 0 }}>Invite new member</p>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <input value={inv.name} onChange={e => setInv(p => ({ ...p, name: e.target.value }))} placeholder="Full name" style={inputStyle()} />
            <input value={inv.email} onChange={e => setInv(p => ({ ...p, email: e.target.value }))} placeholder="Email" type="email" style={inputStyle()} />
          </div>
          <div style={{ display: 'flex', gap: 10 }}>
            <select value={inv.role} onChange={e => setInv(p => ({ ...p, role: e.target.value }))} style={{ ...inputStyle(), flex: 1, cursor: 'pointer' }}>
              <option value="viewer">Viewer — read-only</option>
              <option value="editor">Editor — can run pipelines</option>
              <option value="admin">Admin — full access</option>
            </select>
            <button onClick={handleInvite} disabled={inviting || !inv.email}
              style={{ padding: '9px 16px', borderRadius: 8, fontSize: 13, fontWeight: 600, background: C.accent, color: 'white', border: 'none', cursor: 'pointer', opacity: inviting || !inv.email ? 0.6 : 1, flexShrink: 0 }}>
              {inviting ? 'Inviting…' : 'Send Invite'}
            </button>
            <button onClick={() => setShowInvite(false)}
              style={{ padding: '9px', borderRadius: 8, background: 'transparent', border: `1px solid ${C.border}`, cursor: 'pointer', color: C.textMuted }}>
              <X size={14} />
            </button>
          </div>
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {isLoading ? [1,2,3].map(i => <div key={i} style={{ height: 56, borderRadius: 10, background: C.border, opacity: 0.4 }} />) :
          members.map((m: TeamMember) => (
            <div key={m.id} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 14px', borderRadius: 10, border: `1px solid ${C.border}` }}>
              <div style={{ width: 36, height: 36, borderRadius: '50%', background: 'linear-gradient(135deg, #0EA5E9, #7C3AED)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, fontWeight: 700, color: 'white', flexShrink: 0 }}>{m.initials}</div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 2 }}>
                  <p style={{ fontSize: 13, fontWeight: 600, color: C.textPrimary, margin: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{m.name}</p>
                  <RoleBadge role={m.role} />
                  {m.status === 'invited' && <span style={{ fontSize: 10, fontWeight: 600, padding: '2px 6px', borderRadius: 5, background: 'rgba(245,158,11,0.12)', color: C.amber }}>Pending</span>}
                </div>
                <p style={{ fontSize: 11, color: C.textMuted, margin: 0 }}>{m.email}</p>
              </div>
              {m.last_active && <span style={{ fontSize: 11, color: C.textMuted, flexShrink: 0 }}>{formatDistanceToNow(new Date(m.last_active), { addSuffix: true })}</span>}
              {m.email !== 'admin@orchestrai.io' && (
                <button onClick={() => handleRemove(String(m.id), m.email)} style={{ padding: 6, borderRadius: 7, background: 'transparent', border: 'none', cursor: 'pointer', color: C.red }}>
                  <Trash2 size={13} />
                </button>
              )}
            </div>
          ))
        }
      </div>
    </div>
  )
}

// ── API TOKENS TAB ────────────────────────────────────────────────────────────
function ApiTokensTab() {
  const qc = useQueryClient()
  const toast = useToast()
  const [showCreate, setShowCreate] = useState(false)
  const [nf, setNf] = useState({ name: '', scopes: 'read', expires_days: '' })
  const [creating, setCreating] = useState(false)
  const [newToken, setNewToken] = useState('')
  const [copied, setCopied] = useState(false)
  const { data, isLoading } = useQuery({ queryKey: ['api-tokens'], queryFn: () => api.get(`${API}/tokens`).then(r => r.data), staleTime: 30_000 })
  const tokens = data?.tokens || []

  const handleCreate = async () => {
    setCreating(true)
    try {
      const res = await api.post(`${API}/tokens`, { name: nf.name, scopes: nf.scopes, expires_days: nf.expires_days ? parseInt(nf.expires_days) : null })
      const d = res.data; setNewToken(d.token)
      qc.invalidateQueries({ queryKey: ['api-tokens'] }); setShowCreate(false)
    } catch { toast('Failed to create token', 'error') } finally { setCreating(false) }
  }

  const handleRevoke = async (id: string) => {
    await api.delete(`${API}/tokens/${id}`)
    qc.invalidateQueries({ queryKey: ['api-tokens'] }); toast('Token revoked', 'info')
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <p style={{ fontSize: 14, fontWeight: 600, color: C.textPrimary, margin: 0 }}>
          API Tokens <span style={{ color: C.textMuted, fontWeight: 400 }}>({tokens.filter((t: ApiToken) => !t.revoked).length} active)</span>
        </p>
        <button onClick={() => setShowCreate(v => !v)}
          style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '7px 14px', borderRadius: 8, fontSize: 12, fontWeight: 600, background: C.accent, color: 'white', border: 'none', cursor: 'pointer' }}>
          <Plus size={12} /> Generate Token
        </button>
      </div>

      {newToken && (
        <div style={{ borderRadius: 12, padding: 16, background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.3)', display: 'flex', flexDirection: 'column', gap: 10 }}>
          <p style={{ fontSize: 13, fontWeight: 600, color: C.emerald, margin: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
            <CheckCircle2 size={14} /> Token generated — copy it now, it won&apos;t be shown again
          </p>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <code style={{ flex: 1, fontSize: 12, fontFamily: 'ui-monospace, monospace', color: '#86efac', background: 'rgba(0,0,0,0.2)', padding: '8px 12px', borderRadius: 7, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{newToken}</code>
            <button onClick={() => { navigator.clipboard.writeText(newToken); setCopied(true); setTimeout(() => setCopied(false), 2000) }}
              style={{ padding: 8, borderRadius: 7, background: 'transparent', border: 'none', cursor: 'pointer', color: C.textMuted }}>
              {copied ? <Check size={14} style={{ color: C.emerald }} /> : <Copy size={14} />}
            </button>
          </div>
          <button onClick={() => setNewToken('')} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 12, color: C.textMuted, alignSelf: 'flex-start' }}>Dismiss</button>
        </div>
      )}

      {showCreate && (
        <div style={{ borderRadius: 12, padding: 16, background: '#09111E', border: `1px solid ${C.border}`, display: 'flex', flexDirection: 'column', gap: 12 }}>
          <p style={{ fontSize: 13, fontWeight: 600, color: C.textPrimary, margin: 0 }}>New API Token</p>
          <input value={nf.name} onChange={e => setNf(p => ({ ...p, name: e.target.value }))} placeholder="Token name (e.g. CI/CD pipeline)" style={inputStyle()} />
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <div>
              <label style={labelStyle}>Scope</label>
              <select value={nf.scopes} onChange={e => setNf(p => ({ ...p, scopes: e.target.value }))} style={{ ...inputStyle(), cursor: 'pointer' }}>
                <option value="read">Read only</option><option value="write">Read + Write</option><option value="admin">Admin</option>
              </select>
            </div>
            <div>
              <label style={labelStyle}>Expires (days)</label>
              <input value={nf.expires_days} onChange={e => setNf(p => ({ ...p, expires_days: e.target.value }))} type="number" placeholder="Never" style={inputStyle()} />
            </div>
          </div>
          <div style={{ display: 'flex', gap: 10 }}>
            <button onClick={handleCreate} disabled={creating || !nf.name}
              style={{ flex: 1, padding: '9px 0', borderRadius: 8, fontSize: 13, fontWeight: 600, background: C.accent, color: 'white', border: 'none', cursor: 'pointer', opacity: creating || !nf.name ? 0.6 : 1 }}>
              {creating ? 'Generating…' : 'Generate'}
            </button>
            <button onClick={() => setShowCreate(false)}
              style={{ padding: '9px 14px', borderRadius: 8, fontSize: 13, background: 'transparent', border: `1px solid ${C.border}`, cursor: 'pointer', color: C.textMuted }}>
              Cancel
            </button>
          </div>
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {isLoading ? [1,2].map(i => <div key={i} style={{ height: 54, borderRadius: 10, background: C.border, opacity: 0.4 }} />) :
          tokens.length === 0 ? <p style={{ textAlign: 'center', padding: '32px 0', fontSize: 13, color: C.textMuted }}>No API tokens yet</p> :
          tokens.map((t: ApiToken) => (
            <div key={t.id} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 14px', borderRadius: 10, border: `1px solid ${C.border}`, opacity: t.revoked ? 0.5 : 1 }}>
              <Key size={14} style={{ color: t.revoked ? C.textMuted : C.amber, flexShrink: 0 }} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 2 }}>
                  <p style={{ fontSize: 13, fontWeight: 600, color: C.textPrimary, margin: 0 }}>{t.name}</p>
                  <span style={{ fontSize: 10, fontFamily: 'ui-monospace, monospace', padding: '2px 6px', borderRadius: 5, background: '#09111E', color: C.textMuted }}>{t.scopes}</span>
                  {t.revoked && <span style={{ fontSize: 10, color: C.red }}>revoked</span>}
                </div>
                <p style={{ fontSize: 11, fontFamily: 'ui-monospace, monospace', color: C.textMuted, margin: 0 }}>{t.token_preview}</p>
              </div>
              <span style={{ fontSize: 11, color: C.textMuted, flexShrink: 0 }}>{t.created_at ? formatDistanceToNow(new Date(t.created_at), { addSuffix: true }) : ''}</span>
              {!t.revoked && (
                <button onClick={() => handleRevoke(String(t.id))} style={{ padding: 6, borderRadius: 7, background: 'transparent', border: 'none', cursor: 'pointer', color: C.red }}>
                  <Trash2 size={13} />
                </button>
              )}
            </div>
          ))
        }
      </div>
      <p style={{ fontSize: 11, color: C.textMuted }}>
        Pass token as <code style={{ fontFamily: 'ui-monospace, monospace', background: 'rgba(0,0,0,0.2)', padding: '1px 5px', borderRadius: 4 }}>Authorization: Bearer oai_...</code>
      </p>
    </div>
  )
}

// ── NOTIFICATIONS TAB ─────────────────────────────────────────────────────────
const CHANNEL_COLORS: Record<string, string> = { slack: '#4ade80', email: '#38BDF8', pagerduty: '#f472b6' }
const CONDITION_LABELS: Record<string, string> = {
  pipeline_failure: 'Pipeline Failure', anomaly: 'Anomaly Detected',
  cost_threshold: 'Cost Threshold', null_spike: 'Null Spike',
  row_count_drop: 'Row Count Drop', custom: 'Custom',
}

function NotificationsTab() {
  const toast = useToast()
  const qc = useQueryClient()
  const [slackUrl, setSlackUrl] = useState('')
  const [emailFrom, setEmailFrom] = useState('')
  const [smtpHost, setSmtpHost] = useState('')
  const [smtpPort, setSmtpPort] = useState('587')
  const [smtpUser, setSmtpUser] = useState('')
  const [pagerdutyKey, setPagerdutyKey] = useState('')
  const [testing, setTesting] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [togglingRule, setTogglingRule] = useState<string | null>(null)
  const [dispatchSubject, setDispatchSubject] = useState('')
  const [dispatchBody, setDispatchBody] = useState('')
  const [dispatching, setDispatching] = useState(false)

  const { data: configData } = useQuery({ queryKey: ['notif-config'], queryFn: () => api.get(`${API}/notifications`).then(r => r.data), staleTime: 60_000 })
  useEffect(() => {
    if (configData?.config) {
      setSlackUrl(configData.config.slack_webhook_url || '')
      setEmailFrom(configData.config.email_from || '')
      setSmtpHost(configData.config.email_smtp_host || '')
      setSmtpPort(String(configData.config.email_smtp_port || 587))
      setSmtpUser(configData.config.email_smtp_user || '')
    }
  }, [configData])

  const { data: rulesData, isLoading: rulesLoading } = useQuery({ queryKey: ['alert-rules'], queryFn: () => api.get(`${NOTIF_API}/alert-rules`).then(r => r.data) })
  const alertRules = rulesData?.rules || []

  const { data: historyData } = useQuery({ queryKey: ['notif-history'], queryFn: () => api.get(`${NOTIF_API}/history`).then(r => r.data), refetchInterval: 30_000 })
  const history = historyData?.history || []

  const handleSave = async () => {
    setSaving(true)
    await api.put(`${API}/notifications`, { slack_webhook_url: slackUrl, email_from: emailFrom, email_smtp_host: smtpHost, email_smtp_port: Number(smtpPort), email_smtp_user: smtpUser, pagerduty_key: pagerdutyKey })
    setSaving(false); toast('Notification config saved', 'success')
  }

  const handleTest = async (channel: string) => {
    setTesting(channel)
    try {
      const res = await api.post(`${NOTIF_API}/test`, { channel })
      const d = res.data
      if (d.success) toast(`${channel} test sent`, 'success')
      else toast(d.message || `${channel} test failed`, 'error')
    } catch { toast('Test failed', 'error') } finally { setTesting(null) }
  }

  const handleToggleRule = async (id: string) => {
    setTogglingRule(id)
    await api.post(`${NOTIF_API}/alert-rules/${id}/toggle`)
    qc.invalidateQueries({ queryKey: ['alert-rules'] })
    setTogglingRule(null)
  }

  const handleDeleteRule = async (id: string) => {
    await api.delete(`${NOTIF_API}/alert-rules/${id}`)
    qc.invalidateQueries({ queryKey: ['alert-rules'] }); toast('Rule deleted', 'success')
  }

  const handleDispatch = async () => {
    if (!dispatchSubject.trim()) return
    setDispatching(true)
    try {
      const res = await api.post(`${NOTIF_API}/dispatch`, { subject: dispatchSubject, body: dispatchBody || dispatchSubject, severity: 'info', channels: ['slack'] })
      const d = res.data
      const slackResult = d.results?.slack
      if (slackResult?.ok) toast('Alert dispatched via Slack', 'success')
      else toast(slackResult?.message || 'Dispatch failed', 'error')
      setDispatchSubject(''); setDispatchBody('')
      qc.invalidateQueries({ queryKey: ['notif-history'] })
    } catch { toast('Dispatch failed', 'error') } finally { setDispatching(false) }
  }

  const sectionTitle = (text: string) => (
    <p style={{ fontSize: 13, fontWeight: 700, color: C.textPrimary, margin: '0 0 12px', display: 'flex', alignItems: 'center', gap: 6 }}>{text}</p>
  )

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 28 }}>
      {/* Slack */}
      <div>
        {sectionTitle('💬 Slack Webhook')}
        <div style={{ display: 'flex', gap: 8 }}>
          <input value={slackUrl} onChange={e => setSlackUrl(e.target.value)} placeholder="https://hooks.slack.com/services/..." style={{ ...inputStyle(), fontFamily: 'ui-monospace, monospace', flex: 1 }} />
          <button onClick={() => handleTest('slack')} disabled={testing === 'slack' || !slackUrl}
            style={{ padding: '9px 14px', borderRadius: 8, fontSize: 13, border: `1px solid ${C.border}`, background: 'transparent', color: C.textMuted, cursor: 'pointer', opacity: testing === 'slack' || !slackUrl ? 0.5 : 1, flexShrink: 0 }}>
            {testing === 'slack' ? <RefreshCw size={13} style={{ animation: 'spin 1s linear infinite' }} /> : 'Test'}
          </button>
        </div>
      </div>

      {/* Email SMTP */}
      <div>
        {sectionTitle('📧 Email (SMTP)')}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
          {[
            { label: 'From address', value: emailFrom, set: setEmailFrom, placeholder: 'alerts@company.com', type: 'email' },
            { label: 'SMTP Host',    value: smtpHost,  set: setSmtpHost,  placeholder: 'smtp.sendgrid.net', type: 'text' },
            { label: 'SMTP Port',    value: smtpPort,  set: setSmtpPort,  placeholder: '587', type: 'number' },
            { label: 'SMTP Username',value: smtpUser,  set: setSmtpUser,  placeholder: 'apikey', type: 'text' },
          ].map(f => (
            <div key={f.label}>
              <label style={labelStyle}>{f.label}</label>
              <input value={f.value} onChange={e => f.set(e.target.value)} placeholder={f.placeholder} type={f.type} style={inputStyle()} />
            </div>
          ))}
        </div>
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 8 }}>
          <button onClick={() => handleTest('email')} disabled={testing === 'email' || !smtpHost}
            style={{ padding: '7px 14px', borderRadius: 7, fontSize: 12, border: `1px solid ${C.border}`, background: 'transparent', color: C.textMuted, cursor: 'pointer', opacity: testing === 'email' || !smtpHost ? 0.5 : 1 }}>
            Test Email
          </button>
        </div>
      </div>

      {/* PagerDuty */}
      <div>
        {sectionTitle('📟 PagerDuty')}
        <div style={{ display: 'flex', gap: 8 }}>
          <input value={pagerdutyKey} onChange={e => setPagerdutyKey(e.target.value)} placeholder="Integration key (Events API v2)" type="password" style={{ ...inputStyle(), fontFamily: 'ui-monospace, monospace', flex: 1 }} />
          <button onClick={() => handleTest('pagerduty')} disabled={testing === 'pagerduty' || !pagerdutyKey}
            style={{ padding: '9px 14px', borderRadius: 8, fontSize: 13, border: `1px solid ${C.border}`, background: 'transparent', color: C.textMuted, cursor: 'pointer', opacity: testing === 'pagerduty' || !pagerdutyKey ? 0.5 : 1, flexShrink: 0 }}>
            {testing === 'pagerduty' ? <RefreshCw size={13} style={{ animation: 'spin 1s linear infinite' }} /> : 'Test'}
          </button>
        </div>
      </div>

      <SaveBtn onClick={handleSave} loading={saving} />

      {/* Alert Rules */}
      <div>
        {sectionTitle('Alert Rules')}
        {rulesLoading ? [1,2,3].map(i => <div key={i} style={{ height: 44, borderRadius: 8, background: C.border, opacity: 0.3, marginBottom: 8 }} />) :
          alertRules.map((rule: AlertRule) => (
            <div key={rule.id} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 0', borderBottom: `1px solid ${C.border}` }}>
              <Toggle value={rule.enabled ?? false} onChange={() => handleToggleRule(String(rule.id))} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <p style={{ fontSize: 13, fontWeight: 500, color: C.textPrimary, margin: '0 0 3px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{rule.name}</p>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ fontSize: 10, fontFamily: 'ui-monospace, monospace', padding: '1px 5px', borderRadius: 4, background: '#09111E', color: C.textMuted }}>{CONDITION_LABELS[rule.condition ?? ''] || rule.condition}</span>
                  <span style={{ fontSize: 10, fontWeight: 600, padding: '1px 5px', borderRadius: 4, background: (CHANNEL_COLORS[rule.channel ?? ''] || '#94a3b8') + '20', color: CHANNEL_COLORS[rule.channel ?? ''] || '#94a3b8' }}>{rule.channel}</span>
                  {(rule.fire_count ?? 0) > 0 && <span style={{ fontSize: 10, color: C.textMuted }}>fired {rule.fire_count}×</span>}
                </div>
              </div>
              <button onClick={() => handleDeleteRule(String(rule.id))} style={{ padding: 6, borderRadius: 7, background: 'transparent', border: 'none', cursor: 'pointer', color: C.red }}>
                <Trash2 size={13} />
              </button>
            </div>
          ))
        }
      </div>

      {/* Manual dispatch */}
      <div>
        {sectionTitle('Send Alert Now')}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <input value={dispatchSubject} onChange={e => setDispatchSubject(e.target.value)} placeholder="Alert subject…" style={inputStyle()} />
          <textarea value={dispatchBody} onChange={e => setDispatchBody(e.target.value)} placeholder="Optional message body…" rows={2} style={{ ...inputStyle(), resize: 'none' }} />
          <button onClick={handleDispatch} disabled={dispatching || !dispatchSubject.trim()}
            style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '9px 16px', borderRadius: 8, fontSize: 13, fontWeight: 600, background: C.accent, color: 'white', border: 'none', cursor: 'pointer', opacity: dispatching || !dispatchSubject.trim() ? 0.5 : 1, width: 'fit-content' }}>
            {dispatching ? <RefreshCw size={13} style={{ animation: 'spin 1s linear infinite' }} /> : <Bell size={13} />}
            Dispatch to Slack
          </button>
        </div>
      </div>

      {/* Notification history */}
      {history.length > 0 && (
        <div>
          {sectionTitle('Recent Notifications')}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {history.slice(0, 8).map((h: NotificationHistory) => (
              <div key={h.id} style={{ display: 'flex', alignItems: 'flex-start', gap: 10, padding: '10px 12px', borderRadius: 8, background: '#09111E', border: `1px solid ${C.border}` }}>
                <span style={{ fontSize: 10, fontWeight: 700, padding: '2px 6px', borderRadius: 4, background: (CHANNEL_COLORS[h.channel ?? ''] || '#94a3b8') + '20', color: CHANNEL_COLORS[h.channel ?? ''] || '#94a3b8', flexShrink: 0, marginTop: 1 }}>{h.channel}</span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <p style={{ fontSize: 12, color: C.textPrimary, margin: '0 0 2px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{h.subject}</p>
                  <p style={{ fontSize: 10, color: C.textMuted, margin: 0 }}>{h.sent_at ? new Date(h.sent_at).toLocaleString() : ''}</p>
                </div>
                <span style={{ fontSize: 10, color: h.status === 'sent' ? C.emerald : C.red, flexShrink: 0 }}>{h.status}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ── INTEGRATIONS TAB ──────────────────────────────────────────────────────────
const INTEGRATIONS = [
  { name: 'GitHub',       emoji: '🐙', desc: 'Sync pipelines with GitHub repos and trigger on commits.', connected: false },
  { name: 'Slack',        emoji: '💬', desc: 'Send alerts and reports directly to Slack channels.',      connected: true  },
  { name: 'Snowflake',    emoji: '❄️', desc: 'Native Snowflake connector for data warehouse operations.', connected: true  },
  { name: 'Google Sheets',emoji: '📊', desc: 'Read from and write to Google Sheets as a data source.',  connected: false },
  { name: 'dbt Cloud',    emoji: '🔧', desc: 'Trigger dbt Cloud jobs and sync run results.',             connected: false },
  { name: 'BigQuery',     emoji: '☁️', desc: 'Google BigQuery as a destination or source connector.',    connected: false },
]

function IntegrationsTab() {
  const [connected, setConnected] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(INTEGRATIONS.map(i => [i.name, i.connected]))
  )
  const toast = useToast()
  const router = useRouter()

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <p style={{ fontSize: 13, color: C.textMuted, margin: 0 }}>Connect OrchestrAI to your existing tools and data sources.</p>
      <button onClick={() => router.push('/connectors')}
        style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '9px 16px', borderRadius: 8, fontSize: 13, fontWeight: 600, background: C.accent, color: 'white', border: 'none', cursor: 'pointer', width: 'fit-content' }}>
        Open Connector Gallery <ExternalLink size={13} />
      </button>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        {INTEGRATIONS.map(intg => (
          <div key={intg.name} style={{ background: '#09111E', border: `1px solid ${connected[intg.name] ? 'rgba(16,185,129,0.35)' : C.border}`, borderRadius: 12, padding: '14px 16px', display: 'flex', alignItems: 'flex-start', gap: 12 }}>
            <span style={{ fontSize: 24, flexShrink: 0 }}>{intg.emoji}</span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                <p style={{ fontSize: 13, fontWeight: 600, color: C.textPrimary, margin: 0 }}>{intg.name}</p>
                {connected[intg.name] && <span style={{ fontSize: 10, color: C.emerald, fontWeight: 700 }}>● Connected</span>}
              </div>
              <p style={{ fontSize: 11, color: C.textMuted, margin: '0 0 10px', lineHeight: 1.5 }}>{intg.desc}</p>
              <button onClick={() => { setConnected(p => ({ ...p, [intg.name]: !p[intg.name] })); toast(connected[intg.name] ? `Disconnected ${intg.name}` : `Connected ${intg.name}`, 'success') }}
                style={{ padding: '6px 14px', borderRadius: 7, fontSize: 12, fontWeight: 600, cursor: 'pointer', background: connected[intg.name] ? 'rgba(239,68,68,0.1)' : 'rgba(14,165,233,0.1)', color: connected[intg.name] ? C.red : C.accent, border: `1px solid ${connected[intg.name] ? 'rgba(239,68,68,0.3)' : 'rgba(14,165,233,0.3)'}` }}>
                {connected[intg.name] ? 'Disconnect' : 'Connect'}
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── AUDIT LOG TAB ─────────────────────────────────────────────────────────────
const ACTION_COLORS: Record<string, string> = {
  login: '#38BDF8', create_pipeline: '#10B981', trigger_healing: '#f59e0b', approve_fix: '#A78BFA',
  optimize_query: '#34d399', generate_dbt: '#f472b6', invite_member: '#38BDF8', revoke_token: '#f87171',
  create_token: '#fbbf24', update_notification_config: '#94a3b8', remove_member: '#f87171',
}

function AuditLogTab() {
  const [search, setSearch] = useState('')
  const { data, isLoading } = useQuery({ queryKey: ['audit-log'], queryFn: () => api.get(`${API}/audit-log`).then(r => r.data), refetchInterval: 30_000, staleTime: 10_000 })
  const allEntries = data?.entries || []
  const entries = search ? allEntries.filter((e: AuditLogEntry) => ((e.action ?? '') + (e.actor ?? '') + (e.resource_type ?? '')).toLowerCase().includes(search.toLowerCase())) : allEntries

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <p style={{ fontSize: 14, fontWeight: 600, color: C.textPrimary, margin: 0 }}>
          Audit Log <span style={{ fontSize: 11, padding: '2px 7px', borderRadius: 5, background: 'rgba(14,165,233,0.12)', color: C.accent, marginLeft: 8 }}>{allEntries.length} entries</span>
        </p>
        <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search actions, users…"
          style={{ ...inputStyle(), width: 220 }} />
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {isLoading ? [1,2,3,4,5].map(i => <div key={i} style={{ height: 50, borderRadius: 10, background: C.border, opacity: 0.3 }} />) :
          entries.length === 0 ? <p style={{ textAlign: 'center', padding: '40px 0', fontSize: 13, color: C.textMuted }}>No audit entries yet</p> :
          entries.map((e: AuditLogEntry) => (
            <div key={e.id} style={{ display: 'flex', alignItems: 'flex-start', gap: 12, padding: '12px 14px', borderRadius: 10, border: `1px solid ${C.border}` }}>
              <div style={{ width: 8, height: 8, borderRadius: '50%', background: ACTION_COLORS[e.action ?? ''] || '#64748b', flexShrink: 0, marginTop: 5 }} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 3 }}>
                  <span style={{ fontSize: 12, fontFamily: 'ui-monospace, monospace', fontWeight: 600, color: ACTION_COLORS[e.action ?? ''] || '#94a3b8' }}>{e.action}</span>
                  {e.resource_type && <span style={{ fontSize: 10, padding: '1px 5px', borderRadius: 4, background: '#09111E', color: C.textMuted }}>{e.resource_type}</span>}
                  {e.details && Object.keys(e.details).length > 0 && (
                    <span style={{ fontSize: 10, color: C.textMuted }}>{Object.entries(e.details).map(([k,v]) => `${k}: ${v}`).join(' · ').slice(0,60)}</span>
                  )}
                </div>
                <p style={{ fontSize: 11, color: C.textMuted, margin: 0 }}>
                  by <span style={{ color: C.textPrimary }}>{e.actor}</span>
                  {e.created_at && ` · ${formatDistanceToNow(new Date(e.created_at), { addSuffix: true })}`}
                </p>
              </div>
            </div>
          ))
        }
      </div>
    </div>
  )
}

// ── MAIN PAGE ─────────────────────────────────────────────────────────────────
export default function SettingsPage() {
  const toast = useToast()
  const [active, setActive] = useState<Tab>('General')

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}
      style={{ display: 'flex', height: 'calc(100vh - 56px)', background: C.bg }}
    >
      {/* Left nav */}
      <div style={{ width: 220, background: '#09111E', borderRight: `1px solid ${C.border}`, padding: '20px 12px', display: 'flex', flexDirection: 'column', gap: 4, flexShrink: 0 }}>
        <p style={{ fontSize: 11, letterSpacing: '0.08em', textTransform: 'uppercase' as const, color: C.textLabel, fontWeight: 600, margin: '0 0 12px 8px' }}>Settings</p>
        {TABS.map(tab => {
          const { icon: Icon } = TAB_META[tab]
          const isActive = active === tab
          return (
            <button key={tab} onClick={() => setActive(tab)}
              style={{
                display: 'flex', alignItems: 'center', gap: 10, padding: '9px 12px', borderRadius: 8,
                width: '100%', textAlign: 'left', cursor: 'pointer', fontSize: 13, fontWeight: isActive ? 600 : 400,
                background: isActive ? 'rgba(14,165,233,0.12)' : 'transparent',
                color: isActive ? C.accent : C.textMuted,
                border: 'none',
                borderLeft: isActive ? `2px solid ${C.accent}` : '2px solid transparent',
                transition: 'all 0.15s',
              }}>
              <Icon size={14} style={{ flexShrink: 0 }} />
              <span>{tab}</span>
            </button>
          )
        })}
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '28px 32px' }}>
        <div style={{ maxWidth: 680 }}>
          <h2 style={{ fontSize: 18, fontWeight: 700, color: C.textPrimary, margin: '0 0 4px' }}>{active}</h2>
          <p style={{ fontSize: 12, color: C.textMuted, margin: '0 0 24px' }}>{TAB_META[active].desc}</p>

          {active === 'General'       && <GeneralTab onSave={() => toast('Profile saved', 'success')} />}
          {active === 'Team'          && <TeamTab />}
          {active === 'API Tokens'    && <ApiTokensTab />}
          {active === 'Notifications' && <NotificationsTab />}
          {active === 'Integrations'  && <IntegrationsTab />}
          {active === 'Audit Log'     && <AuditLogTab />}
        </div>
      </div>
    </motion.div>
  )
}
