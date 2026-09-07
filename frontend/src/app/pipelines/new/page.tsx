'use client'
import { useState } from 'react'
import React from 'react'
import { useRouter } from 'next/navigation'
import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import {
  ChevronRight, ChevronLeft, Check, ArrowRight, Plus, X,
  RefreshCw, Zap, Clock, Play, Table, Filter, Settings, Database, Layers,
} from 'lucide-react'

import api from '@/lib/api'
import type { SavedConnection } from '@/lib/types'

// ── Form type ──────────────────────────────────────────────────────────────────
interface PipelineForm {
  name?: string
  source_connection_id?: string
  dest_connection_id?: string
  source_table?: string
  source_query?: string
  dest_table?: string
  sync_mode?: string
  cursor_field?: string
  schedule_cron?: string
  _custom_cron?: string
  description?: string
  field_mappings?: { src: string; dst: string; type: string }[]
  filters?: { field: string; op: string; value: string }[]
}

// ── Design tokens ──────────────────────────────────────────────────────────────
const T = {
  card: '#0F2540',
  border: '#1A3A5C',
  textPrimary: '#F1F5F9',
  textMuted: '#64748B',
  textLabel: '#4B6B8E',
  sky: '#0EA5E9',
  emerald: '#10B981',
  input: '#0B1B33',
}

const inputStyle: React.CSSProperties = {
  background: T.input,
  border: `1px solid ${T.border}`,
  borderRadius: 8,
  color: T.textPrimary,
  width: '100%',
  padding: '9px 12px',
  fontSize: 13,
  outline: 'none',
}

const labelStyle: React.CSSProperties = {
  display: 'block',
  fontSize: 12,
  fontWeight: 600,
  color: T.textPrimary,
  marginBottom: 8,
}

const fetchSaved = () =>
  api.get('/api/connectors/saved').then(r => r.data)

// ── Step indicator ─────────────────────────────────────────────────────────────
const STEPS = ['Source', 'Configure', 'Destination', 'Transform', 'Schedule', 'Review']

function StepBar({ current }: { current: number }) {
  return (
    <div className="flex items-center justify-center mb-8">
      {STEPS.map((s, i) => (
        <div key={s} className="flex items-center">
          <div className="flex flex-col items-center">
            <div
              className="flex items-center justify-center transition-all"
              style={{
                width: 32, height: 32, borderRadius: 999, fontSize: 12, fontWeight: 700,
                background: i < current ? T.emerald : i === current ? T.sky : T.card,
                border: i > current ? `1px solid ${T.border}` : 'none',
                color: i <= current ? '#fff' : T.textLabel,
                boxShadow: i === current ? '0 0 0 4px rgba(14,165,233,0.15)' : 'none',
              }}>
              {i < current ? <Check size={14} /> : i + 1}
            </div>
            <span style={{
              fontSize: 10, marginTop: 6, fontWeight: 600,
              color: i === current ? '#38BDF8' : i < current ? '#34D399' : T.textLabel,
              textTransform: 'uppercase', letterSpacing: '0.06em',
            }}>
              {s}
            </span>
          </div>
          {i < STEPS.length - 1 && (
            <div
              className="transition-all"
              style={{ width: 44, height: 2, margin: '0 6px 18px', borderRadius: 2, background: i < current ? T.emerald : T.border }}
            />
          )}
        </div>
      ))}
    </div>
  )
}

// ── Connector picker ───────────────────────────────────────────────────────────
function ConnectorPicker({
  label,
  value,
  onChange,
  connections,
}: {
  label: string
  value: string
  onChange: (id: string) => void
  connections: SavedConnection[]
}) {
  return (
    <div>
      <label style={{ ...labelStyle, fontSize: 14 }}>{label}</label>
      {connections.length === 0 ? (
        <div className="rounded-xl p-6 text-center" style={{ border: `2px dashed ${T.border}` }}>
          <p style={{ fontSize: 13, color: T.textMuted }}>No saved connections.</p>
          <a href="/connectors" className="hover:underline mt-1 inline-block" style={{ fontSize: 13, color: '#38BDF8' }}>
            Go to Connector Gallery →
          </a>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {connections.map((c: SavedConnection) => (
            <button
              key={c.id}
              onClick={() => onChange(c.id)}
              className="flex items-center gap-3 text-left transition-all hover:bg-white/5"
              style={{
                padding: 14, borderRadius: 12,
                background: value === c.id ? 'rgba(14,165,233,0.08)' : T.input,
                border: `1px solid ${value === c.id ? T.sky : T.border}`,
                boxShadow: value === c.id ? '0 0 0 3px rgba(14,165,233,0.12)' : 'none',
              }}>
              <div className="w-10 h-10 rounded-xl flex items-center justify-center text-xl flex-shrink-0"
                style={{ background: `${c.connector_color}20` }}>
                {c.connector_logo}
              </div>
              <div className="flex-1 min-w-0">
                <p className="truncate" style={{ fontSize: 13, fontWeight: 600, color: T.textPrimary }}>{c.name}</p>
                <p style={{ fontSize: 11, color: T.textMuted }}>
                  {c.connector_name} · {c.connector_category}
                </p>
              </div>
              {value === c.id && <Check size={16} className="flex-shrink-0" style={{ color: '#38BDF8' }} />}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Step 2: Configure Source ───────────────────────────────────────────────────
function ConfigureSource({
  srcConn,
  form,
  setForm,
}: {
  srcConn: SavedConnection
  form: PipelineForm
  setForm: React.Dispatch<React.SetStateAction<PipelineForm>>
}) {
  const connectorId = srcConn?.connector_id || ''
  const isDb = ['postgresql', 'mysql', 'mssql', 'sqlite'].includes(connectorId)
  const isApi = ['rest_api', 'airflow'].includes(connectorId)

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3 rounded-xl"
        style={{ background: T.input, border: `1px solid ${T.border}`, padding: 12 }}>
        <span className="text-xl">{srcConn?.connector_logo}</span>
        <div>
          <p style={{ fontSize: 13, fontWeight: 600, color: T.textPrimary }}>{srcConn?.name}</p>
          <p style={{ fontSize: 11, color: T.textMuted }}>{srcConn?.connector_name}</p>
        </div>
      </div>

      {isDb ? (
        <>
          <div>
            <label style={labelStyle}>
              <Table size={13} className="inline mr-1.5" />Source Table
            </label>
            <input
              value={form.source_table || ''}
              onChange={e => setForm((p: PipelineForm) => ({ ...p, source_table: e.target.value }))}
              placeholder="e.g. public.orders"
              className="focus:ring-1 focus:ring-sky-500"
              style={inputStyle}
            />
          </div>
          <div>
            <label style={{ ...labelStyle, color: T.textMuted, fontWeight: 500 }}>
              Or custom SQL query (overrides table)
            </label>
            <textarea
              rows={4}
              value={form.source_query || ''}
              onChange={e => setForm((p: PipelineForm) => ({ ...p, source_query: e.target.value }))}
              placeholder="SELECT id, name, amount, created_at FROM orders WHERE status = 'paid'"
              className="font-mono resize-none focus:ring-1 focus:ring-sky-500"
              style={{ ...inputStyle, fontSize: 12 }}
            />
          </div>
        </>
      ) : isApi ? (
        <div>
          <label style={labelStyle}>Endpoint Path</label>
          <input
            value={form.source_table || ''}
            onChange={e => setForm((p: PipelineForm) => ({ ...p, source_table: e.target.value }))}
            placeholder="e.g. /api/v1/dags or /users"
            className="focus:ring-1 focus:ring-sky-500"
            style={inputStyle}
          />
        </div>
      ) : (
        <div>
          <label style={labelStyle}>Resource / Sheet / Bucket Path</label>
          <input
            value={form.source_table || ''}
            onChange={e => setForm((p: PipelineForm) => ({ ...p, source_table: e.target.value }))}
            placeholder="e.g. Sheet1, s3://bucket/prefix/, orders collection"
            className="focus:ring-1 focus:ring-sky-500"
            style={inputStyle}
          />
        </div>
      )}

      {/* Sync mode */}
      <div>
        <label style={labelStyle}>
          <RefreshCw size={13} className="inline mr-1.5" />Sync Mode
        </label>
        <div className="grid grid-cols-2 gap-3">
          {[
            { id: 'full_refresh', label: 'Full Refresh', desc: 'Replace destination on every sync' },
            { id: 'incremental', label: 'Incremental', desc: 'Append only new/updated records' },
          ].map(m => (
            <button
              key={m.id}
              onClick={() => setForm((p: PipelineForm) => ({ ...p, sync_mode: m.id }))}
              className="text-left transition-all hover:bg-white/5"
              style={{
                padding: 12, borderRadius: 12,
                background: form.sync_mode === m.id ? 'rgba(14,165,233,0.08)' : T.input,
                border: `1px solid ${form.sync_mode === m.id ? T.sky : T.border}`,
                boxShadow: form.sync_mode === m.id ? '0 0 0 3px rgba(14,165,233,0.12)' : 'none',
              }}>
              <p style={{ fontSize: 13, fontWeight: 600, color: T.textPrimary }}>{m.label}</p>
              <p style={{ fontSize: 11, color: T.textMuted, marginTop: 2 }}>{m.desc}</p>
            </button>
          ))}
        </div>
      </div>

      {form.sync_mode === 'incremental' && (
        <div>
          <label style={labelStyle}>Cursor Field</label>
          <input
            value={form.cursor_field || ''}
            onChange={e => setForm((p: PipelineForm) => ({ ...p, cursor_field: e.target.value }))}
            placeholder="e.g. updated_at or id"
            className="focus:ring-1 focus:ring-sky-500"
            style={inputStyle}
          />
        </div>
      )}
    </div>
  )
}

// ── Step 4: Transform ──────────────────────────────────────────────────────────
function TransformStep({ form, setForm }: { form: PipelineForm; setForm: React.Dispatch<React.SetStateAction<PipelineForm>> }) {
  const [mappings, setMappings] = useState<{ src: string; dst: string; type: string }[]>(
    form.field_mappings || []
  )
  const [filters, setFilters] = useState<{ field: string; op: string; value: string }[]>(
    form.filters || []
  )

  const sync = (m: typeof mappings, f: typeof filters) => {
    setMappings(m); setFilters(f)
    setForm((p: PipelineForm) => ({ ...p, field_mappings: m, filters: f }))
  }

  const addMapping = () => sync([...mappings, { src: '', dst: '', type: 'text' }], filters)
  const addFilter  = () => sync(mappings, [...filters, { field: '', op: '=', value: '' }])

  const smallInput: React.CSSProperties = {
    ...inputStyle, padding: '6px 10px', fontSize: 12,
  }

  return (
    <div className="space-y-6">
      {/* Field mappings */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <label className="flex items-center gap-1.5" style={{ fontSize: 13, fontWeight: 600, color: T.textPrimary }}>
            <Table size={13} /> Field Mappings
            <span style={{ fontSize: 11, fontWeight: 400, color: T.textMuted, marginLeft: 4 }}>
              (optional — leave empty to sync all columns)
            </span>
          </label>
          <button onClick={addMapping}
            className="flex items-center gap-1 hover:opacity-80"
            style={{ fontSize: 12, color: '#38BDF8' }}>
            <Plus size={12} /> Add
          </button>
        </div>
        {mappings.length === 0 ? (
          <div className="rounded-xl p-4 text-center" style={{ border: `1px dashed ${T.border}` }}>
            <p style={{ fontSize: 12, color: T.textMuted }}>
              All columns will be synced as-is. Add mappings to rename or filter fields.
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            <div className="grid grid-cols-[1fr_auto_1fr_auto_auto] gap-2 mb-1"
              style={{ fontSize: 10, fontWeight: 600, color: T.textLabel, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              <span>Source Column</span><span></span><span>Destination Column</span><span>Type</span><span></span>
            </div>
            {mappings.map((m, i) => (
              <div key={i} className="grid grid-cols-[1fr_auto_1fr_auto_auto] gap-2 items-center">
                <input value={m.src} onChange={e => { const n=[...mappings]; n[i]={...n[i],src:e.target.value}; sync(n,filters) }}
                  placeholder="source_col" className="focus:ring-1 focus:ring-sky-500" style={smallInput} />
                <ArrowRight size={12} style={{ color: T.textLabel }} />
                <input value={m.dst} onChange={e => { const n=[...mappings]; n[i]={...n[i],dst:e.target.value}; sync(n,filters) }}
                  placeholder="dest_col" className="focus:ring-1 focus:ring-sky-500" style={smallInput} />
                <select value={m.type} onChange={e => { const n=[...mappings]; n[i]={...n[i],type:e.target.value}; sync(n,filters) }}
                  style={{ ...smallInput, width: 'auto' }}>
                  {['text','integer','float','boolean','timestamp','date'].map(t=><option key={t}>{t}</option>)}
                </select>
                <button onClick={() => { const n=mappings.filter((_,j)=>j!==i); sync(n,filters) }}
                  className="p-1 rounded hover:bg-red-500/10"><X size={12} style={{ color: '#EF4444' }} /></button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Filters */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <label className="flex items-center gap-1.5" style={{ fontSize: 13, fontWeight: 600, color: T.textPrimary }}>
            <Filter size={13} /> Row Filters
            <span style={{ fontSize: 11, fontWeight: 400, color: T.textMuted, marginLeft: 4 }}>
              (optional)
            </span>
          </label>
          <button onClick={addFilter}
            className="flex items-center gap-1 hover:opacity-80"
            style={{ fontSize: 12, color: '#38BDF8' }}>
            <Plus size={12} /> Add
          </button>
        </div>
        {filters.length > 0 && (
          <div className="space-y-2">
            <div className="grid grid-cols-[1fr_auto_1fr_auto] gap-2 mb-1"
              style={{ fontSize: 10, fontWeight: 600, color: T.textLabel, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              <span>Field</span><span>Operator</span><span>Value</span><span></span>
            </div>
            {filters.map((f, i) => (
              <div key={i} className="grid grid-cols-[1fr_auto_1fr_auto] gap-2 items-center">
                <input value={f.field} onChange={e => { const n=[...filters]; n[i]={...n[i],field:e.target.value}; sync(mappings,n) }}
                  placeholder="field_name" className="focus:ring-1 focus:ring-sky-500" style={smallInput} />
                <select value={f.op} onChange={e => { const n=[...filters]; n[i]={...n[i],op:e.target.value}; sync(mappings,n) }}
                  style={{ ...smallInput, width: 'auto' }}>
                  {['=','!=','>','<','>=','<=','LIKE','IN'].map(op=><option key={op}>{op}</option>)}
                </select>
                <input value={f.value} onChange={e => { const n=[...filters]; n[i]={...n[i],value:e.target.value}; sync(mappings,n) }}
                  placeholder="value" className="focus:ring-1 focus:ring-sky-500" style={smallInput} />
                <button onClick={() => { const n=filters.filter((_,j)=>j!==i); sync(mappings,n) }}
                  className="p-1 rounded hover:bg-red-500/10"><X size={12} style={{ color: '#EF4444' }} /></button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

// ── Step 5: Schedule & Name ────────────────────────────────────────────────────
const SCHEDULES = [
  { label: 'Manual only',      cron: '',              icon: Play  },
  { label: 'Every 30 minutes', cron: '*/30 * * * *',  icon: Clock },
  { label: 'Every 1 hour',     cron: '0 * * * *',     icon: Clock },
  { label: 'Every 3 hours',    cron: '0 */3 * * *',   icon: Clock },
  { label: 'Every 6 hours',    cron: '0 */6 * * *',   icon: Clock },
  { label: 'Every 12 hours',   cron: '0 */12 * * *',  icon: Clock },
  { label: 'Every 24 hours',   cron: '0 0 * * *',     icon: Clock },
  { label: 'Custom cron',      cron: '__custom__',    icon: Settings },
]

function ScheduleStep({ form, setForm }: { form: PipelineForm; setForm: React.Dispatch<React.SetStateAction<PipelineForm>> }) {
  const [customCron, setCustomCron] = useState(form._custom_cron || '')
  const isCustom = form.schedule_cron === '__custom__'

  return (
    <div className="space-y-5">
      <div>
        <label style={{ ...labelStyle, fontSize: 13 }}>Pipeline Name *</label>
        <input
          value={form.name || ''}
          onChange={e => setForm((p: PipelineForm) => ({ ...p, name: e.target.value }))}
          placeholder="e.g. Postgres → Snowflake daily sync"
          className="focus:ring-1 focus:ring-sky-500"
          style={inputStyle}
        />
      </div>

      <div>
        <label style={{ ...labelStyle, fontSize: 13 }}>
          <Clock size={13} className="inline mr-1.5" />Sync Schedule
        </label>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          {SCHEDULES.map(s => {
            const active = form.schedule_cron === s.cron
            const Icon = s.icon
            return (
              <button
                key={s.label}
                onClick={() => setForm((p: PipelineForm) => ({ ...p, schedule_cron: s.cron }))}
                className="flex items-center gap-2 text-left transition-all hover:bg-white/5"
                style={{
                  padding: 11, borderRadius: 10,
                  background: active ? 'rgba(14,165,233,0.08)' : T.input,
                  border: `1px solid ${active ? T.sky : T.border}`,
                  boxShadow: active ? '0 0 0 3px rgba(14,165,233,0.12)' : 'none',
                }}>
                <Icon size={14} style={{ color: active ? '#38BDF8' : T.textLabel }} />
                <span style={{ fontSize: 12, fontWeight: 500, color: T.textPrimary }}>{s.label}</span>
              </button>
            )
          })}
        </div>
        {isCustom && (
          <input
            value={customCron}
            onChange={e => { setCustomCron(e.target.value); setForm((p: PipelineForm) => ({ ...p, _custom_cron: e.target.value })) }}
            placeholder="e.g. 0 */4 * * *"
            className="mt-3 font-mono focus:ring-1 focus:ring-sky-500"
            style={inputStyle}
          />
        )}
      </div>

      <div>
        <label style={{ ...labelStyle, color: T.textMuted, fontWeight: 500 }}>
          Description (optional)
        </label>
        <textarea
          rows={2}
          value={form.description || ''}
          onChange={e => setForm((p: PipelineForm) => ({ ...p, description: e.target.value }))}
          placeholder="What does this pipeline do?"
          className="resize-none focus:ring-1 focus:ring-sky-500"
          style={inputStyle}
        />
      </div>
    </div>
  )
}

// ── Review step ────────────────────────────────────────────────────────────────
function ReviewStep({
  form,
  connections,
}: {
  form: PipelineForm
  connections: SavedConnection[]
}) {
  const srcConn = connections.find(c => c.id === form.source_connection_id)
  const dstConn = connections.find(c => c.id === form.dest_connection_id)

  return (
    <div className="space-y-4">
      <div className="rounded-xl space-y-3" style={{ background: T.input, border: `1px solid ${T.border}`, padding: 16 }}>
        <Row label="Pipeline Name" value={form.name || '—'} />
        <Row label="Source" value={`${srcConn?.connector_logo} ${srcConn?.name} (${form.source_table || 'custom query'})`} />
        <Row label="Destination" value={`${dstConn?.connector_logo} ${dstConn?.name} → ${form.dest_table || '—'}`} />
        <Row label="Sync Mode" value={form.sync_mode === 'incremental' ? `Incremental (cursor: ${form.cursor_field})` : 'Full Refresh'} />
        <Row label="Schedule" value={form.schedule_cron ? (form.schedule_cron === '__custom__' ? (form._custom_cron ?? 'custom') : form.schedule_cron) : 'Manual only'} />
        <Row label="Field Mappings" value={form.field_mappings?.length ? `${form.field_mappings.length} mappings` : 'All columns'} />
        <Row label="Filters" value={form.filters?.length ? `${form.filters.length} filters` : 'None'} />
      </div>
      <p className="text-center" style={{ fontSize: 12, color: T.textMuted }}>
        Click &quot;Create Pipeline&quot; to save and run the first sync immediately.
      </p>
    </div>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-4">
      <span className="flex-shrink-0" style={{ fontSize: 12, color: T.textMuted }}>{label}</span>
      <span className="text-right" style={{ fontSize: 12, fontWeight: 500, color: T.textPrimary }}>{value}</span>
    </div>
  )
}

// ── Live preview panel ─────────────────────────────────────────────────────────
function PreviewPanel({ form, connections }: { form: PipelineForm; connections: SavedConnection[] }) {
  const srcConn = connections.find(c => c.id === form.source_connection_id)
  const dstConn = connections.find(c => c.id === form.dest_connection_id)
  const scheduleLabel = form.schedule_cron === '__custom__'
    ? (form._custom_cron || 'custom cron')
    : form.schedule_cron
      ? SCHEDULES.find(s => s.cron === form.schedule_cron)?.label || form.schedule_cron
      : 'Manual only'

  return (
    <div className="card sticky top-6" style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 12, padding: 20 }}>
      <p className="section-header mb-4" style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.08em', color: T.textLabel, fontWeight: 600 }}>
        Pipeline Preview
      </p>

      {/* Flow diagram */}
      <div className="flex items-center gap-2 mb-5">
        <div className="flex-1 rounded-lg text-center"
          style={{ background: T.input, border: `1px solid ${srcConn ? 'rgba(14,165,233,0.4)' : T.border}`, padding: '10px 6px' }}>
          <Database size={14} className="mx-auto mb-1" style={{ color: srcConn ? T.sky : T.textLabel }} />
          <p className="truncate" style={{ fontSize: 11, fontWeight: 600, color: srcConn ? T.textPrimary : T.textLabel }}>
            {srcConn ? srcConn.name : 'Source'}
          </p>
        </div>
        <ArrowRight size={14} className="flex-shrink-0" style={{ color: T.textLabel }} />
        <div className="flex-1 rounded-lg text-center"
          style={{ background: T.input, border: `1px solid ${dstConn ? 'rgba(16,185,129,0.4)' : T.border}`, padding: '10px 6px' }}>
          <Layers size={14} className="mx-auto mb-1" style={{ color: dstConn ? T.emerald : T.textLabel }} />
          <p className="truncate" style={{ fontSize: 11, fontWeight: 600, color: dstConn ? T.textPrimary : T.textLabel }}>
            {dstConn ? dstConn.name : 'Destination'}
          </p>
        </div>
      </div>

      <div className="space-y-2.5">
        {[
          { label: 'Name', value: form.name || '—' },
          { label: 'Object', value: form.source_query ? 'Custom SQL' : (form.source_table || '—') },
          { label: 'Target table', value: form.dest_table || '—' },
          { label: 'Sync mode', value: form.sync_mode === 'incremental' ? 'Incremental' : 'Full Refresh' },
          { label: 'Schedule', value: scheduleLabel },
          { label: 'Mappings', value: form.field_mappings?.length ? `${form.field_mappings.length}` : 'All columns' },
          { label: 'Filters', value: form.filters?.length ? `${form.filters.length}` : 'None' },
        ].map(r => (
          <div key={r.label} className="flex items-center justify-between gap-3">
            <span style={{ fontSize: 11, color: T.textLabel, textTransform: 'uppercase', letterSpacing: '0.05em' }}>{r.label}</span>
            <span className="truncate text-right" style={{ fontSize: 12, fontWeight: 500, color: T.textPrimary, maxWidth: 150 }}>
              {r.value}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Main Page ──────────────────────────────────────────────────────────────────
export default function NewPipelinePage() {
  const router = useRouter()
  const [step, setStep] = useState(0)
  const [form, setForm] = useState<PipelineForm>({ sync_mode: 'full_refresh', schedule_cron: '' })
  const [deploying, setDeploying] = useState(false)
  const [error, setError] = useState('')

  const { data: savedData } = useQuery({
    queryKey: ['connector-saved'],
    queryFn: fetchSaved,
    staleTime: 30_000,
  })
  const connections: SavedConnection[] = savedData?.connections || []

  const srcConn = connections.find(c => c.id === form.source_connection_id)

  const canNext = () => {
    if (step === 0) return !!form.source_connection_id
    if (step === 1) return !!(form.source_table || form.source_query)
    if (step === 2) return !!form.dest_connection_id && !!form.dest_table
    if (step === 3) return true
    if (step === 4) return !!form.name?.trim()
    if (step === 5) return !!form.name?.trim()
    return true
  }

  const deploy = async () => {
    setDeploying(true)
    setError('')
    try {
      const schedule = form.schedule_cron === '__custom__'
        ? (form._custom_cron || '')
        : (form.schedule_cron || '')

      const res = await api.post('/api/pipelines', {
        name: form.name,
        source_connection_id: form.source_connection_id,
        source_table: form.source_table || null,
        source_query: form.source_query || null,
        dest_connection_id: form.dest_connection_id,
        dest_table: form.dest_table,
        sync_mode: form.sync_mode,
        cursor_field: form.cursor_field || null,
        field_mappings: form.field_mappings || [],
        filters: form.filters || [],
        schedule_cron: schedule || null,
        description: form.description || '',
      })
      const data = res.data
      router.push(`/pipelines/${data.id}`)
    } catch (e: unknown) {
      setError((e as Error).message || 'Failed to deploy pipeline')
      setDeploying(false)
    }
  }

  const TOTAL = STEPS.length
  const isLast = step === TOTAL - 1

  const STEP_TITLES: Record<number, { title: string; sub: string }> = {
    0: { title: 'Choose your source', sub: 'Pick the connection to read data from' },
    1: { title: 'Configure the source', sub: 'Tell us which table, query, or resource to sync' },
    2: { title: 'Choose your destination', sub: 'Pick where the data lands' },
    3: { title: 'Transform (optional)', sub: 'Rename columns and filter rows on the way in' },
    4: { title: 'Name & schedule', sub: 'Give the pipeline a name and a sync cadence' },
    5: { title: 'Review & create', sub: 'One last look before deployment' },
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: 'easeOut' }}
      className="min-h-full flex flex-col items-center"
      style={{ padding: 24 }}>
      <div className="w-full" style={{ maxWidth: 980 }}>

        {/* Header */}
        <div className="flex items-center gap-3 mb-6">
          <button
            onClick={() => router.push('/pipelines')}
            className="p-2 rounded-lg hover:bg-white/10 transition-colors">
            <ChevronLeft size={18} style={{ color: T.textMuted }} />
          </button>
          <div>
            <h1 style={{ fontSize: 22, fontWeight: 700, color: T.textPrimary, letterSpacing: '-0.02em' }}>New Pipeline</h1>
            <p style={{ fontSize: 12, color: T.textMuted, marginTop: 2 }}>
              Step {step + 1} of {TOTAL} — {STEPS[step]}
            </p>
          </div>
        </div>

        <StepBar current={step} />

        <div className="grid grid-cols-3 gap-6 items-start">
          {/* Left: form card */}
          <div className="col-span-2">
            <div className="card" style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 12, padding: 28 }}>
              <div className="mb-6">
                <h2 style={{ fontSize: 17, fontWeight: 700, color: T.textPrimary }}>{STEP_TITLES[step]?.title}</h2>
                <p style={{ fontSize: 12, color: T.textMuted, marginTop: 2 }}>{STEP_TITLES[step]?.sub}</p>
              </div>

              {step === 0 && (
                <ConnectorPicker
                  label="Choose your Source connector"
                  value={form.source_connection_id || ''}
                  onChange={id => setForm((p: PipelineForm) => ({ ...p, source_connection_id: id }))}
                  connections={connections}
                />
              )}

              {step === 1 && srcConn && (
                <ConfigureSource srcConn={srcConn} form={form} setForm={setForm} />
              )}

              {step === 2 && (
                <div className="space-y-5">
                  <ConnectorPicker
                    label="Choose your Destination connector"
                    value={form.dest_connection_id || ''}
                    onChange={id => setForm((p: PipelineForm) => ({ ...p, dest_connection_id: id }))}
                    connections={connections.filter(c => c.id !== form.source_connection_id)}
                  />
                  {form.dest_connection_id && (
                    <div>
                      <label style={labelStyle}>Destination Table Name *</label>
                      <input
                        value={form.dest_table || ''}
                        onChange={e => setForm((p: PipelineForm) => ({ ...p, dest_table: e.target.value }))}
                        placeholder="e.g. raw_orders or staging.orders"
                        className="focus:ring-1 focus:ring-sky-500"
                        style={inputStyle}
                      />
                    </div>
                  )}
                </div>
              )}

              {step === 3 && <TransformStep form={form} setForm={setForm} />}

              {step === 4 && <ScheduleStep form={form} setForm={setForm} />}

              {step === 5 && <ReviewStep form={form} connections={connections} />}

              {error && (
                <p className="mt-4 text-xs px-3 py-2 rounded-lg" style={{ color: '#EF4444', background: 'rgba(239,68,68,0.1)' }}>{error}</p>
              )}

              {/* Final full-width deploy button on the last step */}
              {isLast && (
                <button
                  onClick={deploy}
                  disabled={deploying || !form.name?.trim()}
                  className="w-full mt-6 flex items-center justify-center gap-2 transition-all hover:opacity-90 active:scale-[0.99] disabled:opacity-50"
                  style={{
                    background: T.emerald, color: '#fff', borderRadius: 10,
                    padding: '13px 20px', fontSize: 15, fontWeight: 700,
                  }}>
                  {deploying
                    ? <><RefreshCw size={16} className="animate-spin" /> Deploying…</>
                    : <><Zap size={16} /> Create Pipeline</>}
                </button>
              )}
            </div>

            {/* Nav buttons */}
            <div className="flex items-center justify-between mt-4">
              <button
                onClick={() => setStep(s => s - 1)}
                disabled={step === 0}
                className="flex items-center gap-2 transition-colors disabled:opacity-30 hover:bg-white/5"
                style={{
                  border: `1px solid ${T.border}`, color: T.textMuted, borderRadius: 8,
                  padding: '8px 16px', fontSize: 13, fontWeight: 500,
                }}>
                <ChevronLeft size={16} /> Back
              </button>

              {!isLast && (
                <button
                  onClick={() => setStep(s => s + 1)}
                  disabled={!canNext()}
                  className="btn-primary flex items-center gap-2 transition-all disabled:opacity-30 disabled:cursor-not-allowed hover:opacity-90"
                  style={{
                    background: canNext() ? T.sky : T.input, color: '#fff',
                    borderRadius: 8, padding: '8px 20px', fontSize: 13, fontWeight: 600,
                  }}>
                  Continue <ChevronRight size={16} />
                </button>
              )}
            </div>

            {step === 4 && canNext() && (
              <p className="text-center mt-3" style={{ fontSize: 12, color: T.textMuted }}>
                Click Continue to review before deploying
              </p>
            )}
          </div>

          {/* Right: live preview */}
          <div className="col-span-1">
            <PreviewPanel form={form} connections={connections} />
          </div>
        </div>
      </div>
    </motion.div>
  )
}
