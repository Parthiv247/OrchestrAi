'use client'
import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import {
  Database, GitBranch, Globe, FileText, BarChart2, X, Layers,
  ArrowRight, Code, Search, Table2, Sheet, Snowflake, Workflow,
} from 'lucide-react'
import api from '@/lib/api'
import type { LucideIcon } from '@/lib/types'

// ── Design tokens ───────────────────────────────────────────────────────────────
const T = {
  bodyBg: '#080F1C',
  panelBg: '#09111E',
  panelBorder: '#0F2A48',
  cardBg: '#0F2540',
  border: '#1A3A5C',
  accent: '#0EA5E9',
  violet: '#7C3AED',
  emerald: '#10B981',
  amber: '#F59E0B',
  red: '#EF4444',
  text: '#F1F5F9',
  muted: '#64748B',
  label: '#4B6B8E',
}

// ── Types ──────────────────────────────────────────────────────────────────────
type Layer = 'source' | 'raw' | 'staging' | 'mart' | 'dashboard'

interface GNode {
  id: string
  name: string
  label: string
  layer: Layer
  schema?: string
  description?: string
  columns?: string[]
  column_details?: { name: string; description: string; data_type: string }[]
  raw_code?: string
  path?: string
  status?: 'ok' | 'warning' | 'error'
  icon?: string
  // layout
  col: number
  row: number
}

interface GEdge {
  from: string
  to: string
  column_mappings?: { source_col: string; dest_col: string; transform: string }[]
}

// ── Constants ──────────────────────────────────────────────────────────────────
const NODE_W = 168
const NODE_H = 54
const COL_GAP = 190
const ROW_GAP = 74
const PAD_X = 40
const PAD_Y = 40

const LAYER_STYLE: Record<string, { bg: string; border: string; icon: LucideIcon; label: string; pillColor: string; pillBg: string }> = {
  source:    { bg: 'rgba(14,165,233,0.15)',  border: '#0EA5E9', icon: Globe,     label: 'Source',      pillColor: '#38BDF8', pillBg: 'rgba(14,165,233,0.2)' },
  raw:       { bg: 'rgba(100,116,139,0.12)', border: '#64748B', icon: Database,  label: 'Raw',         pillColor: '#94A3B8', pillBg: 'rgba(100,116,139,0.2)' },
  staging:   { bg: 'rgba(124,58,237,0.15)',  border: '#7C3AED', icon: Layers,    label: 'Transform',   pillColor: '#C084FC', pillBg: 'rgba(192,132,252,0.2)' },
  mart:      { bg: 'rgba(16,185,129,0.15)',  border: '#10B981', icon: GitBranch, label: 'Destination', pillColor: '#4ADE80', pillBg: 'rgba(74,222,128,0.2)' },
  dashboard: { bg: 'rgba(245,158,11,0.12)',  border: '#F59E0B', icon: BarChart2, label: 'Dashboard',   pillColor: '#F59E0B', pillBg: 'rgba(245,158,11,0.2)' },
}

const LAYER_ORDER: Layer[] = ['source', 'raw', 'staging', 'mart', 'dashboard']

const NODE_ICON: Record<string, LucideIcon> = {
  postgres: Database,
  rest: Globe,
  csv: FileText,
  sheets: Sheet,
  dbt: Workflow,
  quality: Table2,
  snowflake: Snowflake,
}

// ── Demo fallback graph (used only when the API returns an empty graph) ─────────
const DEMO_NODES: Omit<GNode, 'col' | 'row'>[] = [
  { id: 'src_postgres', name: 'PostgreSQL',    label: 'PostgreSQL',    layer: 'source',  icon: 'postgres', description: 'Operational OLTP database — orders, customers, products.', columns: ['order_id', 'customer_id', 'total', 'created_at'], status: 'ok' },
  { id: 'src_rest',     name: 'REST API',      label: 'REST API',      layer: 'source',  icon: 'rest',     description: 'External REST connector polling JSON payloads every 15 min.', columns: ['event_id', 'payload', 'ts'], status: 'ok' },
  { id: 'src_csv',      name: 'CSV Upload',    label: 'CSV Upload',    layer: 'source',  icon: 'csv',      description: 'Manual CSV file drops ingested via the upload connector.', columns: ['row_id', 'sku', 'qty'], status: 'warning' },
  { id: 'src_sheets',   name: 'Google Sheets', label: 'Google Sheets', layer: 'source',  icon: 'sheets',   description: 'Marketing budget sheet synced hourly.', columns: ['campaign', 'spend', 'date'], status: 'ok' },
  { id: 'tr_dbt',       name: 'dbt Transform', label: 'dbt Transform', layer: 'staging', icon: 'dbt',      description: 'dbt models: staging + marts build, incremental strategy.', columns: ['order_id', 'customer_id', 'revenue', 'loaded_at'], status: 'ok' },
  { id: 'tr_quality',   name: 'Quality Check', label: 'Quality Check', layer: 'staging', icon: 'quality',  description: 'Row-count, null % and freshness gates before load.', columns: ['check_id', 'status'], status: 'ok' },
  { id: 'dst_snowflake', name: 'Snowflake',    label: 'Snowflake',     layer: 'mart',    icon: 'snowflake', description: 'Analytics warehouse — marts schema serves BI and the AI Analyst.', columns: ['order_id', 'customer_id', 'revenue', 'loaded_at'], status: 'ok' },
]

const DEMO_EDGES: GEdge[] = [
  { from: 'src_postgres', to: 'tr_dbt', column_mappings: [
    { source_col: 'orders.total',      dest_col: 'fct_orders.revenue',   transform: 'SUM()' },
    { source_col: 'orders.order_id',   dest_col: 'fct_orders.order_id',  transform: 'passthrough' },
    { source_col: 'customers.id',      dest_col: 'dim_customers.customer_id', transform: 'alias' },
  ]},
  { from: 'src_rest', to: 'tr_dbt', column_mappings: [
    { source_col: 'events.payload',    dest_col: 'stg_events.attributes', transform: 'inferred' },
    { source_col: 'events.ts',         dest_col: 'stg_events.event_at',   transform: 'alias' },
  ]},
  { from: 'src_csv', to: 'tr_quality', column_mappings: [
    { source_col: 'upload.sku',        dest_col: 'stg_inventory.sku',     transform: 'passthrough' },
    { source_col: 'upload.qty',        dest_col: 'stg_inventory.quantity', transform: 'alias' },
  ]},
  { from: 'src_sheets', to: 'tr_quality', column_mappings: [
    { source_col: 'budget.spend',      dest_col: 'stg_marketing.spend_usd', transform: 'passthrough' },
  ]},
  { from: 'tr_dbt', to: 'dst_snowflake', column_mappings: [
    { source_col: 'fct_orders.revenue', dest_col: 'marts.fct_orders.revenue', transform: 'passthrough' },
    { source_col: 'dim_customers.customer_id', dest_col: 'marts.dim_customers.customer_id', transform: 'passthrough' },
  ]},
  { from: 'tr_quality', to: 'dst_snowflake', column_mappings: [
    { source_col: 'stg_inventory.quantity', dest_col: 'marts.fct_inventory.qty', transform: 'alias' },
    { source_col: 'stg_marketing.spend_usd', dest_col: 'marts.fct_marketing.spend', transform: 'passthrough' },
  ]},
]

// ── Layout assignment (preserved logic) ─────────────────────────────────────────
function assignLayout(rawNodes: Omit<GNode, 'col' | 'row'>[], edges: GEdge[]): GNode[] {
  const colIndex: Record<string, number> = {}
  LAYER_ORDER.forEach((l, i) => { colIndex[l] = i })

  const byLayer: Record<string, any[]> = {}
  for (const n of rawNodes) {
    const layer = n.layer || 'raw'
    if (!byLayer[layer]) byLayer[layer] = []
    byLayer[layer].push(n)
  }

  // Add dashboard nodes if no dashboard layer in data
  if (!byLayer['dashboard']) {
    byLayer['dashboard'] = [
      { id: 'dash_analyst',   name: 'AI Analyst',     label: 'AI Analyst',     layer: 'dashboard' },
      { id: 'dash_optimizer', name: 'Cost Optimizer', label: 'Cost Optimizer', layer: 'dashboard' },
    ]
  }

  // Compact columns: only keep layers that actually have nodes, in order
  const usedLayers = LAYER_ORDER.filter(l => (byLayer[l] || []).length > 0)
  const compactCol: Record<string, number> = {}
  usedLayers.forEach((l, i) => { compactCol[l] = i })

  const nodes: GNode[] = []
  for (const [layer, items] of Object.entries(byLayer)) {
    const col = compactCol[layer] ?? colIndex[layer] ?? 1
    // Center shorter columns vertically against the tallest column
    const maxLen = Math.max(...Object.values(byLayer).map(v => v.length))
    const offset = (maxLen - items.length) / 2
    items.forEach((n: Omit<GNode, 'col' | 'row'>, row: number) => {
      nodes.push({ ...n, col, row: row + offset })
    })
  }
  return nodes
}

// ── SVG helpers ────────────────────────────────────────────────────────────────
function nx(col: number) { return PAD_X + col * (NODE_W + COL_GAP) }
function ny(row: number) { return PAD_Y + row * ROW_GAP }
function ncy(row: number) { return ny(row) + NODE_H / 2 }

// ── Canvas ─────────────────────────────────────────────────────────────────────
function LineageCanvas({ nodes, edges, selected, onSelect, highlightEdge, searchTerm }: {
  nodes: GNode[]
  edges: GEdge[]
  selected: GNode | null
  onSelect: (n: GNode | null) => void
  highlightEdge: GEdge | null
  searchTerm: string
}) {
  const [hovered, setHovered] = useState<GNode | null>(null)
  const nodeMap = Object.fromEntries(nodes.map(n => [n.id, n]))
  const maxRow = Math.max(...nodes.map(n => n.row), 0)
  const maxCol = Math.max(...nodes.map(n => n.col), 0)
  const svgW = PAD_X * 2 + (maxCol + 1) * (NODE_W + COL_GAP) - COL_GAP
  const svgH = Math.max(PAD_Y * 2 + (maxRow + 1) * ROW_GAP, 480)

  const matches = (n: GNode) =>
    !searchTerm || n.label.toLowerCase().includes(searchTerm.toLowerCase()) || n.name.toLowerCase().includes(searchTerm.toLowerCase())

  return (
    <div className="relative">
      <svg width={svgW} height={svgH} className="overflow-visible" style={{ minWidth: '100%' }}>
        <defs>
          <linearGradient id="edgeGrad" x1="0" y1="0" x2={svgW} y2="0" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#0EA5E9" />
            <stop offset="50%" stopColor="#7C3AED" />
            <stop offset="100%" stopColor="#10B981" />
          </linearGradient>
          <marker id="arrowhead" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto">
            <path d="M0,0 L0,7 L7,3.5 z" fill="rgba(100,116,139,0.55)" />
          </marker>
          <marker id="arrowhead-active" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto">
            <path d="M0,0 L0,7 L7,3.5 z" fill="#38BDF8" />
          </marker>
          <style>{`
            @keyframes lineage-dash { to { stroke-dashoffset: -24; } }
            .lineage-flow { stroke-dasharray: 7 5; animation: lineage-dash 1.2s linear infinite; }
          `}</style>
        </defs>

        {/* Edges */}
        {edges.map((e, i) => {
          const from = nodeMap[e.from]
          const to = nodeMap[e.to]
          if (!from || !to) return null
          const x1 = nx(from.col) + NODE_W
          const y1 = ncy(from.row)
          const x2 = nx(to.col)
          const y2 = ncy(to.row)
          const mx = (x1 + x2) / 2
          const isActive = selected?.id === e.from || selected?.id === e.to
          const isHighlighted = highlightEdge?.from === e.from && highlightEdge?.to === e.to
          return (
            <path
              key={i}
              className="lineage-flow"
              d={`M ${x1} ${y1} C ${mx} ${y1}, ${mx} ${y2}, ${x2} ${y2}`}
              fill="none"
              stroke={isHighlighted ? '#A78BFA' : isActive ? '#38BDF8' : 'url(#edgeGrad)'}
              strokeWidth={isHighlighted ? 2.5 : isActive ? 2 : 1.5}
              strokeOpacity={isActive || isHighlighted ? 1 : 0.35}
              markerEnd={isActive || isHighlighted ? 'url(#arrowhead-active)' : 'url(#arrowhead)'}
            />
          )
        })}

        {/* Nodes */}
        {nodes.map(n => {
          const style = LAYER_STYLE[n.layer] || LAYER_STYLE.raw
          const x = nx(n.col)
          const y = ny(n.row)
          const isSelected = selected?.id === n.id
          const isConnected = selected && edges.some(e => (e.from === n.id && e.to === selected.id) || (e.from === selected.id && e.to === n.id))
          const dim = !matches(n)
          const statusColor = n.status === 'error' ? T.red : n.status === 'warning' ? T.amber : T.emerald
          return (
            <g
              key={n.id}
              onClick={() => onSelect(isSelected ? null : n)}
              onMouseEnter={() => setHovered(n)}
              onMouseLeave={() => setHovered(null)}
              style={{ cursor: 'pointer', opacity: dim ? 0.2 : 1, transition: 'opacity 0.2s' }}>
              <rect
                x={x} y={y} width={NODE_W} height={NODE_H} rx={8}
                fill={style.bg}
                stroke={isSelected ? style.border : isConnected ? style.border + '80' : style.border + '66'}
                strokeWidth={isSelected ? 2 : isConnected ? 1.5 : 1}
              />
              {isSelected && (
                <rect
                  x={x - 3} y={y - 3} width={NODE_W + 6} height={NODE_H + 6} rx={10}
                  fill="none" stroke={style.border} strokeWidth={1.5} opacity={0.45}
                  style={{ filter: `drop-shadow(0 0 10px ${style.border})` }}
                />
              )}
              <text x={x + 12} y={y + 20} fontSize={9} fill={style.border} fontWeight="700" letterSpacing="0.08em">
                {style.label.toUpperCase()}
              </text>
              <text x={x + 12} y={y + 38} fontSize={11.5} fill="#F1F5F9" fontFamily="ui-monospace,monospace">
                {n.label.length > 19 ? n.label.slice(0, 18) + '…' : n.label}
              </text>
              {n.status && <circle cx={x + NODE_W - 12} cy={y + 14} r={3.5} fill={statusColor} />}
              {n.columns && n.columns.length > 0 && (
                <text x={x + NODE_W - 10} y={y + 38} fontSize={9} fill="rgba(148,163,184,0.7)" textAnchor="end">
                  {n.columns.length} cols
                </text>
              )}
            </g>
          )
        })}
      </svg>

      {/* Hover tooltip card */}
      {hovered && hovered.id !== selected?.id && (
        <div
          className="absolute z-20 w-64 rounded-xl p-3 pointer-events-none shadow-2xl"
          style={{
            left: Math.min(nx(hovered.col) + NODE_W + 12, svgW - 270),
            top: ny(hovered.row) - 4,
            background: T.cardBg,
            border: `1px solid ${T.border}`,
          }}>
          <div className="flex items-center gap-2 mb-1.5">
            <span className="text-[10px] px-1.5 py-0.5 rounded-full font-semibold"
              style={{ color: LAYER_STYLE[hovered.layer]?.pillColor, background: LAYER_STYLE[hovered.layer]?.pillBg }}>
              {LAYER_STYLE[hovered.layer]?.label || hovered.layer}
            </span>
            <span className="text-xs font-mono font-semibold" style={{ color: T.text }}>{hovered.label}</span>
          </div>
          {hovered.description && (
            <p className="text-[11px] leading-relaxed" style={{ color: T.muted }}>{hovered.description}</p>
          )}
          {hovered.columns && hovered.columns.length > 0 && (
            <p className="text-[10px] mt-1.5 font-mono truncate" style={{ color: T.label }}>
              {hovered.columns.slice(0, 4).join(' · ')}{hovered.columns.length > 4 ? ' …' : ''}
            </p>
          )}
          <p className="text-[10px] mt-1.5" style={{ color: T.label }}>Click to open details</p>
        </div>
      )}
    </div>
  )
}

// ── Column lineage detail (preserved API logic) ─────────────────────────────────
function ColumnLineageView({ nodeName, edges, nodes }: {
  nodeName: string
  edges: GEdge[]
  nodes: GNode[]
}) {
  const nodeMap = Object.fromEntries(nodes.map(n => [n.id, n]))

  const inboundEdges = edges.filter(e => {
    const toNode = nodeMap[e.to]
    return toNode?.name === nodeName && (e.column_mappings?.length ?? 0) > 0
  })

  const { data, isLoading } = useQuery({
    queryKey: ['column-lineage', nodeName],
    queryFn: () => api.get(`/api/lineage/columns/${nodeName}`).then(r => r.data),
    staleTime: 300_000,
    refetchInterval: 60_000,
  })

  const apiMappings = data?.column_lineage || []

  const allMappings = [...apiMappings]
  if (allMappings.length === 0) {
    inboundEdges.forEach(e => {
      const fromNode = nodeMap[e.from]
      if (fromNode && e.column_mappings?.length) {
        allMappings.push({
          from_node: fromNode.name || fromNode.label,
          to_node: nodeName,
          mappings: e.column_mappings,
        })
      }
    })
  }

  if (isLoading) return (
    <div className="space-y-1.5 animate-pulse">
      {[1, 2, 3].map(i => <div key={i} className="h-8 rounded" style={{ background: 'rgba(255,255,255,0.05)' }} />)}
    </div>
  )

  if (allMappings.length === 0) return (
    <p className="text-xs" style={{ color: T.muted }}>No column lineage data available for this node.</p>
  )

  const transformColor: Record<string, string> = {
    passthrough: T.emerald, alias: T.amber, inferred: T.violet, 'SUM()': T.accent,
  }

  return (
    <div className="space-y-4">
      {allMappings.map((group: { from_node: string; to_node: string; mappings: { source_col: string; dest_col: string; transform: string }[] }, gi: number) => (
        <div key={gi}>
          <p className="text-[10px] font-semibold uppercase mb-2" style={{ letterSpacing: '0.08em', color: T.label }}>
            {group.from_node} → {group.to_node}
          </p>
          <div className="space-y-1">
            {group.mappings.map((m: { source_col: string; dest_col: string; transform: string }, i: number) => (
              <div key={i} className="flex items-center gap-2 p-1.5 rounded-lg"
                style={{ background: '#0B1E35', border: `1px solid ${T.border}` }}>
                <span className="text-xs font-mono truncate flex-1" style={{ color: T.text }}>{m.source_col}</span>
                <ArrowRight size={10} style={{ color: T.muted, flexShrink: 0 }} />
                <span className="text-xs font-mono truncate flex-1" style={{ color: '#38BDF8' }}>{m.dest_col}</span>
                <span className="text-[9px] px-1.5 py-0.5 rounded font-semibold flex-shrink-0"
                  style={{ background: (transformColor[m.transform] || '#94A3B8') + '20', color: transformColor[m.transform] || '#94A3B8' }}>
                  {m.transform}
                </span>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

// ── Page ───────────────────────────────────────────────────────────────────────
type SidePanelTab = 'info' | 'columns' | 'sql'

export default function LineagePage() {
  const [selected, setSelected] = useState<GNode | null>(null)
  const [highlightEdge, setHighlightEdge] = useState<GEdge | null>(null)
  const [sideTab, setSideTab] = useState<SidePanelTab>('info')
  const [showColumnLineage, setShowColumnLineage] = useState(false)
  const [search, setSearch] = useState('')

  const { data: graphData, isLoading } = useQuery({
    queryKey: ['lineage-graph'],
    queryFn: () => api.get('/api/lineage/graph').then(r => r.data),
    staleTime: 300_000,
    refetchInterval: 60_000,
  })

  const apiNodes: Omit<GNode, 'col' | 'row'>[] = graphData?.nodes || []
  const apiEdges: GEdge[] = graphData?.edges || []
  const usingDemo = !isLoading && apiNodes.length === 0
  const rawNodes = usingDemo ? DEMO_NODES : apiNodes
  const rawEdges = usingDemo ? DEMO_EDGES : apiEdges
  const dataSource: string = usingDemo ? 'demo' : (graphData?.source || 'loading')

  const nodes: GNode[] = useMemo(() => assignLayout(rawNodes, rawEdges), [rawNodes, rawEdges])
  const edges = rawEdges

  const upstreamEdges = selected ? edges.filter(e => e.to === selected.id) : []
  const downstreamEdges = selected ? edges.filter(e => e.from === selected.id) : []
  const nodeMap = Object.fromEntries(nodes.map(n => [n.id, n]))

  // Flat column-lineage rows for the table below the graph
  const columnRows = useMemo(() => {
    const rows: { source: string; transform: string; dest: string; via: string }[] = []
    edges.forEach(e => {
      const from = nodeMap[e.from]
      const to = nodeMap[e.to]
      ;(e.column_mappings || []).forEach(m => {
        rows.push({
          source: from ? `${from.label}.${m.source_col}` : m.source_col,
          transform: m.transform,
          dest: to ? `${to.label}.${m.dest_col}` : m.dest_col,
          via: to?.label || '',
        })
      })
    })
    return rows
  }, [edges, nodeMap])

  const legendItems = [
    { color: T.accent,  label: 'Source' },
    { color: T.violet,  label: 'Transform' },
    { color: T.emerald, label: 'Destination' },
    { color: T.amber,   label: 'Warning' },
    { color: T.red,     label: 'Error' },
  ]

  return (
    <div className="flex h-[calc(100vh-56px)]" style={{ background: T.bodyBg }}>
      {/* ── Main column ─────────────────────────────────────────────────────── */}
      <div className="flex-1 overflow-auto min-w-0" style={{ padding: 24 }}>

        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
          className="mb-4 flex items-center justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-xl font-bold" style={{ color: T.text }}>Data Lineage</h1>
            <p className="text-xs mt-1" style={{ color: T.muted }}>
              {isLoading ? 'Loading manifest…' : `${nodes.length} nodes · ${edges.length} edges · source: ${dataSource}`}
            </p>
          </div>
          <div className="flex items-center gap-2">
            {/* Search */}
            <div className="flex items-center gap-2 px-3 py-2 rounded-lg w-56" style={{ background: T.cardBg, border: `1px solid ${T.border}` }}>
              <Search size={13} style={{ color: T.muted }} />
              <input
                value={search}
                onChange={e => setSearch(e.target.value)}
                placeholder="Search nodes..."
                className="flex-1 bg-transparent text-xs focus:outline-none min-w-0"
                style={{ color: T.text }} />
              {search && <button onClick={() => setSearch('')}><X size={11} style={{ color: T.muted }} /></button>}
            </div>
            {/* Column-level toggle */}
            <button
              onClick={() => setShowColumnLineage(v => !v)}
              className="flex items-center gap-2 text-xs px-3 py-2 rounded-lg font-semibold transition-all"
              style={{
                background: showColumnLineage ? 'rgba(124,58,237,0.2)' : T.cardBg,
                color: showColumnLineage ? '#A78BFA' : T.muted,
                border: `1px solid ${showColumnLineage ? T.violet : T.border}`,
              }}>
              <Table2 size={13} /> Column-level view
            </button>
          </div>
        </motion.div>

        {/* Legend row */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.3, delay: 0.05 }}
          className="mb-4 flex items-center gap-5 px-4 py-2.5 rounded-xl flex-wrap"
          style={{ background: T.cardBg, border: `1px solid ${T.border}` }}>
          {legendItems.map((l, i) => (
            <span key={l.label} className="flex items-center gap-2 text-xs" style={{ color: T.muted }}>
              <span className="w-2.5 h-2.5 rounded-full" style={{ background: l.color }} />
              {l.label}
              {i < 2 && <ArrowRight size={11} className="ml-1" style={{ color: T.label }} />}
            </span>
          ))}
          <span className="ml-auto text-[10px] uppercase font-semibold" style={{ letterSpacing: '0.08em', color: T.label }}>
            Data flows left → right
          </span>
        </motion.div>

        {/* Lineage graph */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.1 }}
          className="rounded-xl overflow-auto"
          style={{ background: T.panelBg, border: `1px solid ${T.border}`, minHeight: 480 }}>
          {isLoading ? (
            <div className="flex items-center justify-center" style={{ height: 480 }}>
              <div className="flex gap-1.5">
                {[0, 1, 2].map(i => <div key={i} className="w-2 h-2 rounded-full animate-bounce" style={{ background: T.accent, animationDelay: `${i * 0.15}s` }} />)}
              </div>
            </div>
          ) : (
            <LineageCanvas
              nodes={nodes}
              edges={edges}
              selected={selected}
              onSelect={n => { setSelected(n); setSideTab('info') }}
              highlightEdge={highlightEdge}
              searchTerm={search}
            />
          )}
        </motion.div>

        {/* Column lineage table (below graph) */}
        {showColumnLineage && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
            className="mt-5 rounded-xl overflow-hidden"
            style={{ background: T.cardBg, border: `1px solid ${T.border}` }}>
            <div className="px-4 py-3 flex items-center justify-between" style={{ borderBottom: `1px solid ${T.border}` }}>
              <p className="text-[11px] font-semibold uppercase flex items-center gap-1.5" style={{ letterSpacing: '0.08em', color: T.label }}>
                <Table2 size={11} /> Column-Level Lineage
              </p>
              <span className="text-[10px]" style={{ color: T.label }}>{columnRows.length} mappings</span>
            </div>
            {columnRows.length === 0 ? (
              <p className="text-xs text-center py-8" style={{ color: T.muted }}>No column mappings available in the current graph.</p>
            ) : (
              <table className="w-full">
                <thead>
                  <tr style={{ background: '#132C4D' }}>
                    {['Source Table.Column', 'Transform', 'Destination Table.Column'].map(h => (
                      <th key={h} className="text-left px-4 py-2.5 text-[11px] font-semibold uppercase" style={{ letterSpacing: '0.08em', color: T.label }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {columnRows.map((row, i) => (
                    <tr key={i} className="hover:bg-sky-500/[0.05] transition-colors"
                      style={{ borderTop: `1px solid ${T.border}`, background: i % 2 === 1 ? 'rgba(255,255,255,0.02)' : 'transparent' }}>
                      <td className="px-4 py-2.5 text-xs font-mono" style={{ color: T.text }}>{row.source}</td>
                      <td className="px-4 py-2.5">
                        <span className="text-[10px] px-2 py-0.5 rounded-full font-semibold"
                          style={{
                            background: row.transform === 'passthrough' ? 'rgba(16,185,129,0.15)' : row.transform === 'alias' ? 'rgba(245,158,11,0.15)' : 'rgba(124,58,237,0.15)',
                            color: row.transform === 'passthrough' ? T.emerald : row.transform === 'alias' ? T.amber : '#A78BFA',
                          }}>
                          {row.transform}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-xs font-mono" style={{ color: '#38BDF8' }}>{row.dest}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </motion.div>
        )}
      </div>

      {/* ── Side panel (node details) ───────────────────────────────────────── */}
      {selected && (
        <motion.div
          initial={{ x: 24, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          transition={{ duration: 0.25 }}
          className="w-80 flex-shrink-0 flex flex-col overflow-hidden"
          style={{ borderLeft: `1px solid ${T.panelBorder}`, background: T.panelBg }}>
          {/* Header */}
          <div className="p-4" style={{ borderBottom: `1px solid ${T.panelBorder}` }}>
            <div className="flex items-start justify-between">
              <div>
                <span className="text-xs px-2 py-0.5 rounded-full font-medium"
                  style={{ color: LAYER_STYLE[selected.layer]?.pillColor, background: LAYER_STYLE[selected.layer]?.pillBg }}>
                  {LAYER_STYLE[selected.layer]?.label || selected.layer}
                </span>
                <h3 className="font-semibold mt-2 font-mono text-sm break-all" style={{ color: T.text }}>{selected.name}</h3>
                {selected.schema && (
                  <p className="text-xs mt-0.5" style={{ color: T.muted }}>schema: {selected.schema}</p>
                )}
              </div>
              <button onClick={() => setSelected(null)} className="p-1 rounded hover:bg-white/5 flex-shrink-0">
                <X size={14} style={{ color: T.muted }} />
              </button>
            </div>

            {/* Sub-tabs */}
            <div className="flex gap-1 mt-3">
              {([
                { id: 'info' as SidePanelTab, label: 'Info' },
                { id: 'columns' as SidePanelTab, label: `Columns${selected.columns?.length ? ` (${selected.columns.length})` : ''}` },
                ...(selected.raw_code ? [{ id: 'sql' as SidePanelTab, label: 'SQL' }] : []),
              ]).map(t => (
                <button key={t.id} onClick={() => setSideTab(t.id)}
                  className="px-3 py-1 rounded-lg text-xs font-medium transition-all"
                  style={{
                    background: sideTab === t.id ? 'rgba(14,165,233,0.15)' : 'transparent',
                    color: sideTab === t.id ? '#38BDF8' : T.muted,
                    border: `1px solid ${sideTab === t.id ? 'rgba(14,165,233,0.3)' : 'transparent'}`,
                  }}>
                  {t.label}
                </button>
              ))}
            </div>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {/* Info tab */}
            {sideTab === 'info' && (
              <>
                {selected.description && (
                  <p className="text-xs leading-relaxed" style={{ color: T.muted }}>{selected.description}</p>
                )}

                {/* Upstream */}
                <div>
                  <p className="text-xs font-semibold mb-2" style={{ color: T.text }}>Upstream ({upstreamEdges.length})</p>
                  <div className="space-y-1">
                    {upstreamEdges.length === 0
                      ? <p className="text-xs" style={{ color: T.muted }}>None (source node)</p>
                      : upstreamEdges.map(e => {
                          const n = nodeMap[e.from]
                          return n ? (
                            <button key={e.from}
                              onClick={() => setSelected(n)}
                              onMouseEnter={() => setHighlightEdge(e)}
                              onMouseLeave={() => setHighlightEdge(null)}
                              className="w-full text-left px-2 py-1.5 rounded-lg text-xs hover:bg-white/5 transition-colors font-mono"
                              style={{ background: T.cardBg, border: `1px solid ${T.border}`, color: T.text }}>
                              ↑ {n.name}
                              {e.column_mappings && e.column_mappings.length > 0 && (
                                <span className="ml-2 text-[9px] px-1 py-0.5 rounded" style={{ background: 'rgba(124,58,237,0.2)', color: '#A78BFA' }}>
                                  {e.column_mappings.length} col maps
                                </span>
                              )}
                            </button>
                          ) : null
                        })}
                  </div>
                </div>

                {/* Downstream */}
                <div>
                  <p className="text-xs font-semibold mb-2" style={{ color: T.text }}>Downstream ({downstreamEdges.length})</p>
                  <div className="space-y-1">
                    {downstreamEdges.length === 0
                      ? <p className="text-xs" style={{ color: T.muted }}>None (terminal node)</p>
                      : downstreamEdges.map(e => {
                          const n = nodeMap[e.to]
                          return n ? (
                            <button key={e.to}
                              onClick={() => setSelected(n)}
                              onMouseEnter={() => setHighlightEdge(e)}
                              onMouseLeave={() => setHighlightEdge(null)}
                              className="w-full text-left px-2 py-1.5 rounded-lg text-xs hover:bg-white/5 transition-colors font-mono"
                              style={{ background: T.cardBg, border: `1px solid ${T.border}`, color: T.text }}>
                              ↓ {n.name}
                            </button>
                          ) : null
                        })}
                  </div>
                </div>

                {/* Column lineage section */}
                {showColumnLineage && (upstreamEdges.length > 0 || downstreamEdges.length > 0) && (
                  <div>
                    <p className="text-xs font-semibold mb-2 flex items-center gap-1.5" style={{ color: T.text }}>
                      <span className="w-1.5 h-1.5 rounded-full" style={{ background: '#A78BFA' }} />
                      Column Lineage
                    </p>
                    <ColumnLineageView nodeName={selected.name} edges={edges} nodes={nodes} />
                  </div>
                )}
              </>
            )}

            {/* Columns tab */}
            {sideTab === 'columns' && (
              <div className="space-y-1">
                {(selected.column_details || []).length === 0 && (selected.columns || []).length === 0 ? (
                  <p className="text-xs" style={{ color: T.muted }}>No column metadata in manifest</p>
                ) : (selected.column_details || []).length > 0 ? (
                  (selected.column_details || []).map((col, i) => (
                    <div key={i} className="p-2 rounded-lg" style={{ background: T.cardBg, border: `1px solid ${T.border}` }}>
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-mono font-semibold" style={{ color: T.text }}>{col.name}</span>
                        {col.data_type && (
                          <span className="text-[9px] px-1.5 py-0.5 rounded font-mono" style={{ background: 'rgba(14,165,233,0.15)', color: '#38BDF8' }}>
                            {col.data_type}
                          </span>
                        )}
                      </div>
                      {col.description && (
                        <p className="text-[10px] mt-0.5" style={{ color: T.muted }}>{col.description}</p>
                      )}
                    </div>
                  ))
                ) : (
                  (selected.columns || []).map((col, i) => (
                    <div key={i} className="p-2 rounded-lg" style={{ background: T.cardBg, border: `1px solid ${T.border}` }}>
                      <span className="text-xs font-mono font-semibold" style={{ color: T.text }}>{col}</span>
                    </div>
                  ))
                )}
              </div>
            )}

            {/* SQL tab */}
            {sideTab === 'sql' && selected.raw_code && (
              <div>
                <div className="flex items-center justify-between mb-2">
                  <p className="text-xs font-semibold flex items-center gap-1.5" style={{ color: T.text }}>
                    <Code size={12} style={{ color: '#A78BFA' }} /> Raw SQL
                  </p>
                  <button
                    onClick={() => navigator.clipboard.writeText(selected.raw_code || '')}
                    className="text-[10px] px-2 py-1 rounded hover:bg-white/10 transition-colors"
                    style={{ color: T.muted, border: `1px solid ${T.border}` }}>
                    Copy
                  </button>
                </div>
                <pre className="text-[10px] font-mono leading-relaxed overflow-x-auto p-3 rounded-lg whitespace-pre-wrap break-all"
                  style={{ background: '#0B1E35', color: '#E2E8F0', border: `1px solid ${T.border}` }}>
                  {selected.raw_code}
                </pre>
                {selected.path && (
                  <p className="text-[10px] mt-2 font-mono" style={{ color: T.muted }}>📁 {selected.path}</p>
                )}
              </div>
            )}
          </div>
        </motion.div>
      )}
    </div>
  )
}
