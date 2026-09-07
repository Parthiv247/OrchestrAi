'use client'

import { useState } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import type { LucideIcon } from 'lucide-react'
import {
  LayoutDashboard, GitBranch, ShieldCheck, Zap, Database,
  MessageSquare, Activity, Settings, Share2, Plug, Mail,
  ChevronLeft, ChevronRight, X, ClipboardCheck,
} from 'lucide-react'

interface NavItem {
  icon: LucideIcon
  label: string
  href: string
}

interface NavSection {
  label: string
  items: NavItem[]
}

const SECTIONS: NavSection[] = [
  {
    label: 'Overview',
    items: [
      { icon: LayoutDashboard, label: 'Overview',   href: '/' },
      { icon: Plug,            label: 'Connectors', href: '/connectors' },
      { icon: GitBranch,       label: 'Pipelines',  href: '/pipelines' },
    ],
  },
  {
    label: 'Monitor',
    items: [
      { icon: ShieldCheck, label: 'Approvals',     href: '/approvals' },
      { icon: Activity,    label: 'Observability', href: '/observability' },
      { icon: ClipboardCheck, label: 'Data Quality', href: '/quality' },
    ],
  },
  {
    label: 'Analyze',
    items: [
      { icon: MessageSquare, label: 'AI Analyst',     href: '/analyst' },
      { icon: Share2,        label: 'Data Lineage',   href: '/lineage' },
      { icon: Zap,           label: 'Cost Optimizer', href: '/optimizer' },
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

function isActive(pathname: string, href: string): boolean {
  if (href === '/') return pathname === '/'
  return pathname === href || pathname.startsWith(href + '/')
}

interface SidebarProps {
  collapsed: boolean
  setCollapsed: (v: boolean) => void
  mobileOpen: boolean
  setMobileOpen: (v: boolean) => void
}

interface TooltipNavItemProps {
  item: NavItem
  active: boolean
  collapsed: boolean
  delay: number
  onClose?: () => void
}

function TooltipNavItem({ item, active, collapsed, delay, onClose }: TooltipNavItemProps) {
  const [hovered, setHovered] = useState(false)

  return (
    <motion.div
      key={item.href}
      initial={{ opacity: 0, x: -12 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay, duration: 0.25, ease: 'easeOut' }}
      style={{ position: 'relative' }}>
      <Link
        href={item.href}
        onClick={onClose}
        className="group relative flex items-center transition-colors duration-150"
        style={{
          height: 36,
          borderRadius: 10,
          gap: collapsed ? 0 : 10,
          paddingLeft: collapsed ? 0 : 12,
          paddingRight: collapsed ? 0 : 12,
          justifyContent: collapsed ? 'center' : 'flex-start',
          background: active ? 'rgba(14,165,233,0.10)' : 'transparent',
          color: active ? '#0EA5E9' : '#7A94B0',
        }}
        onMouseEnter={e => {
          setHovered(true)
          if (!active) {
            e.currentTarget.style.background = 'rgba(255,255,255,0.04)'
            e.currentTarget.style.color = '#CBD5E1'
          }
        }}
        onMouseLeave={e => {
          setHovered(false)
          if (!active) {
            e.currentTarget.style.background = 'transparent'
            e.currentTarget.style.color = '#7A94B0'
          }
        }}>
        {active && (
          <motion.span
            layoutId="sidebar-active-bar"
            className="absolute left-0 rounded-full"
            style={{ top: 8, bottom: 8, width: 2, background: '#0EA5E9' }}
          />
        )}
        <item.icon size={16} strokeWidth={active ? 2.2 : 1.8} className="flex-shrink-0" />
        <AnimatePresence initial={false}>
          {!collapsed && (
            <motion.span
              initial={{ opacity: 0, width: 0 }}
              animate={{ opacity: 1, width: 'auto' }}
              exit={{ opacity: 0, width: 0 }}
              transition={{ duration: 0.15, ease: 'easeInOut' }}
              style={{ fontSize: 13.5, fontWeight: 500, overflow: 'hidden', whiteSpace: 'nowrap' }}>
              {item.label}
            </motion.span>
          )}
        </AnimatePresence>
      </Link>

      {/* Tooltip for collapsed state */}
      <AnimatePresence>
        {collapsed && hovered && (
          <motion.div
            initial={{ opacity: 0, x: -4 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -4 }}
            transition={{ duration: 0.12 }}
            style={{
              position: 'absolute',
              left: '100%',
              top: '50%',
              transform: 'translateY(-50%)',
              marginLeft: 10,
              background: 'var(--card-bg)',
              border: '1px solid var(--border)',
              borderRadius: 8,
              padding: '5px 10px',
              fontSize: 12,
              fontWeight: 500,
              color: 'var(--text-primary)',
              whiteSpace: 'nowrap',
              zIndex: 100,
              boxShadow: '0 4px 16px rgba(0,0,0,0.4)',
              pointerEvents: 'none',
            }}>
            {item.label}
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

function SidebarContent({
  collapsed,
  setCollapsed,
  onClose,
  forceExpanded,
}: {
  collapsed: boolean
  setCollapsed: (v: boolean) => void
  onClose?: () => void
  forceExpanded?: boolean
}) {
  const pathname = usePathname()
  const showExpanded = forceExpanded || !collapsed
  let itemIndex = 0

  return (
    <>
      {/* ── Logo ─────────────────────────────────────────────────────── */}
      <div
        className="flex items-center flex-shrink-0 overflow-hidden"
        style={{
          height: 64,
          paddingLeft: showExpanded ? 16 : 0,
          paddingRight: showExpanded ? 8 : 0,
          justifyContent: showExpanded ? 'flex-start' : 'center',
          gap: showExpanded ? 10 : 0,
        }}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/logo-icon.svg" alt="OrchestrAI" width={32} height={32} className="flex-shrink-0" />
        <AnimatePresence initial={false}>
          {showExpanded && (
            <motion.div
              initial={{ opacity: 0, width: 0 }}
              animate={{ opacity: 1, width: 'auto' }}
              exit={{ opacity: 0, width: 0 }}
              transition={{ duration: 0.15 }}
              className="flex items-center gap-2 overflow-hidden">
              <span className="font-bold text-[15px] tracking-tight whitespace-nowrap" style={{ color: 'var(--text-primary)' }}>
                OrchestrAI
              </span>
              <span
                className="text-[9px] font-semibold px-1.5 py-0.5 rounded-md flex-shrink-0"
                style={{
                  background: 'rgba(14,165,233,0.12)',
                  color: '#0EA5E9',
                  border: '1px solid rgba(14,165,233,0.25)',
                  letterSpacing: '0.04em',
                }}>
                v2.0
              </span>
            </motion.div>
          )}
        </AnimatePresence>
        {/* Mobile close button */}
        {onClose && (
          <button
            onClick={onClose}
            className="ml-auto flex items-center justify-center w-7 h-7 rounded-lg hover:bg-white/5 transition-colors"
            aria-label="Close navigation">
            <X size={15} style={{ color: '#64748B' }} />
          </button>
        )}
      </div>

      {/* ── Navigation ───────────────────────────────────────────────── */}
      <nav className="flex-1 overflow-y-auto pb-3 scrollbar-hide" style={{ paddingLeft: 12, paddingRight: 12 }}>
        {SECTIONS.map(section => (
          <div key={section.label}>
            <AnimatePresence initial={false}>
              {showExpanded && (
                <motion.p
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.12 }}
                  className="uppercase"
                  style={{
                    fontSize: 10,
                    fontWeight: 600,
                    letterSpacing: '0.1em',
                    color: 'var(--text-label)',
                    padding: '16px 12px 4px',
                  }}>
                  {section.label}
                </motion.p>
              )}
            </AnimatePresence>
            {!showExpanded && <div style={{ height: 12 }} />}
            <div className="space-y-0.5">
              {section.items.map(item => {
                const active = isActive(pathname, item.href)
                const delay = itemIndex++ * 0.03
                return (
                  <TooltipNavItem
                    key={item.href}
                    item={item}
                    active={active}
                    collapsed={!showExpanded}
                    delay={delay}
                    onClose={onClose}
                  />
                )
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* ── Bottom: status + collapse toggle ─────────────────────────── */}
      <div className="flex-shrink-0 px-3 pb-4 space-y-2">
        {/* System status card — full when expanded, just dot when collapsed */}
        <AnimatePresence initial={false}>
          {showExpanded ? (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.15 }}
              className="flex items-center gap-2.5 px-3 py-2.5"
              style={{
                background: 'var(--input-bg)',
                border: '1px solid var(--border-light)',
                borderRadius: 10,
              }}>
              <span className="status-dot pulse-green flex-shrink-0" style={{ background: '#10B981' }} />
              <div className="min-w-0">
                <p style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)', lineHeight: '14px' }}>
                  All systems operational
                </p>
                <p style={{ fontSize: 10, color: 'var(--text-label)', lineHeight: '13px' }}>
                  99.98% uptime · 30 days
                </p>
              </div>
            </motion.div>
          ) : (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.15 }}
              className="flex items-center justify-center py-1">
              <span className="status-dot pulse-green" style={{ background: '#10B981' }} />
            </motion.div>
          )}
        </AnimatePresence>

        {/* Collapse toggle — desktop only (hidden when rendered as mobile overlay) */}
        {!onClose && (
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="w-full flex items-center justify-center h-8 rounded-lg hover:bg-white/5 transition-colors"
            style={{ border: '1px solid var(--border-light)' }}
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}>
            {collapsed
              ? <ChevronRight size={14} style={{ color: 'var(--text-label)' }} />
              : <ChevronLeft size={14} style={{ color: 'var(--text-label)' }} />}
          </button>
        )}
      </div>
    </>
  )
}

export function Sidebar({ collapsed, setCollapsed, mobileOpen, setMobileOpen }: SidebarProps) {
  return (
    <>
      {/* ── Desktop sidebar ──────────────────────────────────────────── */}
      <motion.aside
        className="fixed left-0 top-0 h-screen flex-col z-50 select-none hidden md:flex"
        animate={{ width: collapsed ? 64 : 240 }}
        transition={{ duration: 0.2, ease: [0.2, 0.8, 0.2, 1] }}
        style={{ background: 'var(--sidebar-bg)', borderRight: '1px solid var(--border-light)', overflow: 'hidden' }}>
        <SidebarContent
          collapsed={collapsed}
          setCollapsed={setCollapsed}
        />
      </motion.aside>

      {/* ── Mobile sidebar overlay ───────────────────────────────────── */}
      <AnimatePresence>
        {mobileOpen && (
          <motion.aside
            initial={{ x: -280 }}
            animate={{ x: 0 }}
            exit={{ x: -280 }}
            transition={{ duration: 0.22, ease: [0.2, 0.8, 0.2, 1] }}
            className="fixed left-0 top-0 h-screen flex flex-col z-50 select-none md:hidden"
            style={{ width: 240, background: 'var(--sidebar-bg)', borderRight: '1px solid var(--border-light)' }}>
            <SidebarContent
              collapsed={false}
              setCollapsed={setCollapsed}
              onClose={() => setMobileOpen(false)}
              forceExpanded
            />
          </motion.aside>
        )}
      </AnimatePresence>
    </>
  )
}
