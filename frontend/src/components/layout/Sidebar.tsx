'use client'

import { useState } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import type { LucideIcon } from 'lucide-react'
import {
  LayoutDashboard, GitBranch, ShieldCheck, Zap, Database,
  MessageSquare, Activity, Settings, Share2, Plug, Mail,
  ChevronLeft, ChevronRight, ClipboardCheck, TrendingUp,
} from 'lucide-react'

interface NavItem { icon: LucideIcon; label: string; href: string; badge?: string }
interface NavSection { label: string; items: NavItem[] }

const SECTIONS: NavSection[] = [
  {
    label: 'Core',
    items: [
      { icon: LayoutDashboard, label: 'Overview',     href: '/' },
      { icon: Plug,            label: 'Connectors',   href: '/connectors' },
      { icon: GitBranch,       label: 'Pipelines',    href: '/pipelines' },
    ],
  },
  {
    label: 'Monitor',
    items: [
      { icon: ShieldCheck,    label: 'Approvals',     href: '/approvals' },
      { icon: Activity,       label: 'Observability', href: '/observability' },
      { icon: ClipboardCheck, label: 'Data Quality',  href: '/quality' },
    ],
  },
  {
    label: 'Analyze',
    items: [
      { icon: MessageSquare, label: 'AI Analyst',     href: '/analyst' },
      { icon: Share2,        label: 'Data Lineage',   href: '/lineage' },
      { icon: TrendingUp,    label: 'Cost Optimizer', href: '/optimizer' },
    ],
  },
  {
    label: 'Build',
    items: [
      { icon: Database, label: 'dbt Assistant', href: '/dbt' },
      { icon: Mail,     label: 'Reports',       href: '/reports' },
      { icon: Settings, label: 'Settings',      href: '/settings' },
    ],
  },
]

function isActive(pathname: string, href: string) {
  if (href === '/') return pathname === '/'
  return pathname.startsWith(href)
}

export function Sidebar() {
  const pathname = usePathname()
  const [collapsed, setCollapsed] = useState(false)

  return (
    <motion.aside
      animate={{ width: collapsed ? 64 : 220 }}
      transition={{ duration: 0.25, ease: [0.25, 0.46, 0.45, 0.94] }}
      style={{
        height: '100vh',
        background: 'var(--sidebar-bg, #09111E)',
        borderRight: '1px solid var(--border, #1A3A5C)',
        display: 'flex',
        flexDirection: 'column',
        position: 'fixed',
        left: 0,
        top: 0,
        zIndex: 50,
        overflow: 'hidden',
        flexShrink: 0,
      }}
    >
      {/* ── Logo ── */}
      <div style={{
        height: 56,
        display: 'flex',
        alignItems: 'center',
        padding: collapsed ? '0 18px' : '0 18px',
        borderBottom: '1px solid var(--border, #1A3A5C)',
        gap: 10,
        flexShrink: 0,
      }}>
        {/* Logo mark */}
        <div style={{
          width: 28, height: 28, borderRadius: 8, flexShrink: 0,
          background: 'linear-gradient(135deg, #0EA5E9, #7C3AED)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          boxShadow: '0 0 12px rgba(14,165,233,0.35)',
        }}>
          <span style={{ fontSize: 13, fontWeight: 800, color: '#fff', letterSpacing: '-0.03em' }}>O</span>
        </div>
        <AnimatePresence>
          {!collapsed && (
            <motion.div
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -8 }}
              transition={{ duration: 0.18 }}
              style={{ overflow: 'hidden', whiteSpace: 'nowrap' }}
            >
              <span style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-primary)', letterSpacing: '-0.02em' }}>OrchestrAI</span>
              <span style={{
                marginLeft: 6, fontSize: 9, fontWeight: 700, letterSpacing: '0.08em',
                padding: '2px 5px', borderRadius: 4,
                background: 'rgba(14,165,233,0.15)', color: '#0EA5E9',
              }}>v2.0</span>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* ── Nav ── */}
      <nav style={{ flex: 1, overflowY: 'auto', overflowX: 'hidden', padding: '12px 8px' }}>
        {SECTIONS.map((section) => (
          <div key={section.label} style={{ marginBottom: 4 }}>
            {/* Section label */}
            <AnimatePresence>
              {!collapsed && (
                <motion.p
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  style={{
                    fontSize: 10, fontWeight: 700, letterSpacing: '0.1em',
                    textTransform: 'uppercase', color: 'var(--text-label)',
                    padding: '10px 10px 4px', margin: 0,
                  }}
                >
                  {section.label}
                </motion.p>
              )}
            </AnimatePresence>

            {section.items.map((item) => {
              const active = isActive(pathname, item.href)
              const Icon = item.icon
              return (
                <Link key={item.href} href={item.href} style={{ textDecoration: 'none', display: 'block' }}>
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 10,
                    padding: collapsed ? '9px 18px' : '8px 10px',
                    borderRadius: 8,
                    marginBottom: 1,
                    background: active ? 'rgba(14,165,233,0.12)' : 'transparent',
                    border: active ? '1px solid rgba(14,165,233,0.2)' : '1px solid transparent',
                    transition: 'all 0.15s ease',
                    cursor: 'pointer',
                    position: 'relative',
                  }}
                  onMouseEnter={e => { if (!active) (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.04)' }}
                  onMouseLeave={e => { if (!active) (e.currentTarget as HTMLElement).style.background = 'transparent' }}
                  >
                    {/* Active indicator bar */}
                    {active && (
                      <div style={{
                        position: 'absolute', left: 0, top: '50%', transform: 'translateY(-50%)',
                        width: 3, height: 18, borderRadius: '0 3px 3px 0',
                        background: '#0EA5E9',
                      }} />
                    )}
                    <Icon
                      size={15}
                      style={{
                        color: active ? '#0EA5E9' : 'var(--text-muted)',
                        flexShrink: 0,
                        transition: 'color 0.15s',
                      }}
                    />
                    <AnimatePresence>
                      {!collapsed && (
                        <motion.span
                          initial={{ opacity: 0 }}
                          animate={{ opacity: 1 }}
                          exit={{ opacity: 0 }}
                          style={{
                            fontSize: 13,
                            fontWeight: active ? 600 : 500,
                            color: active ? 'var(--text-primary)' : 'var(--text-secondary)',
                            whiteSpace: 'nowrap',
                            transition: 'color 0.15s',
                          }}
                        >
                          {item.label}
                        </motion.span>
                      )}
                    </AnimatePresence>
                  </div>
                </Link>
              )
            })}
            {/* Section divider */}
            <div style={{ height: 1, background: 'var(--border-light)', margin: '8px 4px' }} />
          </div>
        ))}
      </nav>

      {/* ── Footer: status + collapse ── */}
      <div style={{
        borderTop: '1px solid var(--border)',
        padding: collapsed ? '12px 14px' : '12px 14px',
        flexShrink: 0,
      }}>
        {!collapsed && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 8,
            padding: '8px 10px', borderRadius: 8,
            background: 'rgba(16,185,129,0.07)',
            border: '1px solid rgba(16,185,129,0.15)',
            marginBottom: 8,
          }}>
            <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#10B981', animation: 'pulse-green 2s infinite', flexShrink: 0 }} />
            <div style={{ overflow: 'hidden' }}>
              <p style={{ fontSize: 11, fontWeight: 600, color: '#10B981', margin: 0 }}>All systems operational</p>
              <p style={{ fontSize: 10, color: 'var(--text-muted)', margin: 0 }}>99.98% uptime</p>
            </div>
          </div>
        )}
        <button
          onClick={() => setCollapsed(!collapsed)}
          style={{
            width: '100%', display: 'flex', alignItems: 'center', justifyContent: collapsed ? 'center' : 'flex-end',
            gap: 6, background: 'none', border: 'none', cursor: 'pointer',
            color: 'var(--text-muted)', fontSize: 11, padding: '4px 0',
            transition: 'color 0.15s',
          }}
          onMouseEnter={e => (e.currentTarget.style.color = 'var(--text-primary)')}
          onMouseLeave={e => (e.currentTarget.style.color = 'var(--text-muted)')}
        >
          {collapsed ? <ChevronRight size={14} /> : <><ChevronLeft size={14} /><span>Collapse</span></>}
        </button>
      </div>
    </motion.aside>
  )
}
