'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import type { LucideIcon } from 'lucide-react'
import {
  Search, X, GitBranch, ShieldCheck, Database, MessageSquare,
  Activity, Share2, Zap, LayoutDashboard, Settings, CornerDownLeft,
} from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'

import api from '@/lib/api'

interface SearchResult {
  id: string
  title: string
  subtitle: string
  href: string
  icon: LucideIcon
  category: string
  color: string
}

/* Raw API response shapes */
interface RawIncident {
  id: string | number
  anomaly_type?: string
  pipeline_name?: string
  root_cause?: string | null
  approval_status?: string
}
interface RawPipeline {
  dag_id: string
  name: string
  source_type?: string
  last_run?: { status?: string } | null
}
interface RawModel {
  name: string
  schema_layer?: string
  status?: string
}

const STATIC_PAGES: SearchResult[] = [
  { id: 'p-overview',      title: 'Overview',        subtitle: 'KPIs, pipeline health, recent incidents',    href: '/',              icon: LayoutDashboard, category: 'Pages', color: '#38BDF8' },
  { id: 'p-pipelines',     title: 'Pipelines',       subtitle: 'Monitor and trigger ETL pipelines',          href: '/pipelines',     icon: GitBranch,       category: 'Pages', color: '#38BDF8' },
  { id: 'p-approvals',     title: 'Approval Panel',  subtitle: 'Review and approve AI healing fixes',        href: '/approvals',     icon: ShieldCheck,     category: 'Pages', color: '#38BDF8' },
  { id: 'p-optimizer',     title: 'Cost Optimizer',  subtitle: 'Rewrite SQL queries, track savings',         href: '/optimizer',     icon: Zap,             category: 'Pages', color: '#38BDF8' },
  { id: 'p-dbt',           title: 'dbt Assistant',   subtitle: 'Generate and run dbt staging & mart models', href: '/dbt',           icon: Database,        category: 'Pages', color: '#38BDF8' },
  { id: 'p-analyst',       title: 'AI Analyst',      subtitle: 'Ask natural language questions about data',  href: '/analyst',       icon: MessageSquare,   category: 'Pages', color: '#38BDF8' },
  { id: 'p-lineage',       title: 'Data Lineage',    subtitle: 'Visual DAG: source → raw → staging → mart',  href: '/lineage',       icon: Share2,          category: 'Pages', color: '#38BDF8' },
  { id: 'p-observability', title: 'Observability',   subtitle: 'AI insights, metrics charts, incidents',     href: '/observability', icon: Activity,        category: 'Pages', color: '#38BDF8' },
  { id: 'p-settings',      title: 'Settings',        subtitle: 'Team, API keys, connections, audit log',     href: '/settings',      icon: Settings,        category: 'Pages', color: '#38BDF8' },
]

function scoreMatch(text: string, query: string): number {
  const t = text.toLowerCase()
  const q = query.toLowerCase()
  if (t === q) return 3
  if (t.startsWith(q)) return 2
  if (t.includes(q)) return 1
  return 0
}

function filterResults(query: string, all: SearchResult[]): SearchResult[] {
  if (!query.trim()) return all.slice(0, 8)
  const scored = all
    .map(r => ({
      r,
      score: Math.max(
        scoreMatch(r.title, query),
        scoreMatch(r.subtitle, query),
        scoreMatch(r.category, query),
      ),
    }))
    .filter(x => x.score > 0)
    .sort((a, b) => b.score - a.score)
  return scored.map(x => x.r).slice(0, 10)
}

export function GlobalSearch() {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [selectedIdx, setSelectedIdx] = useState(0)
  const router = useRouter()
  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLDivElement>(null)

  /* ── Dynamic data (existing API calls kept intact) ─────────────────── */
  const { data: incidents = [] } = useQuery<RawIncident[]>({
    queryKey: ['incidents-search'],
    queryFn: () =>
      api.get('/api/incidents?limit=50')
        .then(r => r.data as RawIncident[])
        .catch(() => []),
    staleTime: 30_000,
    enabled: open,
  })

  const { data: pipelines } = useQuery<{ pipelines?: RawPipeline[] } | null>({
    queryKey: ['pipelines-search'],
    queryFn: () =>
      api.get('/api/pipelines')
        .then(r => r.data as { pipelines?: RawPipeline[] })
        .catch(() => null),
    staleTime: 30_000,
    enabled: open,
  })

  const { data: models = [] } = useQuery<RawModel[]>({
    queryKey: ['models-search'],
    queryFn: () =>
      api.get('/api/dbt/models')
        .then(r => r.data as RawModel[])
        .catch(() => []),
    staleTime: 60_000,
    enabled: open,
  })

  const dynamicResults: SearchResult[] = [
    ...(Array.isArray(incidents) ? incidents : []).slice(0, 20).map((inc): SearchResult => ({
      id: `inc-${inc.id}`,
      title: `${(inc.anomaly_type || 'Incident').toUpperCase()} — ${inc.pipeline_name || ''}`,
      subtitle: inc.root_cause ? inc.root_cause.substring(0, 80) : `Status: ${inc.approval_status}`,
      href: '/approvals',
      icon: ShieldCheck,
      category: 'Recent Incidents',
      color: inc.approval_status === 'pending' ? '#F59E0B' : '#64748B',
    })),
    ...(pipelines?.pipelines || []).slice(0, 10).map((p): SearchResult => ({
      id: `pip-${p.dag_id}`,
      title: p.name,
      subtitle: `${p.source_type ?? 'ETL'} pipeline · ${p.last_run?.status || 'no runs'}`,
      href: '/pipelines',
      icon: GitBranch,
      category: 'Pipelines',
      color: '#0EA5E9',
    })),
    ...(Array.isArray(models) ? models : []).slice(0, 20).map((m): SearchResult => ({
      id: `mdl-${m.name}`,
      title: m.name,
      subtitle: `dbt ${m.schema_layer ?? ''} model · ${m.status ?? 'unknown'}`,
      href: '/dbt',
      icon: Database,
      category: 'dbt Models',
      color: '#7C3AED',
    })),
  ]

  const allResults = [...STATIC_PAGES, ...dynamicResults]
  const results = filterResults(query, allResults)

  const grouped = results.reduce<Record<string, SearchResult[]>>((acc, r) => {
    if (!acc[r.category]) acc[r.category] = []
    acc[r.category].push(r)
    return acc
  }, {})

  /* ── Cmd+K / Ctrl+K toggle ─────────────────────────────────────────── */
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        setOpen(v => !v)
        setQuery('')
        setSelectedIdx(0)
      }
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [])

  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 50)
  }, [open])

  // Keep the selected row visible while arrowing through results
  useEffect(() => {
    const el = listRef.current?.querySelector<HTMLElement>(`[data-idx="${selectedIdx}"]`)
    el?.scrollIntoView({ block: 'nearest' })
  }, [selectedIdx])

  const navigate = useCallback((href: string) => {
    router.push(href)
    setOpen(false)
    setQuery('')
  }, [router])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setSelectedIdx(i => Math.min(i + 1, results.length - 1)) }
    if (e.key === 'ArrowUp')   { e.preventDefault(); setSelectedIdx(i => Math.max(i - 1, 0)) }
    if (e.key === 'Enter' && results[selectedIdx]) navigate(results[selectedIdx].href)
  }

  if (!open) return null

  let globalIdx = 0

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.12 }}
        className="fixed inset-0 z-[100] flex items-start justify-center pt-[14vh] px-4"
        style={{ background: 'rgba(4,8,16,0.72)', backdropFilter: 'blur(6px)', WebkitBackdropFilter: 'blur(6px)' }}
        onClick={() => setOpen(false)}>
        <motion.div
          initial={{ opacity: 0, scale: 0.97, y: -8 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          transition={{ duration: 0.16, ease: 'easeOut' }}
          className="w-full overflow-hidden"
          style={{
            maxWidth: 560,
            background: '#0F2540',
            border: '1px solid #1A3A5C',
            borderRadius: 16,
            boxShadow: '0 24px 80px rgba(0,0,0,0.55), 0 0 0 1px rgba(14,165,233,0.06)',
          }}
          onClick={e => e.stopPropagation()}>

          {/* ── Input ─────────────────────────────────────────────────── */}
          <div className="flex items-center gap-3 px-5" style={{ height: 60, borderBottom: '1px solid #1A3A5C' }}>
            <Search size={18} style={{ color: '#4B6B8E', flexShrink: 0 }} />
            <input
              ref={inputRef}
              value={query}
              onChange={e => { setQuery(e.target.value); setSelectedIdx(0) }}
              onKeyDown={handleKeyDown}
              placeholder="Search pipelines, connectors, incidents..."
              className="flex-1 bg-transparent focus:outline-none"
              style={{ fontSize: 18, fontWeight: 400, color: '#F1F5F9', caretColor: '#0EA5E9' }}
            />
            {query && (
              <button onClick={() => setQuery('')} className="p-1 rounded-md hover:bg-white/10 transition-colors">
                <X size={14} style={{ color: '#64748B' }} />
              </button>
            )}
            <kbd
              className="text-[10px] px-1.5 py-0.5 rounded font-mono flex-shrink-0"
              style={{ background: 'rgba(255,255,255,0.05)', color: '#64748B', border: '1px solid #1A3A5C' }}>
              ESC
            </kbd>
          </div>

          {/* ── Results ───────────────────────────────────────────────── */}
          <div ref={listRef} className="max-h-[380px] overflow-y-auto py-1.5">
            {results.length === 0 && (
              <div className="text-center py-10">
                <p style={{ fontSize: 13.5, color: '#64748B' }}>
                  No results for &ldquo;{query}&rdquo;
                </p>
                <p className="mt-1" style={{ fontSize: 11.5, color: '#4B6B8E' }}>
                  Try searching for a pipeline, incident, or page name
                </p>
              </div>
            )}

            {Object.entries(grouped).map(([category, items]) => (
              <div key={category}>
                <p
                  className="px-5 pt-3 pb-1 uppercase"
                  style={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.1em', color: '#2D4A6A' }}>
                  {category}
                </p>
                {items.map(result => {
                  const idx = globalIdx++
                  const Icon = result.icon
                  const selected = idx === selectedIdx
                  return (
                    <button
                      key={result.id}
                      data-idx={idx}
                      onClick={() => navigate(result.href)}
                      onMouseEnter={() => setSelectedIdx(idx)}
                      className="w-full flex items-center gap-3 px-5 text-left transition-colors duration-75"
                      style={{
                        height: 40,
                        background: selected ? 'rgba(14,165,233,0.08)' : 'transparent',
                        boxShadow: selected ? 'inset 2px 0 0 #0EA5E9' : 'none',
                      }}>
                      <div
                        className="flex items-center justify-center flex-shrink-0"
                        style={{ width: 24, height: 24, borderRadius: 7, background: `${result.color}1f` }}>
                        <Icon size={13} style={{ color: result.color }} />
                      </div>
                      <span className="truncate flex-shrink-0" style={{ fontSize: 13.5, fontWeight: 500, color: '#F1F5F9', maxWidth: '55%' }}>
                        {result.title}
                      </span>
                      <span className="truncate flex-1" style={{ fontSize: 12, color: '#4B6B8E' }}>
                        {result.subtitle}
                      </span>
                      {selected && (
                        <CornerDownLeft size={12} className="flex-shrink-0" style={{ color: '#4B6B8E' }} />
                      )}
                    </button>
                  )
                })}
              </div>
            ))}
          </div>

          {/* ── Footer ────────────────────────────────────────────────── */}
          <div
            className="px-5 py-2.5 flex items-center gap-4"
            style={{ borderTop: '1px solid #1A3A5C', background: 'rgba(8,15,28,0.4)' }}>
            {[['↑↓', 'navigate'], ['↵', 'open'], ['esc', 'close']].map(([key, label]) => (
              <span key={key} className="flex items-center gap-1.5">
                <kbd
                  className="text-[10px] px-1.5 py-0.5 rounded font-mono"
                  style={{ background: 'rgba(255,255,255,0.05)', color: '#64748B', border: '1px solid #1A3A5C' }}>
                  {key}
                </kbd>
                <span style={{ fontSize: 10.5, color: '#4B6B8E' }}>{label}</span>
              </span>
            ))}
            <span className="ml-auto" style={{ fontSize: 10.5, color: '#4B6B8E' }}>
              {results.length} result{results.length === 1 ? '' : 's'}
            </span>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  )
}
