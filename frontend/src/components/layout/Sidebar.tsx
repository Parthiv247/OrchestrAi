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
  PanelLeftClose, PanelLeft,
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
      { icon: ShieldCheck,    label: 'Approvals',     href: '/approvals', badge: 'live' },
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

// Tooltip that appears when sidebar is collapsed
function CollapseTooltip({ label, children }: { label: string; children: React.ReactNode }) {
  const [visible, setVisible] = useState(false)
  return (
    <div
      style={{ position: 'relative' }}
      onMouseEnter={() => setVisible(true)}
      onMouseLeave={() => setVisible(false)}
    >
      {children}
      <AnimatePresence>
        {visible && (
          <motion.div
            initial={{ opacity: 0, x: -4 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -4 }}
            transition={{ duration: 0.12 }}
            style={{
              position: 'absolute', left: '100%', top: '50%', transform: 'translateY(-50%)',
              marginLeft: 10, zIndex: 200, pointerEvents: 'none',
              background: '#1A3A5C', border: '1px solid #2D5070', borderRadius: 7,
              padding: '5px 10px', whiteSpace: 'nowrap',
              fontSize: 12, fontWeight: 600, color: '#F1F5F9',
              boxShadow: '0 4px 16px rgba(0,0,0,0.35)',
            }}
          >
            {label}
            {/* Arrow */}
            <div style={{
              position: 'absolute', right: '100%', top: '50%', transform: 'translateY(-50%)',
              borderTop: '4px solid transparent', borderBottom: '4px solid transparent',
              borderRight: '5px solid #1A3A5C',
            }} />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

export function Sidebar() {
  const pathname = usePathname()
  const [collapsed, setCollapsed] = useState(false)

  return (
    <motion.aside
      animate={{ width: collapsed ? 60 : 224 }}
      transition={{ duration: 0.22, ease: [0.25, 0.46, 0.45, 0.94] }}
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
        padding: '0 14px',
        borderBottom: '1px solid var(--border, #1A3A5C)',
        gap: 10,
        flexShrink: 0,
      }}>
        <div style={{
          width: 30, height: 30, borderRadius: 9, flexShrink: 0,
          background: 'linear-gradient(135deg, #0EA5E9 0%, #7C3AED 100%)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          boxShadow: '0 0 14px rgba(14,165,233,0.4)',
        }}>
          <Zap size={15} style={{ color: '#fff' }} />
        </div>
        <AnimatePresence>
          {!collapsed && (
            <motion.div
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -10 }}
              transition={{ duration: 0.16 }}
              style={{ overflow: 'hidden', whiteSpace: 'nowrap', flex: 1 }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                <span style={{ fontSize: 14.5, fontWeight: 800, color: 'var(--text-primary)', letterSpacing: '-0.02em' }}>
                  OrchestrAI
                </span>
                <span style={{
                  fontSize: 9, fontWeight: 700, letterSpacing: '0.06em',
                  padding: '2px 6px', borderRadius: 5,
                  background: 'linear-gradient(135deg, rgba(14,165,233,0.25), rgba(124,58,237,0.25))',
                  border: '1px solid rgba(14,165,233,0.3)',
                  color: '#0EA5E9',
                }}>
                  v2.0
                </span>
              </div>
              <p style={{ fontSize: 10, color: 'var(--text-label)', margin: 0, letterSpacing: '0.02em' }}>
                Self-Healing Data Platform
              </p>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* ── Nav ── */}
      <nav
        style={{ flex: 1, overflowY: 'auto', overflowX: 'hidden', padding: '8px 6px' }}
        className="scrollbar-hide"
      >
        {SECTIONS.map((section, si) => (
          <div key={section.label} style={{ marginBottom: 2 }}>
            {/* Section label */}
            <AnimatePresence>
              {!collapsed && (
                <motion.p
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  style={{
                    fontSize: 9.5, fontWeight: 700, letterSpacing: '0.12em',
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
              const navItem = (
                <Link key={item.href} href={item.href} style={{ textDecoration: 'none', display: 'block', outline: 'none' }}>
                  <motion.div
                    whileTap={{ scale: 0.97 }}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 9,
                      padding: collapsed ? '9px 15px' : '7px 10px',
                      borderRadius: 9,
                      marginBottom: 1,
                      background: active
                        ? 'rgba(14,165,233,0.13)'
                        : 'transparent',
                      border: active
                        ? '1px solid rgba(14,165,233,0.22)'
                        : '1px solid transparent',
                      cursor: 'pointer',
                      position: 'relative',
                      transition: 'background 0.15s, border-color 0.15s',
                      justifyContent: collapsed ? 'center' : 'flex-start',
                    }}
                    onMouseEnter={e => {
                      if (!active) {
                        (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.045)'
                        const icon = (e.currentTarget as HTMLElement).querySelector('.nav-icon') as HTMLElement
                        if (icon) icon.style.color = 'var(--text-primary)'
                      }
                    }}
                    onMouseLeave={e => {
                      if (!active) {
                        (e.currentTarget as HTMLElement).style.background = 'transparent'
                        const icon = (e.currentTarget as HTMLElement).querySelector('.nav-icon') as HTMLElement
                        if (icon) icon.style.color = 'var(--text-muted)'
                      }
                    }}
                  >
                    {/* Active bar */}
                    {active && (
                      <motion.div
                        layoutId="active-bar"
                        style={{
                          position: 'absolute', left: 0, top: '50%', transform: 'translateY(-50%)',
                          width: 3, height: 16, borderRadius: '0 3px 3px 0',
                          background: 'linear-gradient(180deg, #0EA5E9, #7C3AED)',
                        }}
                      />
                    )}

                    <Icon
                      size={15}
                      className="nav-icon"
                      style={{
                        color: active ? '#0EA5E9' : 'var(--text-muted)',
                        flexShrink: 0,
                        transition: 'color 0.15s',
                      }}
                    />

                    <AnimatePresence>
                      {!collapsed && (
                        <motion.div
                          initial={{ opacity: 0 }}
                          animate={{ opacity: 1 }}
                          exit={{ opacity: 0 }}
                          style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1, minWidth: 0 }}
                        >
                          <span style={{
                            fontSize: 13, fontWeight: active ? 600 : 500,
                            color: active ? 'var(--text-primary)' : 'var(--text-secondary)',
                            whiteSpace: 'nowrap', transition: 'color 0.15s', flex: 1,
                          }}>
                            {item.label}
                          </span>
                          {item.badge === 'live' && (
                            <span style={{
                              display: 'inline-flex', alignItems: 'center', gap: 3,
                              fontSize: 8.5, fontWeight: 700, letterSpacing: '0.06em',
                              padding: '2px 5px', borderRadius: 4,
                              background: 'rgba(16,185,129,0.12)',
                              border: '1px solid rgba(16,185,129,0.25)',
                              color: '#10B981',
                            }}>
                              <span style={{ width: 4, height: 4, borderRadius: '50%', background: '#10B981', animation: 'pulse-green 2s infinite' }} />
                              LIVE
                            </span>
                          )}
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </motion.div>
                </Link>
              )

              return collapsed ? (
                <CollapseTooltip key={item.href} label={item.label}>
                  {navItem}
                </CollapseTooltip>
              ) : (
                <div key={item.href}>{navItem}</div>
              )
            })}

            {/* Section divider — skip after last section */}
            {si < SECTIONS.length - 1 && (
              <div style={{ height: 1, background: 'var(--border-light)', margin: '6px 4px 4px' }} />
            )}
          </div>
        ))}
      </nav>

      {/* ── Footer ── */}
      <div style={{
        borderTop: '1px solid var(--border)',
        padding: '10px 8px',
        flexShrink: 0,
      }}>
        {!collapsed && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 9,
            padding: '8px 10px', borderRadius: 9, marginBottom: 8,
            background: 'rgba(16,185,129,0.07)',
            border: '1px solid rgba(16,185,129,0.15)',
          }}>
            <div style={{
              width: 7, height: 7, borderRadius: '50%', background: '#10B981',
              animation: 'pulse-green 2s infinite', flexShrink: 0,
            }} />
            <div>
              <p style={{ fontSize: 11, fontWeight: 600, color: '#10B981', margin: 0 }}>All systems operational</p>
              <p style={{ fontSize: 10, color: 'var(--text-muted)', margin: 0 }}>99.98% uptime · 11 agents active</p>
            </div>
          </div>
        )}

        <button
          onClick={() => setCollapsed(!collapsed)}
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          style={{
            width: '100%', display: 'flex', alignItems: 'center',
            justifyContent: collapsed ? 'center' : 'flex-end',
            gap: 6, background: 'none', border: 'none', cursor: 'pointer',
            color: 'var(--text-muted)', fontSize: 11, padding: '6px 4px',
            borderRadius: 7, transition: 'color 0.15s, background 0.15s',
          }}
          onMouseEnter={e => {
            e.currentTarget.style.color = 'var(--text-primary)'
            e.currentTarget.style.background = 'rgba(255,255,255,0.04)'
          }}
          onMouseLeave={e => {
            e.currentTarget.style.color = 'var(--text-muted)'
            e.currentTarget.style.background = 'transparent'
          }}
        >
          {collapsed
            ? <PanelLeft size={15} />
            : <><PanelLeftClose size={15} /><span>Collapse</span></>
          }
        </button>
      </div>
    </motion.aside>
  )
}
