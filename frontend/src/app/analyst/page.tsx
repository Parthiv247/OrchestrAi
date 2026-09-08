'use client'
import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Send, ThumbsUp, ThumbsDown, BarChart2, Table, Code, Download,
  Database, ChevronRight, ChevronDown, Search, X, History, Copy,
  Check, Camera, Sparkles, Clock, Columns, MessageSquare,
} from 'lucide-react'
import { EmptyState } from '@/components/ui/EmptyState'
import { DEMO_QUERY_HISTORY } from '@/lib/demo'
import { Skeleton } from '@/components/ui/Skeleton'
import { useMutation } from '@tanstack/react-query'
import { formatDistanceToNow } from 'date-fns'
import { useTables } from '@/lib/queries'
import api, { analystApi } from '@/lib/api'
import { CodeBlock } from '@/components/ui/CodeBlock'
import type { TableInfo } from '@/lib/types'
import {
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend,
} from 'recharts'

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

const COLORS = ['#0EA5E9', '#7C3AED', '#10B981', '#F59E0B', '#EF4444', '#06B6D4', '#F97316']

const SUGGESTIONS = [
  'Show total records per pipeline',
  'Top 5 anomalies this week',
  'Average load time by source',
]

interface QueryResultData {
  columns?: string[]
  rows?: (string | number | null)[][]
  row_count?: number
  sql?: string
  optimized_sql?: string
  explanation?: string
  chart_config?: { type?: string; x_column?: string; y_column?: string }
  execution_time_ms?: number
  optimization_id?: string
  anti_patterns?: { pattern?: string; description?: string }[]
}

interface Message {
  role: 'user' | 'assistant'
  content: string
  result?: QueryResultData
  id?: string
}

const isNumeric = (v: unknown) => v !== null && v !== '' && !isNaN(parseFloat(String(v))) && isFinite(Number(v))

// ── Chart renderer (preserved logic) ────────────────────────────────────────────
function ChartRenderer({ chartConfig, rows, columns }: { chartConfig: QueryResultData['chart_config']; rows: (string | number | null)[][]; columns: string[] }) {
  if (!rows?.length || !columns?.length)
    return <p className="text-center py-8 text-sm" style={{ color: T.muted }}>No data to chart</p>

  // Coerce numeric-looking strings to numbers so recharts can plot them
  const data = rows.map(row => {
    const obj: Record<string, string | number | null> = {}
    columns.forEach((col, i) => { obj[col] = isNumeric(row[i]) ? parseFloat(String(row[i])) : row[i] })
    return obj
  })

  // Identify a numeric column (for y) and a label column (for x)
  const numericIdx = columns.findIndex((_, i) => rows.some(r => isNumeric(r[i])) && rows.every(r => r[i] === null || isNumeric(r[i])))
  const labelIdx = columns.findIndex((_, i) => i !== numericIdx)

  let { type, x_column, y_column } = chartConfig || {}
  // Auto-pick a chart when the LLM said "table"/unknown but the data is chartable
  if (!['bar', 'line', 'pie', 'scatter'].includes(type ?? '')) {
    if (rows.length < 2 || numericIdx < 0) {
      return <p className="text-center py-6 text-sm" style={{ color: T.muted }}>Single value — see the result table</p>
    }
    type = 'bar'
    y_column = columns[numericIdx]
    x_column = columns[labelIdx >= 0 ? labelIdx : 0]
  }

  const has = (c: unknown) => typeof c === 'string' && columns.includes(c)
  const xKey = has(x_column) ? x_column : columns[labelIdx >= 0 ? labelIdx : 0]
  const yKey = has(y_column) ? y_column : columns[numericIdx >= 0 ? numericIdx : (columns[1] ? 1 : 0)]

  const commonProps = { data, margin: { top: 8, right: 24, left: 0, bottom: 8 } }
  const tooltipStyle = { background: '#112B47', border: `1px solid ${T.border}`, borderRadius: 8, color: '#E2E8F0', fontSize: 12 }
  const axisTick = { fontSize: 11, fill: T.muted }

  if (type === 'bar') return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart {...commonProps}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
        <XAxis dataKey={xKey} tick={axisTick} axisLine={{ stroke: T.border }} tickLine={false} label={{ value: xKey, position: 'insideBottom', offset: -4, fontSize: 10, fill: T.label }} />
        <YAxis tick={axisTick} axisLine={false} tickLine={false} />
        <Tooltip contentStyle={tooltipStyle} cursor={{ fill: 'rgba(14,165,233,0.06)' }} />
        <Bar dataKey={yKey} fill={T.accent} radius={[4, 4, 0, 0]} maxBarSize={48} />
      </BarChart>
    </ResponsiveContainer>
  )

  if (type === 'line') return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart {...commonProps}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
        <XAxis dataKey={xKey} tick={axisTick} axisLine={{ stroke: T.border }} tickLine={false} />
        <YAxis tick={axisTick} axisLine={false} tickLine={false} />
        <Tooltip contentStyle={tooltipStyle} />
        <Line type="monotone" dataKey={yKey} stroke={T.accent} strokeWidth={2} dot={false} activeDot={{ r: 4, fill: T.accent }} />
      </LineChart>
    </ResponsiveContainer>
  )

  if (type === 'pie') return (
    <ResponsiveContainer width="100%" height={300}>
      <PieChart>
        <Pie data={data} dataKey={yKey} nameKey={xKey} cx="50%" cy="50%" innerRadius={55} outerRadius={95} paddingAngle={2} isAnimationActive={false} label={{ fontSize: 10, fill: '#94A3B8' }}>
          {data.map((_: Record<string, string | number | null>, i: number) => <Cell key={i} fill={COLORS[i % COLORS.length]} stroke={T.cardBg} />)}
        </Pie>
        <Tooltip contentStyle={tooltipStyle} />
        <Legend wrapperStyle={{ fontSize: 11 }} />
      </PieChart>
    </ResponsiveContainer>
  )

  if (type === 'scatter') return (
    <ResponsiveContainer width="100%" height={300}>
      <ScatterChart {...commonProps}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
        <XAxis dataKey={xKey} name={xKey} tick={axisTick} axisLine={{ stroke: T.border }} tickLine={false} />
        <YAxis dataKey={yKey} name={yKey} tick={axisTick} axisLine={false} tickLine={false} />
        <Tooltip contentStyle={tooltipStyle} />
        <Scatter fill={T.violet} />
      </ScatterChart>
    </ResponsiveContainer>
  )

  return <p className="text-center py-4 text-sm" style={{ color: T.muted }}>Chart type: {type}</p>
}

// ── Export helpers (preserved logic) ───────────────────────────────────────────
function downloadCSV(rows: (string | number | null)[][], columns: string[]) {
  const lines = [columns.join(','), ...rows.map(r => r.map(v => JSON.stringify(v ?? '')).join(','))]
  const blob = new Blob([lines.join('\n')], { type: 'text/csv' })
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'query_results.csv'; a.click()
}

function downloadPNG(chartId = 'analyst-chart') {
  const el = document.getElementById(chartId)
  if (!el) return
  import('html2canvas').then(mod => {
    mod.default(el, { background: T.cardBg }).then((canvas: HTMLCanvasElement) => {
      const a = document.createElement('a'); a.href = canvas.toDataURL('image/png'); a.download = 'chart.png'; a.click()
    })
  }).catch(() => {
    // fallback: just copy SVG
    const svg = el.querySelector('svg')
    if (!svg) return
    const blob = new Blob([svg.outerHTML], { type: 'image/svg+xml' })
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'chart.svg'; a.click()
  })
}

// ── Table browser with columns preview ──────────────────────────────────────────
function TableBrowser({ tables, onInsert }: { tables: TableInfo[]; onInsert: (name: string) => void }) {
  const [search, setSearch] = useState('')
  const [expanded, setExpanded] = useState<Record<string, boolean>>({})
  const [previewTable, setPreviewTable] = useState<string | null>(null)
  const [previewCols, setPreviewCols] = useState<Record<string, { column_name?: string; name?: string; data_type?: string; type?: string }[]>>({})
  const [previewLoading, setPreviewLoading] = useState<string | null>(null)

  const schemaGroups = tables.reduce((acc: Record<string, TableInfo[]>, t: TableInfo) => {
    const s = (t as TableInfo & { schema_name?: string }).schema_name || 'public'
    if (!acc[s]) acc[s] = []
    acc[s].push(t)
    return acc
  }, {})

  const filtered = Object.entries(schemaGroups).reduce((acc: Record<string, TableInfo[]>, [schema, tbls]) => {
    const f = tbls.filter((t: TableInfo) =>
      !search || t.table_name.toLowerCase().includes(search.toLowerCase())
    )
    if (f.length) acc[schema] = f
    return acc
  }, {} as Record<string, TableInfo[]>)

  const schemaColor: Record<string, string> = {
    raw: T.amber,
    staging: T.violet,
    marts: T.emerald,
    public: T.accent,
  }

  const togglePreview = (t: TableInfo & { schema_name?: string; full_name?: string }) => {
    const key = t.full_name || t.table_name
    if (previewTable === key) { setPreviewTable(null); return }
    setPreviewTable(key)
    if (!previewCols[key]) {
      setPreviewLoading(key)
      analystApi.getSchema(t.table_name, t.schema_name || 'marts')
        .then(r => {
          const cols = r.data?.columns || r.data?.schema || []
          setPreviewCols(prev => ({ ...prev, [key]: Array.isArray(cols) ? cols : [] }))
        })
        .catch(() => setPreviewCols(prev => ({ ...prev, [key]: [] })))
        .finally(() => setPreviewLoading(null))
    }
  }

  return (
    <div className="flex flex-col min-h-0 flex-1">
      <div className="px-3 pb-2">
        <div className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg" style={{ background: T.cardBg, border: `1px solid ${T.border}` }}>
          <Search size={12} style={{ color: T.muted }} />
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search tables..."
            className="flex-1 bg-transparent text-xs focus:outline-none min-w-0"
            style={{ color: T.text }}
          />
          {search && <button onClick={() => setSearch('')}><X size={10} style={{ color: T.muted }} /></button>}
        </div>
      </div>
      <div className="flex-1 overflow-y-auto px-2 pb-3 space-y-1">
        {Object.entries(filtered).map(([schema, tbls]) => (
          <div key={schema}>
            <button
              onClick={() => setExpanded(e => ({ ...e, [schema]: !e[schema] }))}
              className="w-full flex items-center gap-1.5 px-2 py-1.5 rounded-lg hover:bg-white/5 transition-colors">
              {expanded[schema] !== false
                ? <ChevronDown size={12} style={{ color: T.muted }} />
                : <ChevronRight size={12} style={{ color: T.muted }} />}
              <Database size={11} style={{ color: schemaColor[schema] || T.muted }} />
              <span className="text-[11px] font-semibold uppercase" style={{ letterSpacing: '0.08em', color: schemaColor[schema] || T.muted }}>{schema}</span>
              <span className="ml-auto text-[10px]" style={{ color: T.label }}>{tbls.length}</span>
            </button>
            {expanded[schema] !== false && (
              <div className="ml-3 space-y-0.5" style={{ borderLeft: `1px solid ${T.panelBorder}` }}>
                {tbls.map((t: TableInfo & { schema_name?: string; full_name?: string }) => {
                  const key = t.full_name || t.table_name
                  const isOpen = previewTable === key
                  return (
                    <div key={key}>
                      <div className="flex items-center group">
                        <button
                          onClick={() => togglePreview(t)}
                          className="p-1 rounded hover:bg-white/5 flex-shrink-0"
                          title="Preview columns">
                          {isOpen
                            ? <ChevronDown size={10} style={{ color: T.muted }} />
                            : <ChevronRight size={10} style={{ color: T.label }} />}
                        </button>
                        <button
                          onClick={() => onInsert(t.full_name || t.table_name)}
                          className="flex-1 min-w-0 text-left px-1.5 py-1.5 rounded-lg text-xs transition-colors hover:bg-sky-500/10"
                          title={`Click to insert ${t.full_name || t.table_name}`}>
                          <span className="font-mono truncate block group-hover:text-sky-400" style={{ color: T.text }}>{t.table_name}</span>
                        </button>
                        {t.row_count != null && (
                          <span className="text-[10px] pr-2 flex-shrink-0" style={{ color: T.label }}>{t.row_count.toLocaleString()}</span>
                        )}
                      </div>
                      <AnimatePresence>
                        {isOpen && (
                          <motion.div
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: 'auto', opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            transition={{ duration: 0.18 }}
                            className="overflow-hidden">
                            <div className="ml-5 mr-2 mb-1.5 rounded-lg px-2.5 py-2" style={{ background: T.cardBg, border: `1px solid ${T.border}` }}>
                              <p className="text-[10px] font-semibold uppercase mb-1.5 flex items-center gap-1" style={{ letterSpacing: '0.08em', color: T.label }}>
                                <Columns size={9} /> Columns
                              </p>
                              {previewLoading === key ? (
                                <div className="space-y-1">
                                  {[1, 2, 3].map(i => <Skeleton key={i} height={13} style={{ width: i % 2 === 0 ? '65%' : '80%' }} />)}
                                </div>
                              ) : (previewCols[key] || []).length === 0 ? (
                                <p className="text-[10px]" style={{ color: T.muted }}>No column metadata</p>
                              ) : (
                                <div className="space-y-0.5 max-h-36 overflow-y-auto">
                                  {(previewCols[key] || []).slice(0, 20).map((c, i: number) => (
                                    <div key={i} className="flex items-center justify-between gap-2">
                                      <span className="text-[10px] font-mono truncate" style={{ color: T.text }}>{c.column_name || c.name || String(c)}</span>
                                      {(c.data_type || c.type) && (
                                        <span className="text-[9px] font-mono flex-shrink-0" style={{ color: T.accent }}>{c.data_type || c.type}</span>
                                      )}
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        ))}
        {tables.length === 0 && (
          <p className="text-xs text-center py-6" style={{ color: T.muted }}>No tables found</p>
        )}
      </div>
    </div>
  )
}

// ── Page ────────────────────────────────────────────────────────────────────────
export default function AnalystPage() {
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<Message[]>([])
  const [sessionId, setSessionId] = useState('')
  const [showTableBrowser, setShowTableBrowser] = useState(true)
  const [savedQueries, setSavedQueries] = useState<{ q: string; ts: number }[]>([])
  const [copiedId, setCopiedId] = useState<number | null>(null)
  const [collapsed, setCollapsed] = useState<Record<number, boolean>>({})
  const [viewMode, setViewMode] = useState<Record<number, 'chart' | 'table'>>({})
  const bottomRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const { data: tables } = useTables()
  const tableList = Array.isArray(tables) ? tables : []
  const tableCount = tableList.length

  const query = useMutation({
    mutationFn: (q: string) => analystApi.query(q, sessionId).then(r => r.data),
    onSuccess: (data) => {
      const msg: Message = { role: 'assistant', content: data.explanation || data.sql, result: data, id: data.optimization_id }
      setMessages(prev => [...prev, msg])
    },
    onError: () => {
      setMessages(prev => [...prev, { role: 'assistant', content: 'Sorry, I had trouble with that query. Please try rephrasing.' }])
    },
  })

  const send = (q: string = input) => {
    if (!q.trim() || query.isPending) return
    setMessages(prev => [...prev, { role: 'user', content: q }])
    setInput('')
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
    query.mutate(q)
    // Save to history
    setSavedQueries(prev => {
      const entry = { q: q.trim(), ts: Date.now() }
      const next = [entry, ...prev.filter(x => x.q !== entry.q)].slice(0, 50)
      localStorage.setItem('analyst_history', JSON.stringify(next))
      return next
    })
  }

  // Load browser-only state after mount to prevent hydration mismatch
  useEffect(() => {
    setSessionId(crypto.randomUUID())
    try {
      const stored = localStorage.getItem('analyst_history')
      if (stored) {
        setSavedQueries(JSON.parse(stored))
      } else {
        // Seed demo query history so the page doesn't look empty
        setSavedQueries(DEMO_QUERY_HISTORY as any[])
      }
    } catch { /* ignore */ }
  }, [])

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  // Pair messages into notebook cells (question + its answer), oldest→newest
  const allCells: { key: number; question: string; answer: Message | null }[] = []
  for (let i = 0; i < messages.length; i++) {
    if (messages[i].role === 'user') {
      const next = messages[i + 1]
      allCells.push({ key: i, question: messages[i].content, answer: next && next.role === 'assistant' ? next : null })
    }
  }
  // Keep only the 5 most recent queries — older ones drop off the top.
  const MAX_CELLS = 5
  const cells = allCells.slice(-MAX_CELLS)

  const insertTable = (fullName: string) => {
    setInput(prev => (prev.trim() ? `${prev.trimEnd()} ${fullName}` : fullName))
  }

  const autoGrow = (el: HTMLTextAreaElement) => {
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 160) + 'px'
  }

  return (
    <div className="flex h-[calc(100vh-56px)]" style={{ background: T.bodyBg }}>

      {/* ══ LEFT PANEL — 320px: Query History + Table Browser ══════════════════ */}
      <motion.aside
        initial={{ x: -16, opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        transition={{ duration: 0.3, ease: 'easeOut' }}
        className="w-80 flex-shrink-0 flex flex-col min-h-0"
        style={{ background: T.panelBg, borderRight: `1px solid ${T.panelBorder}` }}>

        {/* Query history */}
        <div className="flex flex-col min-h-0" style={{ flexBasis: '45%' }}>
          <div className="px-4 pt-4 pb-2 flex items-center justify-between flex-shrink-0">
            <p className="text-[11px] font-semibold uppercase flex items-center gap-1.5" style={{ letterSpacing: '0.08em', color: T.label }}>
              <History size={11} /> Query History
            </p>
            {savedQueries.length > 0 && (
              <button
                onClick={() => { setSavedQueries([]); localStorage.removeItem('analyst_history') }}
                className="text-[10px] transition-colors hover:opacity-70"
                style={{ color: T.label }}>
                Clear
              </button>
            )}
          </div>
          <div className="flex-1 overflow-y-auto px-2 pb-2">
            {savedQueries.length === 0 ? (
              <div className="px-3 py-6 text-center">
                <Clock size={18} className="mx-auto mb-2" style={{ color: T.label }} />
                <p className="text-[11px]" style={{ color: T.muted }}>Your past questions appear here</p>
              </div>
            ) : savedQueries.map((h, i) => (
              <button
                key={`${h.ts}-${i}`}
                onClick={() => send(h.q)}
                title="Click to re-run"
                className="w-full flex items-center gap-2 h-9 px-2.5 rounded-lg text-left transition-colors hover:bg-white/5 group">
                <span className="flex-1 min-w-0 text-xs truncate transition-colors" style={{ color: T.text }}>{h.q}</span>
                <span className="text-[9px] flex-shrink-0" style={{ color: T.label }}>
                  {formatDistanceToNow(h.ts, { addSuffix: false })}
                </span>
              </button>
            ))}
          </div>
        </div>

        <div style={{ borderTop: `1px solid ${T.panelBorder}` }} />

        {/* Table browser (collapsible) */}
        <div className="flex flex-col min-h-0 flex-1">
          <button
            onClick={() => setShowTableBrowser(v => !v)}
            className="px-4 pt-3 pb-2 flex items-center justify-between flex-shrink-0 hover:bg-white/[0.02] transition-colors">
            <p className="text-[11px] font-semibold uppercase flex items-center gap-1.5" style={{ letterSpacing: '0.08em', color: T.label }}>
              <Database size={11} /> Table Browser
              <span className="normal-case font-normal" style={{ letterSpacing: 0 }}>({tableCount})</span>
            </p>
            {showTableBrowser
              ? <ChevronDown size={13} style={{ color: T.muted }} />
              : <ChevronRight size={13} style={{ color: T.muted }} />}
          </button>
          {showTableBrowser && <TableBrowser tables={tableList} onInsert={insertTable} />}
        </div>
      </motion.aside>

      {/* ══ RIGHT PANEL — chat-style query + results ═══════════════════════════ */}
      <div className="flex-1 flex flex-col min-w-0">

        {/* Header */}
        <motion.div
          initial={{ y: -8, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ duration: 0.3 }}
          className="px-6 py-3.5 flex items-center justify-between flex-shrink-0"
          style={{ borderBottom: `1px solid ${T.panelBorder}` }}>
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: 'rgba(14,165,233,0.12)', border: '1px solid rgba(14,165,233,0.25)' }}>
              <Sparkles size={15} style={{ color: T.accent }} />
            </div>
            <div>
              <h1 className="text-sm font-semibold" style={{ color: T.text }}>AI Analyst</h1>
              <p className="text-[11px]" style={{ color: T.muted }}>{tableCount} tables connected · ask in plain English</p>
            </div>
          </div>
          <span className="text-[10px] px-2 py-1 rounded-md font-medium flex items-center gap-1.5" style={{ background: 'rgba(16,185,129,0.1)', color: T.emerald, border: '1px solid rgba(16,185,129,0.2)' }}>
            <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ background: T.emerald }} />
            Groq LLM ready
          </span>
        </motion.div>

        {/* Results area */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {cells.length === 0 && !query.isPending && (
            <div className="flex items-center justify-center h-full">
              <EmptyState
                icon={MessageSquare}
                title="Ask your data anything"
                description="Type a question in plain English and OrchestrAI will convert it to SQL and run it against your warehouse."
                size="sm"
              />
            </div>
          )}

          <AnimatePresence initial={false}>
            {cells.map(cell => {
              const r = cell.answer?.result
              const isCollapsed = collapsed[cell.key]
              const sql = r?.optimized_sql || r?.sql || ''
              const chartable = r && ((r.rows?.length || 0) >= 2 || ['bar', 'line', 'pie', 'scatter'].includes(r.chart_config?.type ?? ''))
              const mode = viewMode[cell.key] || (chartable ? 'chart' : 'table')
              return (
                <motion.div
                  key={cell.key}
                  initial={{ opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.3 }}
                  className="rounded-xl overflow-hidden"
                  style={{ background: T.cardBg, border: `1px solid ${T.border}` }}>

                  {/* Cell header — the question */}
                  <button
                    onClick={() => setCollapsed(p => ({ ...p, [cell.key]: !p[cell.key] }))}
                    className="w-full flex items-center gap-2.5 px-4 py-3 text-left hover:bg-white/[0.03] transition-colors">
                    {isCollapsed
                      ? <ChevronRight size={15} style={{ color: T.accent }} className="flex-shrink-0" />
                      : <ChevronDown size={15} style={{ color: T.accent }} className="flex-shrink-0" />}
                    <span className="text-sm font-medium flex-1" style={{ color: T.text }}>{cell.question}</span>
                    {r && (
                      <span className="text-[10px] font-mono flex-shrink-0" style={{ color: T.label }}>
                        {r.row_count} rows · {r.execution_time_ms}ms
                      </span>
                    )}
                  </button>

                  {!isCollapsed && (
                    <div className="px-4 pb-4 space-y-4" style={{ borderTop: `1px solid ${T.border}` }}>
                      {!cell.answer ? (
                        <p className="text-sm pt-3" style={{ color: T.muted }}>Running…</p>
                      ) : !r ? (
                        <div className="mt-3 px-3 py-2.5 rounded-lg text-sm flex items-center gap-2" style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.25)', color: '#FCA5A5' }}>
                          <X size={14} className="flex-shrink-0" style={{ color: T.red }} />
                          {cell.answer.content}
                        </div>
                      ) : (
                        <>
                          {/* Explanation + actions */}
                          <div className="flex items-start justify-between gap-4 pt-3">
                            <p className="text-sm flex-1 leading-relaxed" style={{ color: T.muted }}>{r.explanation}</p>
                            <div className="flex items-center gap-1.5 flex-shrink-0">
                              {/* Chart / Table toggle */}
                              {chartable && (
                                <div className="flex rounded-lg overflow-hidden" style={{ border: `1px solid ${T.border}` }}>
                                  {(['chart', 'table'] as const).map(m => (
                                    <button
                                      key={m}
                                      onClick={() => setViewMode(p => ({ ...p, [cell.key]: m }))}
                                      className="flex items-center gap-1 text-[11px] px-2.5 py-1 transition-colors font-medium"
                                      style={{
                                        background: mode === m ? 'rgba(14,165,233,0.15)' : 'transparent',
                                        color: mode === m ? '#38BDF8' : T.muted,
                                      }}>
                                      {m === 'chart' ? <BarChart2 size={11} /> : <Table size={11} />}
                                      {m === 'chart' ? 'Chart' : 'Table'}
                                    </button>
                                  ))}
                                </div>
                              )}
                              <button
                                onClick={() => { navigator.clipboard.writeText(sql).then(() => { setCopiedId(cell.key); setTimeout(() => setCopiedId(null), 2000) }) }}
                                className="flex items-center gap-1 text-[11px] px-2 py-1 rounded-lg transition-colors hover:bg-white/5"
                                style={{ border: `1px solid ${T.border}`, color: copiedId === cell.key ? T.emerald : T.muted }}
                                title="Copy SQL">
                                {copiedId === cell.key ? <Check size={11} /> : <Copy size={11} />}{copiedId === cell.key ? 'Copied' : 'SQL'}
                              </button>
                              <button
                                onClick={() => downloadPNG(`analyst-chart-${cell.key}`)}
                                className="flex items-center gap-1 text-[11px] px-2 py-1 rounded-lg transition-colors hover:bg-white/5"
                                style={{ border: `1px solid ${T.border}`, color: T.muted }}
                                title="Export chart PNG">
                                <Camera size={11} /> PNG
                              </button>
                              <button
                                onClick={() => downloadCSV(r.rows || [], r.columns || [])}
                                className="flex items-center gap-1 text-[11px] px-2 py-1 rounded-lg transition-colors hover:bg-white/5"
                                style={{ border: `1px solid ${T.border}`, color: T.muted }}
                                title="Download CSV">
                                <Download size={11} /> CSV
                              </button>
                              <button onClick={() => analystApi.feedback(cell.answer?.id || '', 1)} className="p-1 rounded hover:opacity-80 transition-colors" style={{ color: T.muted }}><ThumbsUp size={12} /></button>
                              <button onClick={() => analystApi.feedback(cell.answer?.id || '', -1)} className="p-1 rounded hover:opacity-80 transition-colors" style={{ color: T.muted }}><ThumbsDown size={12} /></button>
                            </div>
                          </div>

                          {/* SQL */}
                          <div>
                            <p className="text-[11px] font-semibold uppercase mb-1.5 flex items-center gap-1" style={{ letterSpacing: '0.08em', color: T.label }}><Code size={11} /> SQL</p>
                            <CodeBlock code={sql} language="sql" />
                          </div>

                          {/* Chart view */}
                          {chartable && mode === 'chart' && (
                            <div>
                              <p className="text-[11px] font-semibold uppercase mb-1.5 flex items-center gap-1" style={{ letterSpacing: '0.08em', color: T.label }}><BarChart2 size={11} /> Visualization</p>
                              <div id={`analyst-chart-${cell.key}`} className="rounded-xl p-4" style={{ background: '#0B1E35', border: `1px solid ${T.border}` }}>
                                <ChartRenderer chartConfig={r.chart_config} rows={r.rows || []} columns={r.columns || []} />
                              </div>
                            </div>
                          )}

                          {/* Table view */}
                          {(!chartable || mode === 'table') && (
                            <div>
                              <p className="text-[11px] font-semibold uppercase mb-1.5 flex items-center gap-1" style={{ letterSpacing: '0.08em', color: T.label }}><Table size={11} /> Results ({r.row_count})</p>
                              <div className="rounded-xl overflow-hidden" style={{ border: `1px solid ${T.border}` }}>
                                <div className="overflow-auto max-h-80">
                                  <table className="w-full text-sm">
                                    <thead className="sticky top-0 z-10">
                                      <tr style={{ background: '#132C4D' }}>
                                        {(r.columns || []).map((col: string) => (
                                          <th key={col} className="text-left px-4 py-2.5 text-[11px] font-semibold uppercase whitespace-nowrap" style={{ letterSpacing: '0.08em', color: T.label }}>{col}</th>
                                        ))}
                                      </tr>
                                    </thead>
                                    <tbody>
                                      {(r.rows || []).slice(0, 100).map((row: (string | number | null)[], ri: number) => (
                                        <tr
                                          key={ri}
                                          className="hover:bg-sky-500/[0.06] transition-colors"
                                          style={{
                                            borderTop: `1px solid ${T.border}`,
                                            background: ri % 2 === 1 ? 'rgba(255,255,255,0.02)' : 'transparent',
                                          }}>
                                          {row.map((cellv, j) => (
                                            <td key={j} className="px-4 py-2 text-xs font-mono whitespace-nowrap" style={{ color: T.text }}>
                                              {cellv === null ? <span style={{ color: T.label }}>null</span> : String(cellv)}
                                            </td>
                                          ))}
                                        </tr>
                                      ))}
                                    </tbody>
                                  </table>
                                </div>
                              </div>
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  )}
                </motion.div>
              )
            })}
          </AnimatePresence>

          {/* Typing indicator */}
          {query.isPending && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className="rounded-xl px-4 py-3.5 flex items-center gap-3 text-sm"
              style={{ background: T.cardBg, border: `1px solid ${T.border}`, color: T.text }}>
              <div className="flex gap-1.5">
                {[0, 1, 2].map(i => (
                  <div key={i} className="w-1.5 h-1.5 rounded-full animate-bounce" style={{ background: T.accent, animationDelay: `${i * 0.15}s` }} />
                ))}
              </div>
              <span style={{ color: T.muted }}>Analyzing your data…</span>
            </motion.div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* ── Input area (sticky bottom) ────────────────────────────────────── */}
        <div className="px-6 py-4 flex-shrink-0" style={{ borderTop: `1px solid ${T.panelBorder}`, background: T.bodyBg }}>
          <div className="max-w-3xl mx-auto">
            {/* Example query chips */}
            {messages.length === 0 && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.2 }}
                className="flex flex-wrap gap-2 mb-3 justify-center">
                {SUGGESTIONS.map(s => (
                  <button
                    key={s}
                    onClick={() => send(s)}
                    className="text-xs px-3 py-1.5 rounded-full transition-all hover:border-sky-500/50"
                    style={{ background: T.cardBg, color: T.muted, border: `1px solid ${T.border}` }}>
                    {s}
                  </button>
                ))}
              </motion.div>
            )}
            <div className="flex items-end gap-2 rounded-xl p-2" style={{ background: T.cardBg, border: `1px solid ${T.border}` }}>
              <textarea
                ref={textareaRef}
                value={input}
                rows={1}
                onChange={e => { setInput(e.target.value); autoGrow(e.target) }}
                onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }}
                placeholder="Ask anything about your data..."
                className="flex-1 resize-none bg-transparent px-2 py-2 text-sm focus:outline-none min-w-0"
                style={{ color: T.text, maxHeight: 160 }}
              />
              <button
                onClick={() => send()}
                disabled={!input.trim() || query.isPending}
                className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold text-white transition-all hover:opacity-90 active:scale-95 disabled:opacity-40 flex-shrink-0"
                style={{ background: T.accent }}>
                <Send size={14} /> Ask AI <Sparkles size={13} />
              </button>
            </div>
            <p className="text-[10px] mt-1.5 text-center" style={{ color: T.label }}>
              Enter to send · Shift+Enter for a new line · answers include SQL, chart & table
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
