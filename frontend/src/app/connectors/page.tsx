'use client'
import { useState, useMemo, useEffect } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import {
  Plus, CheckCircle2, XCircle, Clock, Search,
  Trash2, TestTube2, RefreshCw, Zap, Plug,
  Database, Cloud, HardDrive, Code2, Layers,
} from 'lucide-react'
import { EmptyState } from '@/components/ui/EmptyState'
import { SkeletonCard, SkeletonList } from '@/components/ui/Skeleton'
import { useToast } from '@/components/ui/Toaster'
import type { CatalogConnector, ConnectorField, SavedConnection, LucideIcon } from '@/lib/types'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import api from '@/lib/api'
import { formatDistanceToNow } from 'date-fns'

// ── Design tokens ──────────────────────────────────────────────────────────────
const T = {
  card: '#0F2540',
  border: '#1A3A5C',
  textPrimary: '#F1F5F9',
  textMuted: '#64748B',
  textLabel: '#4B6B8E',
  sky: '#0EA5E9',
  input: '#0B1B33',
}

// ── API helpers ────────────────────────────────────────────────────────────────
const fetchCatalog = () =>
  api.get('/api/connectors/catalog').then(r => r.data)

const fetchSaved = () =>
  api.get('/api/connectors/saved').then(r => r.data)

const createConnection = (body: unknown) =>
  api.post('/api/connectors/saved', body)
    .then(r => r.data)
    .catch(() => { throw new Error('Failed to save') })

const deleteConnection = (id: string) =>
  api.delete(`/api/connectors/saved/${id}`).then(r => r.data)

const testConnection = (id: string) =>
  api.post(`/api/connectors/saved/${id}/test`).then(r => r.data)

// ── Brand logo (Brandfetch) ─────────────────────────────────────────────────────
// Needs a free client ID in frontend/.env.local: NEXT_PUBLIC_BRANDFETCH_CLIENT_ID=...
// Falls back to the connector's emoji when the ID or domain is missing / image fails.
const BRANDFETCH_ID = process.env.NEXT_PUBLIC_BRANDFETCH_CLIENT_ID || ''

// ── Static catalog fallback — mirrors backend CONNECTOR_CATALOG ────────────────
// Shown instantly even when backend is offline. Backend response takes priority.
const STATIC_CATALOG: Record<string, CatalogConnector[]> = {
  'Databases': [
    { id: 'postgresql', name: 'PostgreSQL', category: 'Databases', description: 'Open-source relational database — production workloads, analytics.', color: '#336791', logo: '🐘', popular: true, fields: [
      { key: 'host', label: 'Host', type: 'text', placeholder: 'localhost' },
      { key: 'port', label: 'Port', type: 'number', placeholder: '5432' },
      { key: 'database', label: 'Database', type: 'text', placeholder: 'mydb' },
      { key: 'user', label: 'Username', type: 'text', placeholder: 'postgres' },
      { key: 'password', label: 'Password', type: 'password', placeholder: '••••••' },
    ]},
    { id: 'mysql', name: 'MySQL', category: 'Databases', description: "World's most popular open-source database.", color: '#4479A1', logo: '🐬', popular: true, fields: [
      { key: 'host', label: 'Host', type: 'text', placeholder: 'localhost' },
      { key: 'port', label: 'Port', type: 'number', placeholder: '3306' },
      { key: 'database', label: 'Database', type: 'text', placeholder: 'mydb' },
      { key: 'user', label: 'Username', type: 'text', placeholder: 'root' },
      { key: 'password', label: 'Password', type: 'password', placeholder: '••••••' },
    ]},
    { id: 'mongodb', name: 'MongoDB', category: 'Databases', description: 'Document database for modern apps.', color: '#47A248', logo: '🍃', fields: [
      { key: 'connection_string', label: 'Connection String', type: 'text', placeholder: 'mongodb://localhost:27017' },
      { key: 'database', label: 'Database', type: 'text', placeholder: 'mydb' },
    ]},
    { id: 'sqlite', name: 'SQLite', category: 'Databases', description: 'Lightweight embedded SQL database — great for local dev and demos.', color: '#0F80CC', logo: '📦', fields: [
      { key: 'file_path', label: 'File Path', type: 'text', placeholder: '/data/mydb.sqlite' },
    ]},
    { id: 'mssql', name: 'MS SQL Server', category: 'Databases', description: "Microsoft's enterprise relational database.", color: '#CC2927', logo: '🪟', fields: [
      { key: 'host', label: 'Host', type: 'text', placeholder: 'localhost' },
      { key: 'port', label: 'Port', type: 'number', placeholder: '1433' },
      { key: 'database', label: 'Database', type: 'text', placeholder: 'mydb' },
      { key: 'user', label: 'Username', type: 'text', placeholder: 'sa' },
      { key: 'password', label: 'Password', type: 'password', placeholder: '••••••' },
    ]},
  ],
  'Cloud Warehouses': [
    { id: 'snowflake', name: 'Snowflake', category: 'Cloud Warehouses', description: 'Cloud data platform — scalable warehouse built for analytics.', color: '#29B5E8', logo: '❄️', popular: true, fields: [
      { key: 'account', label: 'Account', type: 'text', placeholder: 'xy12345.us-east-1' },
      { key: 'user', label: 'Username', type: 'text', placeholder: 'MYUSER' },
      { key: 'password', label: 'Password', type: 'password', placeholder: '••••••' },
      { key: 'warehouse', label: 'Warehouse', type: 'text', placeholder: 'COMPUTE_WH' },
      { key: 'database', label: 'Database', type: 'text', placeholder: 'MY_DB' },
      { key: 'schema', label: 'Schema', type: 'text', placeholder: 'PUBLIC' },
    ]},
    { id: 'bigquery', name: 'BigQuery', category: 'Cloud Warehouses', description: "Google's serverless, highly scalable data warehouse.", color: '#4285F4', logo: '🔷', popular: true, fields: [
      { key: 'project_id', label: 'Project ID', type: 'text', placeholder: 'my-gcp-project' },
      { key: 'dataset_id', label: 'Dataset', type: 'text', placeholder: 'my_dataset' },
      { key: 'credentials_json', label: 'Service Account JSON', type: 'textarea', placeholder: '{"type": "service_account", ...}' },
    ]},
    { id: 'redshift', name: 'Amazon Redshift', category: 'Cloud Warehouses', description: 'Fully managed petabyte-scale data warehouse from AWS.', color: '#8C4FFF', logo: '🔴', fields: [
      { key: 'host', label: 'Cluster Endpoint', type: 'text', placeholder: 'cluster.xxxx.us-east-1.redshift.amazonaws.com' },
      { key: 'port', label: 'Port', type: 'number', placeholder: '5439' },
      { key: 'database', label: 'Database', type: 'text', placeholder: 'dev' },
      { key: 'user', label: 'Username', type: 'text', placeholder: 'awsuser' },
      { key: 'password', label: 'Password', type: 'password', placeholder: '••••••' },
    ]},
    { id: 'databricks', name: 'Databricks', category: 'Cloud Warehouses', description: 'Unified analytics platform built on Apache Spark.', color: '#FF3621', logo: '🧱', fields: [
      { key: 'host', label: 'Workspace Host', type: 'text', placeholder: 'xxx.azuredatabricks.net' },
      { key: 'http_path', label: 'HTTP Path', type: 'text', placeholder: '/sql/1.0/warehouses/xxx' },
      { key: 'access_token', label: 'Access Token', type: 'password', placeholder: 'dapi••••••' },
      { key: 'catalog', label: 'Catalog', type: 'text', placeholder: 'hive_metastore' },
    ]},
  ],
  'Cloud Storage': [
    { id: 's3', name: 'Amazon S3', category: 'Cloud Storage', description: 'Scalable object storage for data lakes and archives.', color: '#FF9900', logo: '🪣', popular: true, fields: [
      { key: 'bucket', label: 'Bucket Name', type: 'text', placeholder: 'my-data-lake' },
      { key: 'region', label: 'Region', type: 'text', placeholder: 'us-east-1' },
      { key: 'aws_access_key_id', label: 'Access Key ID', type: 'text', placeholder: 'AKIAIOSFODNN7EXAMPLE' },
      { key: 'aws_secret_key', label: 'Secret Access Key', type: 'password', placeholder: '••••••' },
    ]},
    { id: 'gcs', name: 'Google Cloud Storage', category: 'Cloud Storage', description: 'Unified object storage for developers and enterprises.', color: '#4285F4', logo: '☁️', fields: [
      { key: 'bucket', label: 'Bucket Name', type: 'text', placeholder: 'my-gcs-bucket' },
      { key: 'credentials_json', label: 'Service Account JSON', type: 'textarea', placeholder: '{"type": "service_account", ...}' },
    ]},
    { id: 'azure_blob', name: 'Azure Blob Storage', category: 'Cloud Storage', description: "Microsoft's massively scalable object storage.", color: '#0078D4', logo: '🔵', fields: [
      { key: 'account_name', label: 'Account Name', type: 'text', placeholder: 'mystorageaccount' },
      { key: 'container', label: 'Container', type: 'text', placeholder: 'mycontainer' },
      { key: 'account_key', label: 'Account Key', type: 'password', placeholder: '••••••' },
    ]},
  ],
  'APIs & SaaS': [
    { id: 'rest_api', name: 'REST API', category: 'APIs & SaaS', description: 'Connect any HTTP/REST API with custom headers and auth.', color: '#10B981', logo: '🌐', fields: [
      { key: 'base_url', label: 'Base URL', type: 'text', placeholder: 'https://api.example.com' },
      { key: 'auth_type', label: 'Auth Type', type: 'select', options: ['None', 'Bearer Token', 'API Key', 'Basic Auth'] },
      { key: 'auth_value', label: 'Token / Key', type: 'password', placeholder: 'your-api-key' },
    ]},
    { id: 'google_sheets', name: 'Google Sheets', category: 'APIs & SaaS', description: 'Pull data directly from Google Sheets spreadsheets.', color: '#34A853', logo: '📊', popular: true, fields: [
      { key: 'spreadsheet_id', label: 'Spreadsheet ID', type: 'text', placeholder: '1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms' },
      { key: 'range', label: 'Range', type: 'text', placeholder: 'Sheet1!A1:Z1000' },
      { key: 'credentials_json', label: 'Service Account JSON', type: 'textarea', placeholder: '{"type": "service_account", ...}' },
    ]},
    { id: 'salesforce', name: 'Salesforce', category: 'APIs & SaaS', description: 'CRM data — leads, opportunities, accounts, contacts.', color: '#00A1E0', logo: '☁️', fields: [
      { key: 'instance_url', label: 'Instance URL', type: 'text', placeholder: 'https://yourorg.salesforce.com' },
      { key: 'access_token', label: 'Access Token', type: 'password', placeholder: '••••••' },
    ]},
    { id: 'stripe', name: 'Stripe', category: 'APIs & SaaS', description: 'Payment and subscription data from Stripe.', color: '#635BFF', logo: '💳', fields: [
      { key: 'api_key', label: 'Secret Key', type: 'password', placeholder: 'sk_live_••••••' },
    ]},
  ],
  'Files': [
    { id: 'csv', name: 'CSV / Excel', category: 'Files', description: 'Upload or point to a CSV, TSV, XLSX or Parquet file.', color: '#10B981', logo: '📄', popular: true, fields: [
      { key: 'file_path', label: 'File Path or Upload', type: 'text', placeholder: '/data/sales.csv' },
      { key: 'delimiter', label: 'Delimiter', type: 'select', options: [',', ';', '|', '\\t'] },
    ]},
    { id: 'json', name: 'JSON / JSONL', category: 'Files', description: 'Ingest from a local JSON or JSONL file or URL.', color: '#F59E0B', logo: '📋', fields: [
      { key: 'file_path', label: 'File Path or URL', type: 'text', placeholder: '/data/events.jsonl' },
    ]},
    { id: 'parquet', name: 'Parquet', category: 'Files', description: 'Columnar storage format optimised for analytics.', color: '#8B5CF6', logo: '🗂️', fields: [
      { key: 'file_path', label: 'File Path', type: 'text', placeholder: '/data/warehouse.parquet' },
    ]},
  ],
}

function ConnectorLogo({ url, domain, emoji, size = 22 }: { url?: string; domain?: string; emoji?: string; size?: number }) {
  const [failed, setFailed] = useState(false)
  // Explicit override URL wins; otherwise fall back to the Brandfetch domain lookup.
  const src = url
    ? url
    : domain && BRANDFETCH_ID
      ? `https://cdn.brandfetch.io/${domain}/w/${size * 2}/h/${size * 2}?c=${BRANDFETCH_ID}`
      : ''
  if (src && !failed) {
    return (
      <img
        src={src}
        alt=""
        width={size}
        height={size}
        style={{ objectFit: 'contain', borderRadius: 4 }}
        onError={() => setFailed(true)}
      />
    )
  }
  return <span style={{ fontSize: size * 0.9, lineHeight: 1 }}>{emoji}</span>
}

// ── Category icon map ──────────────────────────────────────────────────────────
const CategoryIcon: Record<string, LucideIcon> = {
  'Databases':        Database,
  'Cloud Warehouses': Cloud,
  'Cloud Storage':    HardDrive,
  'APIs & SaaS':      Code2,
  'Pipeline & ETL':   Layers,
  'Files':            HardDrive,
}

const ConnStatusBadge = ({ status }: { status: string }) => {
  const map: Record<string, { label: string; color: string; bg: string; icon: LucideIcon }> = {
    connected: { label: 'Connected',  color: '#4ADE80', bg: 'rgba(74,222,128,0.15)',   icon: CheckCircle2 },
    error:     { label: 'Error',      color: '#EF4444', bg: 'rgba(239,68,68,0.15)',     icon: XCircle      },
    untested:  { label: 'Not tested', color: '#94A3B8', bg: 'rgba(100,116,139,0.15)',   icon: Clock        },
  }
  const s = map[status] || map['untested']
  const Icon = s.icon
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium"
      style={{ color: s.color, background: s.bg }}>
      <Icon size={10} /> {s.label}
    </span>
  )
}

// ── Connector Card (catalog) ───────────────────────────────────────────────────
function ConnectorCard({
  connector,
  connected,
  onAdd,
}: {
  connector: CatalogConnector
  connected: boolean
  onAdd: (c: CatalogConnector) => void
}) {
  const [hovered, setHovered] = useState(false)
  return (
    <button
      onClick={() => onAdd(connector)}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      className="group relative flex flex-col gap-3 text-left transition-all duration-200"
      style={{
        background: T.card,
        border: `1px solid ${hovered ? 'rgba(14,165,233,0.55)' : T.border}`,
        borderRadius: 12,
        padding: 16,
        boxShadow: hovered ? '0 0 0 3px rgba(14,165,233,0.10), 0 8px 24px rgba(0,0,0,0.3)' : 'none',
        transform: hovered ? 'translateY(-2px)' : 'none',
      }}>
      {connected ? (
        <span className="absolute top-2.5 right-2.5 inline-flex items-center gap-1 text-[9px] font-semibold px-1.5 py-0.5 rounded-full"
          style={{ background: 'rgba(74,222,128,0.15)', color: '#4ADE80' }}>
          <CheckCircle2 size={9} /> Connected
        </span>
      ) : connector.popular ? (
        <span className="absolute top-2.5 right-2.5 text-[9px] font-semibold px-1.5 py-0.5 rounded-full"
          style={{ background: 'rgba(96,165,250,0.2)', color: '#60A5FA' }}>
          Popular
        </span>
      ) : null}
      <div className="flex items-center gap-3">
        <div
          className="w-10 h-10 rounded-xl flex items-center justify-center text-xl flex-shrink-0"
          style={{ background: `${connector.color}20` }}>
          <ConnectorLogo url={connector.logo_url} domain={connector.domain} emoji={connector.logo} size={24} />
        </div>
        <div className="min-w-0">
          <p className="truncate" style={{ fontSize: 14, fontWeight: 600, color: T.textPrimary }}>{connector.name}</p>
          <p style={{ fontSize: 10, color: T.textLabel, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            {connector.category}
          </p>
        </div>
      </div>
      <p className="leading-relaxed line-clamp-2" style={{ fontSize: 12, color: T.textMuted }}>
        {connector.description}
      </p>
      <div
        className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity"
        style={{ fontSize: 12, fontWeight: 500, color: T.sky }}>
        <Plus size={12} /> Connect
      </div>
    </button>
  )
}

// ── Add Connection Dialog ──────────────────────────────────────────────────────
const inputStyle: React.CSSProperties = {
  background: T.input,
  border: `1px solid ${T.border}`,
  borderRadius: 8,
  color: T.textPrimary,
  width: '100%',
  padding: '8px 12px',
  fontSize: 13,
  outline: 'none',
}

function AddConnectionDialog({
  connector: initialConnector,
  allConnectors,
  open,
  onClose,
  onSaved,
}: {
  connector: CatalogConnector | null
  allConnectors: CatalogConnector[]
  open: boolean
  onClose: () => void
  onSaved: () => void
}) {
  const [connectorId, setConnectorId] = useState<string>(initialConnector?.id || '')
  const [name, setName] = useState('')
  const [fields, setFields] = useState<Record<string, string>>({})
  const [notes, setNotes] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [uploading, setUploading] = useState(false)

  // Sync when opened with a preselected connector (or reset when opened blank)
  useEffect(() => {
    if (open) {
      setConnectorId(initialConnector?.id || '')
      setName(initialConnector ? `My ${initialConnector.name}` : '')
      setFields({})
      setNotes('')
      setError('')
    }
  }, [open, initialConnector])

  const connector = allConnectors.find(c => c.id === connectorId) || null

  const handlePickConnector = (id: string) => {
    setConnectorId(id)
    const c = allConnectors.find(x => x.id === id)
    if (c) setName(`My ${c.name}`)
    setFields({})
  }

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true); setError('')
    try {
      const fd = new FormData()
      fd.append('file', file)
      const r = await api.post('/api/connectors/upload', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
      const d = r.data
      setFields(p => ({ ...p, file_path: d.file_path, file_format: d.file_format }))
    } catch {
      setError('Upload failed — try again')
    } finally {
      setUploading(false)
    }
  }

  const handleSave = async () => {
    if (!connector) { setError('Pick a connector type first'); return }
    if (!name.trim()) { setError('Connection name is required'); return }
    setSaving(true)
    setError('')
    try {
      await createConnection({
        connector_id: connector.id,
        name: name.trim(),
        credentials: fields,
        notes,
      })
      onSaved()
      onClose()
    } catch (e: unknown) {
      setError((e as Error).message || 'Failed to save connection')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-md" style={{ background: T.card, border: `1px solid ${T.border}` }}>
        <DialogHeader>
          <DialogTitle style={{ color: T.textPrimary }}>
            <span className="flex items-center gap-3">
              {connector && (
                <span className="w-9 h-9 rounded-xl flex items-center justify-center text-lg"
                  style={{ background: `${connector.color}20` }}>
                  <ConnectorLogo url={connector.logo_url} domain={connector.domain} emoji={connector.logo} size={22} />
                </span>
              )}
              {connector ? `Connect ${connector.name}` : 'Add Connection'}
            </span>
          </DialogTitle>
        </DialogHeader>

        <div className="overflow-y-auto space-y-4" style={{ maxHeight: '60vh', paddingRight: 4 }}>
          {/* Connector type picker (shown when opened from the header button) */}
          {!initialConnector && (
            <div>
              <label className="block mb-1.5" style={{ fontSize: 12, fontWeight: 500, color: T.textPrimary }}>
                Connector Type *
              </label>
              <select value={connectorId} onChange={e => handlePickConnector(e.target.value)} style={inputStyle}>
                <option value="">Select a connector…</option>
                {allConnectors.map(c => (
                  <option key={c.id} value={c.id}>{c.name} — {c.category}</option>
                ))}
              </select>
            </div>
          )}

          {/* Connection name */}
          <div>
            <label className="block mb-1.5" style={{ fontSize: 12, fontWeight: 500, color: T.textPrimary }}>
              Connection Name *
            </label>
            <input
              value={name}
              onChange={e => setName(e.target.value)}
              className="focus:ring-1 focus:ring-sky-500"
              style={inputStyle}
              placeholder="e.g. prod-postgres"
            />
          </div>

          {/* Credential fields */}
          {(connector?.fields || []).map((f: ConnectorField) => (
            <div key={f.key}>
              <label className="block mb-1.5" style={{ fontSize: 12, fontWeight: 500, color: T.textPrimary }}>
                {f.label}
              </label>
              {f.type === 'textarea' ? (
                <textarea
                  rows={4}
                  value={fields[f.key] || ''}
                  onChange={e => setFields(p => ({ ...p, [f.key]: e.target.value }))}
                  className="font-mono resize-none focus:ring-1 focus:ring-sky-500"
                  style={{ ...inputStyle, fontSize: 12 }}
                  placeholder={f.placeholder || ''}
                />
              ) : f.type === 'select' ? (
                <select
                  value={fields[f.key] || ''}
                  onChange={e => setFields(p => ({ ...p, [f.key]: e.target.value }))}
                  style={inputStyle}>
                  <option value="">Select…</option>
                  {(f.options || []).map((opt: string) => (
                    <option key={opt} value={opt}>{opt}</option>
                  ))}
                </select>
              ) : f.key === 'file_path' ? (
                <div className="space-y-2">
                  <input
                    type="text"
                    value={fields[f.key] || ''}
                    onChange={e => setFields(p => ({ ...p, [f.key]: e.target.value }))}
                    className="font-mono focus:ring-1 focus:ring-sky-500"
                    style={inputStyle}
                    placeholder={f.placeholder || 'path or upload a file →'}
                  />
                  <label className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg cursor-pointer transition-colors hover:bg-white/5"
                    style={{ border: `1px dashed ${T.border}`, color: T.textMuted, fontSize: 12, fontWeight: 500 }}>
                    <input type="file" className="hidden" accept=".csv,.tsv,.parquet,.xlsx,.xls"
                      onChange={handleUpload} disabled={uploading} />
                    {uploading ? <><RefreshCw size={12} className="animate-spin" /> Uploading…</> : <>⬆ Upload a file</>}
                  </label>
                  {fields.file_path?.startsWith('data/uploads/') && (
                    <p className="text-[11px]" style={{ color: '#4ADE80' }}>✓ uploaded — ready to use</p>
                  )}
                </div>
              ) : (
                <input
                  type={f.type === 'password' ? 'password' : f.type === 'number' ? 'number' : 'text'}
                  value={fields[f.key] || ''}
                  onChange={e => setFields(p => ({ ...p, [f.key]: e.target.value }))}
                  className="focus:ring-1 focus:ring-sky-500"
                  style={inputStyle}
                  placeholder={f.placeholder || ''}
                />
              )}
            </div>
          ))}

          {/* Notes */}
          <div>
            <label className="block mb-1.5" style={{ fontSize: 12, fontWeight: 500, color: T.textMuted }}>
              Notes (optional)
            </label>
            <input
              value={notes}
              onChange={e => setNotes(e.target.value)}
              className="focus:ring-1 focus:ring-sky-500"
              style={inputStyle}
              placeholder="e.g. Production read-replica"
            />
          </div>

          {error && (
            <p className="text-xs px-3 py-2 rounded-lg" style={{ color: '#EF4444', background: 'rgba(239,68,68,0.1)' }}>{error}</p>
          )}
        </div>

        <div className="flex gap-3 pt-2">
          <button
            onClick={onClose}
            className="flex-1 py-2 rounded-lg transition-colors hover:bg-white/5"
            style={{ border: `1px solid ${T.border}`, color: T.textMuted, fontSize: 13, fontWeight: 500 }}>
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving || !connector}
            className="flex-1 py-2 rounded-lg text-white transition-all disabled:opacity-50"
            style={{ background: T.sky, fontSize: 13, fontWeight: 600 }}>
            {saving ? 'Saving…' : 'Save Connection'}
          </button>
        </div>
      </DialogContent>
    </Dialog>
  )
}

// ── Main Page ──────────────────────────────────────────────────────────────────
export default function ConnectorsPage() {
  const qc = useQueryClient()
  const toast = useToast()
  const [search, setSearch] = useState('')
  const [activeCategory, setActiveCategory] = useState('All')
  const [addingConnector, setAddingConnector] = useState<CatalogConnector | null>(null)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [testingId, setTestingId] = useState<string | null>(null)

  const { data: catalogData, isLoading: catalogLoading } = useQuery({
    queryKey: ['connector-catalog'],
    queryFn: fetchCatalog,
    staleTime: Infinity,
  })

  const { data: savedData, isLoading: savedLoading } = useQuery({
    queryKey: ['connector-saved'],
    queryFn: fetchSaved,
    refetchInterval: 30_000,
  })

  // Use backend catalog when available; fall back to static catalog instantly
  const catalog: Record<string, CatalogConnector[]> = catalogData?.catalog || STATIC_CATALOG
  const saved: SavedConnection[] = savedData?.connections || []
  const allConnectors: CatalogConnector[] = useMemo(() => Object.values(catalog).flat(), [catalog])
  const connectedIds = useMemo(() => new Set(saved.map(s => s.connector_id)), [saved])

  const categories = useMemo(() => {
    const cats = Object.keys(catalog)
    return ['All', ...cats]
  }, [catalog])

  const filteredConnectors = useMemo(() => {
    return allConnectors.filter(c => {
      const matchSearch =
        !search ||
        c.name.toLowerCase().includes(search.toLowerCase()) ||
        c.description.toLowerCase().includes(search.toLowerCase()) ||
        c.category.toLowerCase().includes(search.toLowerCase())
      const matchCat = activeCategory === 'All' || c.category === activeCategory
      return matchSearch && matchCat
    })
  }, [allConnectors, search, activeCategory])

  // Group filtered by category for display
  const grouped = useMemo(() => {
    const result: Record<string, any[]> = {}
    filteredConnectors.forEach(c => {
      if (!result[c.category]) result[c.category] = []
      result[c.category].push(c)
    })
    return result
  }, [filteredConnectors])

  const handleDelete = async (id: string) => {
    await deleteConnection(id)
    qc.invalidateQueries({ queryKey: ['connector-saved'] })
  }

  const handleTest = async (id: string) => {
    setTestingId(id)
    try {
      const res = await testConnection(id)
      const ok = res?.status === 'connected'
      const msg = res?.message || res?.detail || (ok ? 'Connection successful' : 'Connection failed')
      toast(msg, ok ? 'success' : 'error')
      qc.invalidateQueries({ queryKey: ['connector-saved'] })
    } catch (e: unknown) {
      toast((e as Error)?.message || 'Test failed — backend unreachable', 'error')
    } finally {
      setTestingId(null)
    }
  }

  const openBlankDialog = () => { setAddingConnector(null); setDialogOpen(true) }
  const openConnectorDialog = (c: CatalogConnector) => { setAddingConnector(c); setDialogOpen(true) }

  const connectedCount = saved.filter(s => s.status === 'connected').length

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: 'easeOut' }}
      style={{ padding: 24 }}
      className="min-h-full space-y-6">

      {/* ── Header ───────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <div>
          <h1 style={{ fontSize: 24, fontWeight: 700, color: T.textPrimary, letterSpacing: '-0.02em' }}>
            Connectors
          </h1>
          <p style={{ fontSize: 13, color: T.textMuted, marginTop: 2 }}>
            Connect a new data source · {catalogData?.total || allConnectors.length} connectors available · {connectedCount} active
          </p>
        </div>
        <button
          onClick={openBlankDialog}
          className="btn-primary inline-flex items-center gap-2 transition-all hover:opacity-90 active:scale-[0.98]"
          style={{ background: T.sky, color: '#fff', borderRadius: 8, padding: '8px 16px', fontSize: 13, fontWeight: 600 }}>
          <Plus size={15} /> Add Connection
        </button>
      </div>

      {/* ── Search + filter bar ──────────────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center">
        <div className="relative flex-1 max-w-xs">
          <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: T.textLabel }} />
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search connectors…"
            className="w-full focus:ring-1 focus:ring-sky-500"
            style={{
              background: T.input, border: `1px solid ${T.border}`, borderRadius: 8,
              color: T.textPrimary, fontSize: 13, padding: '7px 12px 7px 32px', outline: 'none',
            }}
          />
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {categories.map(cat => (
            <button
              key={cat}
              onClick={() => setActiveCategory(cat)}
              className="transition-colors"
              style={{
                fontSize: 12, fontWeight: 500, borderRadius: 999, padding: '5px 12px',
                background: activeCategory === cat ? T.sky : 'transparent',
                color: activeCategory === cat ? '#fff' : T.textMuted,
                border: `1px solid ${activeCategory === cat ? T.sky : T.border}`,
              }}>
              {cat}
            </button>
          ))}
        </div>
      </div>

      {/* ── Catalog grid ─────────────────────────────────────────────────── */}
      {(catalogLoading && allConnectors.length === 0) ? (
        <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-3">
          {Array.from({ length: 8 }).map((_, i) => (
            <SkeletonCard key={i} lines={2} />
          ))}
        </div>
      ) : filteredConnectors.length === 0 ? (
        <div className="text-center py-12">
          <p style={{ fontSize: 13, color: T.textMuted }}>No connectors match &quot;{search}&quot;</p>
        </div>
      ) : (
        <div className="space-y-6">
          {Object.entries(grouped).map(([category, connectors]) => {
            const Icon = CategoryIcon[category] || Database
            return (
              <div key={category}>
                <div className="flex items-center gap-2 mb-3">
                  <Icon size={13} style={{ color: T.textLabel }} />
                  <h3 className="section-header" style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.08em', color: T.textLabel, fontWeight: 600 }}>
                    {category}
                  </h3>
                  <span style={{
                    fontSize: 10, padding: '1px 7px', borderRadius: 999,
                    background: 'rgba(26,58,92,0.5)', color: T.textMuted,
                  }}>
                    {connectors.length}
                  </span>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-3">
                  {connectors.map(c => (
                    <ConnectorCard
                      key={c.id}
                      connector={c}
                      connected={connectedIds.has(c.id)}
                      onAdd={openConnectorDialog}
                    />
                  ))}
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* ── My Connections ───────────────────────────────────────────────── */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <h2 className="section-header" style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.08em', color: T.textLabel, fontWeight: 600 }}>
            My Connections
          </h2>
          {saved.length > 0 && (
            <span style={{
              fontSize: 10, padding: '1px 7px', borderRadius: 999,
              background: 'rgba(14,165,233,0.15)', color: '#38BDF8', fontWeight: 600,
            }}>
              {saved.length}
            </span>
          )}
        </div>

        {savedLoading ? (
          <SkeletonList items={2} />
        ) : saved.length === 0 ? (
          <div style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 12 }}>
            <EmptyState
              icon={Plug}
              title="No connections yet"
              description="Add your first connection to start ingesting data. Choose from PostgreSQL, REST API, CSV, or Google Sheets."
              action={{ label: 'Add Connection', onClick: openBlankDialog }}
            />
          </div>
        ) : (
          <div className="card overflow-hidden" style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 12 }}>
            <table className="w-full data-table">
              <thead>
                <tr style={{ borderBottom: `1px solid ${T.border}` }}>
                  {['Name', 'Type', 'Status', 'Last Tested', ''].map((h, i) => (
                    <th key={i} className="text-left"
                      style={{
                        fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.08em',
                        color: T.textLabel, fontWeight: 600, padding: '10px 20px',
                      }}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {saved.map(conn => (
                  <tr key={conn.id}
                    className="transition-colors hover:bg-white/[0.03]"
                    style={{ borderBottom: `1px solid ${T.border}` }}>
                    <td style={{ padding: '12px 20px' }}>
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg flex items-center justify-center text-base flex-shrink-0"
                          style={{ background: `${conn.connector_color}20` }}>
                          <ConnectorLogo url={conn.connector_logo_url} domain={conn.connector_domain} emoji={conn.connector_logo} size={18} />
                        </div>
                        <div className="min-w-0">
                          <p className="truncate" style={{ fontSize: 13, fontWeight: 600, color: T.textPrimary }}>{conn.name}</p>
                          {conn.test_message && (
                            <p className="text-[10px] mt-0.5 leading-snug truncate"
                              style={{ color: conn.status === 'error' ? '#EF4444' : '#4ADE80', maxWidth: 320 }}
                              title={conn.test_message}>
                              {conn.status === 'error' ? '⚠ ' : '✓ '}{conn.test_message}
                            </p>
                          )}
                        </div>
                      </div>
                    </td>
                    <td style={{ padding: '12px 20px', fontSize: 12, color: T.textMuted, whiteSpace: 'nowrap' }}>
                      {conn.connector_name} · {conn.connector_category}
                    </td>
                    <td style={{ padding: '12px 20px' }}>
                      <ConnStatusBadge status={conn.status ?? 'untested'} />
                    </td>
                    <td style={{ padding: '12px 20px', fontSize: 12, color: T.textMuted, whiteSpace: 'nowrap' }}>
                      {conn.last_tested_at
                        ? formatDistanceToNow(new Date(conn.last_tested_at), { addSuffix: true })
                        : conn.updated_at
                          ? formatDistanceToNow(new Date(conn.updated_at), { addSuffix: true })
                          : '—'}
                    </td>
                    <td style={{ padding: '12px 20px', textAlign: 'right', whiteSpace: 'nowrap' }}>
                      <button
                        onClick={() => handleTest(conn.id)}
                        disabled={testingId === conn.id}
                        title="Test connection"
                        className="inline-flex items-center gap-1.5 mr-2 transition-all hover:bg-sky-500/10 disabled:opacity-50"
                        style={{
                          fontSize: 12, fontWeight: 500, color: T.sky,
                          border: '1px solid rgba(14,165,233,0.3)', borderRadius: 8, padding: '4px 10px',
                        }}>
                        {testingId === conn.id
                          ? <RefreshCw size={11} className="animate-spin" />
                          : <TestTube2 size={11} />}
                        Test
                      </button>
                      <button
                        onClick={() => handleDelete(conn.id)}
                        title="Delete"
                        className="p-1.5 rounded-lg hover:bg-red-500/10 transition-colors"
                        style={{ color: '#EF4444' }}>
                        <Trash2 size={14} className="opacity-60 hover:opacity-100" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Add Connection Dialog */}
      <AddConnectionDialog
        connector={addingConnector}
        allConnectors={allConnectors}
        open={dialogOpen}
        onClose={() => { setDialogOpen(false); setAddingConnector(null) }}
        onSaved={() => qc.invalidateQueries({ queryKey: ['connector-saved'] })}
      />
    </motion.div>
  )
}
