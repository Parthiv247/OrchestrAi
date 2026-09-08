'use client'
import { useState } from 'react'
import { motion } from 'framer-motion'
import { Zap, Copy, Check, DollarSign, BarChart2, TrendingDown, Code2, Database, GitBranch, Terminal, Lightbulb } from 'lucide-react'
import { useMutation } from '@tanstack/react-query'
import { useSavings } from '@/lib/queries'
import { optimizerApi } from '@/lib/api'
import { useToast } from '@/components/ui/Toaster'
import { CodeBlock } from '@/components/ui/CodeBlock'
import { CardSkeleton } from '@/components/ui/LoadingSkeleton'
import { DEMO_SAVINGS } from '@/lib/demo'
import type { LucideIcon } from '@/lib/types'
import type { OptimizerResult, SavingsHistory, AntiPattern } from '@/lib/types'

const C = {
  bg: '#080F1C', card: '#0F2540', border: '#1A3A5C',
  accent: '#0EA5E9', emerald: '#10B981', amber: '#F59E0B', red: '#EF4444', violet: '#7C3AED',
  textPrimary: '#F1F5F9', textMuted: '#64748B', textLabel: '#4B6B8E',
}

const SAMPLE_SQL = `SELECT *
FROM raw.nyc_taxi_trips
WHERE pickup_datetime > '2024-01-01'`

const TIPS = [
  { icon: Database,  title: 'Use columnar storage',  desc: 'Store wide tables in Parquet or ORC format for 10x faster scans.' },
  { icon: Code2,     title: 'Add WHERE clauses',     desc: 'Filter early to reduce data shuffled across nodes.' },
  { icon: Lightbulb, title: 'Avoid SELECT *',        desc: 'Select only the columns you need to cut I/O by up to 80%.' },
]

function StatCard({ label, value, sub, color, icon: Icon }: { label: string; value: string; sub?: string; color: string; icon: LucideIcon }) {
  return (
    <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, padding: '16px 20px', flex: 1 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <div style={{ width: 32, height: 32, borderRadius: 8, background: color + '20', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Icon size={15} style={{ color }} />
        </div>
        <p style={{ fontSize: 11, letterSpacing: '0.08em', textTransform: 'uppercase' as const, color: C.textLabel, fontWeight: 600, margin: 0 }}>{label}</p>
      </div>
      <p style={{ fontSize: 26, fontWeight: 700, color, margin: 0 }}>{value}</p>
      {sub && <p style={{ fontSize: 11, color: C.textMuted, margin: '2px 0 0' }}>{sub}</p>}
    </div>
  )
}

export default function OptimizerPage() {
  const toast = useToast()
  const [sql, setSql] = useState(SAMPLE_SQL)
  const [result, setResult] = useState<OptimizerResult | null>(null)
  const [copied, setCopied] = useState(false)
  const [history, setHistory] = useState<SavingsHistory[]>([])
  const { data: savingsRaw, isLoading: savLoading } = useSavings()
  const savings = savingsRaw || (!savLoading ? DEMO_SAVINGS : null)

  const optimize = useMutation({
    mutationFn: () => optimizerApi.optimize(sql).then(r => r.data),
    onSuccess: (data) => {
      setResult(data)
      setHistory(prev => [{ ...data, original_sql: sql, ts: new Date() }, ...prev].slice(0, 5))
      toast(`Query optimized — ${data.savings_percent?.toFixed(0) || 0}% faster, $${data.dollar_savings?.toFixed(4) || '0'} saved`, 'success')
    },
    onError: () => toast('Optimization failed — check the SQL syntax', 'error'),
  })

  const copyOptimized = () => {
    if (result?.optimized_sql) {
      navigator.clipboard.writeText(result.optimized_sql)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}
      style={{ padding: 24, background: C.bg, minHeight: '100%', display: 'flex', flexDirection: 'column', gap: 24 }}
    >
      {/* Header */}
      <div>
        <h1 style={{ fontSize: 22, fontWeight: 700, color: C.textPrimary, margin: '0 0 4px' }}>Cost Optimizer</h1>
        <p style={{ fontSize: 13, color: C.textMuted, margin: 0 }}>AI-powered SQL query optimization — reduce spend and improve execution time</p>
      </div>

      {/* Stat cards */}
      <div style={{ display: 'flex', gap: 12 }}>
        {savLoading ? (
          <><CardSkeleton /><CardSkeleton /><CardSkeleton /></>
        ) : (
          <>
            <StatCard label="Total Saved"        value={`$${(savings?.total_dollar_saved || 0).toFixed(2)}`}       color={C.emerald} icon={DollarSign} />
            <StatCard label="Avg Savings"         value={`${(savings?.avg_improvement_percent || 0).toFixed(1)}%`}  color={C.violet}  icon={TrendingDown} sub="per query" />
            <StatCard label="Queries Optimized"   value={String(savings?.total_queries_optimized || 0)}             color={C.accent}  icon={BarChart2} />
          </>
        )}
      </div>

      {/* Savings by source */}
      {savings?.breakdown && Object.keys(savings.breakdown).length > 0 && (
        <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, padding: 20 }}>
          <p style={{ fontSize: 11, letterSpacing: '0.08em', textTransform: 'uppercase' as const, color: C.textLabel, fontWeight: 600, margin: '0 0 14px' }}>Savings by Source</p>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10 }}>
            {(['analyst','dbt:staging','dbt:mart','manual'] as const).map(key => {
              const b = (savings.breakdown as Record<string, { total_saved?: number; query_count?: number; avg_pct?: number }>)[key]
              const icons: Record<string, LucideIcon> = { analyst: Code2, 'dbt:staging': Database, 'dbt:mart': GitBranch, manual: Terminal }
              const colors: Record<string, string> = { analyst: C.accent, 'dbt:staging': C.violet, 'dbt:mart': C.amber, manual: C.textMuted }
              const labels: Record<string, string> = { analyst: 'Analyst Queries', 'dbt:staging': 'dbt Staging', 'dbt:mart': 'dbt Marts', manual: 'Manual' }
              const Icon = icons[key]
              const color = colors[key]
              return (
                <div key={key} style={{ background: '#09111E', border: `1px solid ${C.border}`, borderRadius: 10, padding: 14 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 10 }}>
                    <Icon size={12} style={{ color }} />
                    <span style={{ fontSize: 11, color, fontWeight: 600 }}>{labels[key]}</span>
                  </div>
                  <p style={{ fontSize: 20, fontWeight: 700, color: C.textPrimary, margin: '0 0 2px' }}>${Number(b?.total_saved || 0).toFixed(3)}</p>
                  <p style={{ fontSize: 11, color: C.textMuted, margin: 0 }}>{b?.query_count || 0} quer{b?.query_count === 1 ? 'y' : 'ies'} · {Number(b?.avg_pct || 0).toFixed(1)}% avg</p>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Two-panel SQL editor */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        {/* Left: SQL Input */}
        <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, padding: 20, display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div>
            <p style={{ fontSize: 11, letterSpacing: '0.08em', textTransform: 'uppercase' as const, color: C.textLabel, fontWeight: 600, margin: '0 0 10px' }}>SQL Input</p>
            <textarea
              value={sql} onChange={e => setSql(e.target.value)}
              style={{ width: '100%', height: 280, padding: '12px 14px', borderRadius: 8, fontSize: 13, fontFamily: 'ui-monospace, monospace', resize: 'none', background: '#060D18', border: `1px solid ${C.border}`, color: '#CBD5E1', outline: 'none', boxSizing: 'border-box', lineHeight: 1.6 }}
              placeholder="SELECT * FROM your_table..."
            />
          </div>
          <button
            onClick={() => optimize.mutate()}
            disabled={optimize.isPending || !sql.trim()}
            style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, padding: '12px 0', borderRadius: 8, fontSize: 14, fontWeight: 600, cursor: 'pointer', background: 'linear-gradient(135deg, #0EA5E9, #7C3AED)', color: 'white', border: 'none', opacity: optimize.isPending || !sql.trim() ? 0.6 : 1 }}>
            <Zap size={15} />
            {optimize.isPending ? 'Optimizing…' : '⚡ Optimize Query'}
          </button>
        </div>

        {/* Right: Results */}
        <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, padding: 20 }}>
          <p style={{ fontSize: 11, letterSpacing: '0.08em', textTransform: 'uppercase' as const, color: C.textLabel, fontWeight: 600, margin: '0 0 14px' }}>Optimized Result</p>
          {!result && !optimize.isPending && (
            <div style={{ height: 280, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 12, textAlign: 'center' }}>
              <div style={{ width: 60, height: 60, borderRadius: 16, background: 'rgba(124,58,237,0.12)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <Zap size={26} style={{ color: C.violet }} />
              </div>
              <div>
                <p style={{ fontWeight: 600, color: C.textPrimary, margin: '0 0 4px' }}>Paste a query and click Optimize</p>
                <p style={{ fontSize: 12, color: C.textMuted, margin: 0 }}>AI will rewrite it for maximum performance</p>
              </div>
            </div>
          )}
          {optimize.isPending && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, height: 280, justifyContent: 'center' }}>
              {[90, 75, 55].map((w, i) => (
                <div key={i} style={{ height: 10, borderRadius: 5, background: C.border, width: `${w}%`, opacity: 0.8 }} />
              ))}
            </div>
          )}
          {result && !optimize.isPending && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              {/* Savings badge */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px', borderRadius: 8, background: 'rgba(16,185,129,0.1)', border: '1px solid rgba(16,185,129,0.2)' }}>
                <Zap size={15} style={{ color: C.emerald }} />
                <span style={{ fontSize: 13, fontWeight: 600, color: C.emerald }}>
                  {result.savings_percent}% faster · ${result.dollar_savings?.toFixed(4)} saved
                </span>
              </div>
              {/* Anti-patterns */}
              {(result.anti_patterns?.length ?? 0) > 0 && (
                <div>
                  <p style={{ fontSize: 11, color: C.textLabel, fontWeight: 600, margin: '0 0 6px', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Issues Detected</p>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {result.anti_patterns!.map((ap: AntiPattern) => (
                      <span key={ap.type} style={{ fontSize: 11, padding: '3px 8px', borderRadius: 5, background: 'rgba(245,158,11,0.12)', color: C.amber }}>{ap.type}</span>
                    ))}
                  </div>
                </div>
              )}
              {/* Changes made */}
              {(result.changes_made?.length ?? 0) > 0 && (
                <div>
                  <p style={{ fontSize: 11, color: C.textLabel, fontWeight: 600, margin: '0 0 6px', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Changes Made</p>
                  <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 4 }}>
                    {result.changes_made!.map((c: string, i: number) => (
                      <li key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 8, fontSize: 13 }}>
                        <span style={{ color: C.emerald, marginTop: 2 }}>•</span>
                        <span style={{ color: C.textPrimary }}>{c}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {/* Optimized SQL */}
              <div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                  <p style={{ fontSize: 11, color: C.textLabel, fontWeight: 600, margin: 0, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Optimized SQL</p>
                  <button onClick={copyOptimized}
                    style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 12, padding: '4px 10px', borderRadius: 6, background: 'transparent', border: `1px solid ${C.border}`, color: C.textMuted, cursor: 'pointer' }}>
                    {copied ? <><Check size={11} style={{ color: C.emerald }} /> Copied</> : <><Copy size={11} /> Copy</>}
                  </button>
                </div>
                <CodeBlock code={result.optimized_sql || ''} language="sql" maxLines={15} />
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Tips row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
        {TIPS.map(t => {
          const Icon = t.icon
          return (
            <div key={t.title} style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 10, padding: '14px 16px', display: 'flex', alignItems: 'flex-start', gap: 12 }}>
              <div style={{ width: 30, height: 30, borderRadius: 8, background: 'rgba(14,165,233,0.12)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, marginTop: 2 }}>
                <Icon size={14} style={{ color: C.accent }} />
              </div>
              <div>
                <p style={{ fontSize: 12, fontWeight: 600, color: C.textPrimary, margin: '0 0 3px' }}>{t.title}</p>
                <p style={{ fontSize: 11, color: C.textMuted, margin: 0, lineHeight: 1.5 }}>{t.desc}</p>
              </div>
            </div>
          )
        })}
      </div>

      {/* Optimization history table */}
      {(history.length > 0 || (savings?.history?.length > 0)) && (
        <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, padding: 20 }}>
          <p style={{ fontSize: 11, letterSpacing: '0.08em', textTransform: 'uppercase' as const, color: C.textLabel, fontWeight: 600, margin: '0 0 14px' }}>Optimization History</p>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Query', 'Saved $', 'Saved %', 'Date'].map(h => (
                  <th key={h} style={{ fontSize: 11, letterSpacing: '0.08em', textTransform: 'uppercase' as const, color: C.textLabel, fontWeight: 600, padding: '0 0 10px', textAlign: 'left' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(history.length > 0 ? history : (savings?.history || []).slice(0,5)).map((h: SavingsHistory, i: number) => (
                <tr key={i} style={{ borderTop: `1px solid ${C.border}` }}>
                  <td style={{ padding: '10px 0', fontSize: 12, fontFamily: 'ui-monospace, monospace', color: C.textPrimary, maxWidth: 260, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {(h.original_sql || '').substring(0,60)}…
                  </td>
                  <td style={{ padding: '10px 0', fontSize: 12, color: C.emerald, fontWeight: 600 }}>${Number(h.dollar_savings || 0).toFixed(3)}</td>
                  <td style={{ padding: '10px 0', fontSize: 12, color: C.emerald, fontWeight: 600 }}>{'-' + Number(h.savings_percent || 0).toFixed(0) + '%'}</td>
                  <td style={{ padding: '10px 0', fontSize: 11, color: C.textMuted }}>{h.ts ? new Date(h.ts).toLocaleDateString() : h.created_at ? new Date(h.created_at).toLocaleDateString() : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </motion.div>
  )
}
