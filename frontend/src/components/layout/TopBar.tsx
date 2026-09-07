'use client'

import { useState, useRef, useEffect } from 'react'
import { usePathname, useRouter } from 'next/navigation'
import {
  Bell, Shield, LogOut, User, X, Settings, Search,
  ChevronRight, RefreshCw, Menu,
} from 'lucide-react'
import { useIncidents, useBackendHealth } from '@/lib/queries'
import { useToast } from '@/components/ui/Toaster'
import { formatDistanceToNow } from 'date-fns'
import { ThemeToggle } from '@/components/ui/ThemeToggle'

interface Incident {
  id: string | number
  anomaly_type?: string
  approval_status?: string
  pipeline_name?: string
  created_at?: string
  root_cause?: string
}

const TITLES: Record<string, string> = {
  '/': 'Overview',
  '/pipelines': 'Pipelines',
  '/pipelines/new': 'New Pipeline',
  '/connectors': 'Connector Gallery',
  '/approvals': 'Approval Panel',
  '/optimizer': 'Cost Optimizer',
  '/dbt': 'dbt Assistant',
  '/analyst': 'AI Analyst',
  '/lineage': 'Data Lineage',
  '/observability': 'Observability',
  '/quality': 'Data Quality',
  '/reports': 'Scheduled Reports',
  '/settings': 'Settings',
}

const SECTIONS: Record<string, string> = {
  '/': 'Overview',
  '/connectors': 'Overview',
  '/pipelines': 'Overview',
  '/pipelines/new': 'Overview',
  '/approvals': 'Monitor',
  '/observability': 'Monitor',
  '/quality': 'Monitor',
  '/analyst': 'Analyze',
  '/lineage': 'Analyze',
  '/optimizer': 'Analyze',
  '/dbt': 'Build',
  '/reports': 'Build',
  '/settings': 'Build',
}

const ANOMALY_COLOR: Record<string, string> = {
  ZERO_LOAD: '#EF4444',
  ROW_COUNT_DROP: '#F59E0B',
  ML_ANOMALY: '#0EA5E9',
  NULL_SPIKE: '#7C3AED',
  CONSECUTIVE_FAILURES: '#EF4444',
}

const DROPDOWN_STYLE: React.CSSProperties = {
  background: 'var(--card-bg)',
  border: '1px solid var(--border)',
  boxShadow: '0 12px 40px rgba(0,0,0,0.45)',
}

interface TopBarProps {
  sidebarWidth?: number
  onMobileMenuOpen?: () => void
}

export function TopBar({ sidebarWidth = 240, onMobileMenuOpen }: TopBarProps) {
  const pathname = usePathname()
  const router = useRouter()
  const toast = useToast()
  const { data: incidents } = useIncidents()
  const { data: healthData, isError: healthError } = useBackendHealth()
  const backendOk = !healthError && healthData?.status === 'ok'
  const [bellOpen, setBellOpen] = useState(false)
  const [avatarOpen, setAvatarOpen] = useState(false)
  const bellRef = useRef<HTMLDivElement>(null)
  const avatarRef = useRef<HTMLDivElement>(null)

  // User profile from localStorage
  const [userName, setUserName] = useState('Admin User')
  const [userEmail, setUserEmail] = useState('admin@orchestrai.io')
  useEffect(() => {
    try {
      const name = localStorage.getItem('profile_name'); if (name) setUserName(name)
      const email = localStorage.getItem('profile_email'); if (email) setUserEmail(email)
    } catch { /* localStorage unavailable (SSR / privacy mode) */ }
  }, [])
  const initials = userName.split(' ').map(p => p[0]).join('').toUpperCase().slice(0, 2) || 'A'

  // Simulated live-sync ticker
  const [syncSeconds, setSyncSeconds] = useState(2)
  useEffect(() => {
    const t = setInterval(() => setSyncSeconds(s => (s >= 30 ? 1 : s + 1)), 1000)
    return () => clearInterval(t)
  }, [])

  const allIncidents: Incident[] = (incidents as { incidents?: Incident[] } | undefined)?.incidents ?? []
  const activeCount = allIncidents.filter(i => i.approval_status === 'pending').length
  const recentIncidents = allIncidents.slice(0, 6)

  // Close dropdowns on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (bellRef.current && !bellRef.current.contains(e.target as Node)) setBellOpen(false)
      if (avatarRef.current && !avatarRef.current.contains(e.target as Node)) setAvatarOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const title = TITLES[pathname]
    ?? (pathname.startsWith('/pipelines/') ? 'Pipeline Detail' : 'OrchestrAI')
  const section = SECTIONS[pathname]
    ?? (pathname.startsWith('/pipelines/') ? 'Overview' : '')

  return (
    <header
      className="fixed top-0 right-0 z-40 flex items-center justify-between px-6"
      style={{
        left: sidebarWidth,
        height: 56,
        background: 'var(--topbar-bg)',
        backdropFilter: 'blur(12px)',
        WebkitBackdropFilter: 'blur(12px)',
        borderBottom: '1px solid var(--border-light)',
        transition: 'left 0.2s cubic-bezier(0.2,0.8,0.2,1)',
      }}>

      {/* ── Left: hamburger (mobile) + breadcrumb + page title ────────── */}
      <div className="flex items-center gap-1.5 min-w-0">
        <button
          className="md:hidden flex items-center justify-center w-8 h-8 rounded-lg mr-2 hover:bg-white/5 flex-shrink-0"
          onClick={onMobileMenuOpen}
          aria-label="Open navigation">
          <Menu size={18} style={{ color: '#94A3B8' }} />
        </button>
        {section && (
          <>
            <span style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-label)' }}>{section}</span>
            <ChevronRight size={12} style={{ color: 'var(--text-muted)' }} />
          </>
        )}
        <h1 style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary)' }} className="truncate">
          {title}
        </h1>
      </div>

      {/* ── Center: last-synced indicator ─────────────────────────────── */}
      <div className="hidden lg:flex items-center gap-2 absolute left-1/2 -translate-x-1/2">
        <RefreshCw size={11} className="animate-spin-slow" style={{ color: '#10B981' }} />
        <span className="status-dot pulse-green" style={{ background: '#10B981', width: 5, height: 5 }} />
        <span style={{ fontSize: 11.5, fontWeight: 500, color: 'var(--text-label)' }}>
          Last synced: {syncSeconds}s ago
        </span>
      </div>

      {/* ── Right: search · live · bell · workspace · avatar ──────────── */}
      <div className="flex items-center gap-3">

        {/* Cmd+K search chip */}
        <button
          onClick={() => {
            const e = new KeyboardEvent('keydown', { key: 'k', metaKey: true, bubbles: true })
            document.dispatchEvent(e)
          }}
          className="flex items-center gap-2 px-3 h-8 rounded-lg transition-all duration-150 hover:border-[#0EA5E9]"
          style={{
            background: 'var(--input-bg)',
            border: '1px solid var(--border)',
            color: 'var(--text-muted)',
            fontSize: 12,
          }}>
          <Search size={12} />
          <span className="hidden md:inline">Search</span>
          <kbd
            className="text-[10px] px-1.5 py-px rounded font-mono"
            style={{ background: 'rgba(255,255,255,0.06)', color: '#94A3B8', border: '1px solid #1A3A5C' }}>
            ⌘K
          </kbd>
        </button>

        {/* Backend health indicator — only show when connected */}
        {backendOk && (
          <div
            className="flex items-center gap-1.5 px-2.5 h-7 rounded-full"
            title="All systems operational"
            style={{ background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.2)' }}>
            <span className="status-dot pulse-green" style={{ background: '#10B981', width: 6, height: 6 }} />
            <span style={{ fontSize: 11, fontWeight: 600, color: '#10B981' }}>Live</span>
          </div>
        )}

        {/* Theme toggle */}
        <ThemeToggle />

        {/* Notification bell */}
        <div className="relative" ref={bellRef}>
          <button
            onClick={() => { setBellOpen(v => !v); setAvatarOpen(false) }}
            className="relative flex items-center justify-center w-8 h-8 rounded-lg transition-colors hover:bg-white/5"
            aria-label="Notifications">
            <Bell size={15} style={{ color: activeCount > 0 ? '#F59E0B' : '#64748B' }} />
            {activeCount > 0 && (
              <span
                className="absolute -top-0.5 -right-0.5 min-w-[15px] h-[15px] px-0.5 rounded-full text-[9px] flex items-center justify-center font-bold"
                style={{ background: '#F59E0B', color: '#080F1C' }}>
                {activeCount}
              </span>
            )}
          </button>

          {bellOpen && (
            <div className="absolute right-0 top-10 w-80 rounded-xl z-50 overflow-hidden" style={DROPDOWN_STYLE}>
              <div className="flex items-center justify-between px-4 py-3" style={{ borderBottom: '1px solid var(--border)' }}>
                <span style={{ fontSize: 13, fontWeight: 600, color: '#F1F5F9' }}>Incidents</span>
                <button
                  onClick={() => setBellOpen(false)}
                  className="p-1 rounded hover:bg-white/5 transition-colors"
                  aria-label="Close">
                  <X size={13} style={{ color: '#64748B' }} />
                </button>
              </div>
              <div className="max-h-72 overflow-y-auto">
                {recentIncidents.length === 0 ? (
                  <p className="text-center py-8" style={{ fontSize: 12.5, color: '#64748B' }}>
                    No incidents — all clear
                  </p>
                ) : recentIncidents.map(inc => (
                  <button
                    key={String(inc.id)}
                    onClick={() => { setBellOpen(false); router.push('/approvals') }}
                    className="w-full text-left px-4 py-3 hover:bg-white/[0.04] transition-colors flex items-start gap-3"
                    style={{ borderBottom: '1px solid var(--border-light)' }}>
                    <Shield
                      size={14}
                      className="mt-0.5 flex-shrink-0"
                      style={{ color: inc.approval_status === 'pending' ? '#F59E0B' : '#4B6B8E' }}
                    />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-2">
                        <span
                          className="metric-label"
                          style={{ color: ANOMALY_COLOR[inc.anomaly_type ?? ''] ?? '#94A3B8' }}>
                          {inc.anomaly_type ?? 'UNKNOWN'}
                        </span>
                        <span
                          className="text-[10px] px-1.5 py-0.5 rounded-full font-semibold flex-shrink-0"
                          style={inc.approval_status === 'pending'
                            ? { background: 'rgba(245,158,11,0.12)', color: '#F59E0B' }
                            : { background: 'rgba(100,116,139,0.12)', color: '#94A3B8' }}>
                          {inc.approval_status}
                        </span>
                      </div>
                      <p className="truncate mt-0.5" style={{ fontSize: 12.5, color: '#F1F5F9' }}>
                        {inc.pipeline_name}
                      </p>
                      <p className="mt-0.5" style={{ fontSize: 10.5, color: '#4B6B8E' }}>
                        {inc.created_at ? formatDistanceToNow(new Date(inc.created_at), { addSuffix: true }) : ''}
                      </p>
                    </div>
                  </button>
                ))}
              </div>
              <button
                onClick={() => { setBellOpen(false); router.push('/approvals') }}
                className="w-full text-center py-2.5 hover:bg-white/[0.04] transition-colors"
                style={{ fontSize: 12, fontWeight: 600, color: 'var(--accent)', borderTop: '1px solid var(--border)' }}>
                View all in Approval Panel →
              </button>
            </div>
          )}
        </div>

        {/* Avatar */}
        <div className="relative" ref={avatarRef}>
          <button
            onClick={() => { setAvatarOpen(v => !v); setBellOpen(false) }}
            className="w-8 h-8 rounded-full flex items-center justify-center text-[11px] font-bold text-white transition-transform hover:scale-105"
            style={{ background: 'linear-gradient(135deg, #0EA5E9, #7C3AED)', boxShadow: '0 0 0 2px rgba(14,165,233,0.15)' }}
            aria-label="Account menu">
            {initials}
          </button>

          {avatarOpen && (
            <div className="absolute right-0 top-10 w-56 rounded-xl z-50 overflow-hidden" style={DROPDOWN_STYLE}>
              <div className="px-4 py-3" style={{ borderBottom: '1px solid var(--border)' }}>
                <p style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>{userName}</p>
                <p className="mt-0.5 truncate" style={{ fontSize: 11.5, color: 'var(--text-muted)' }}>{userEmail}</p>
                <span
                  className="inline-block mt-1.5 text-[10px] px-2 py-0.5 rounded-full font-semibold"
                  style={{ background: 'rgba(124,58,237,0.14)', color: '#A78BFA' }}>
                  Admin
                </span>
              </div>
              <div className="p-1">
                <button
                  className="w-full flex items-center gap-2.5 px-3 h-8 rounded-lg hover:bg-white/[0.04] transition-colors"
                  style={{ fontSize: 12.5, color: 'var(--text-secondary)' }}
                  onClick={() => { setAvatarOpen(false); router.push('/settings') }}>
                  <User size={14} /> Profile
                </button>
                <button
                  className="w-full flex items-center gap-2.5 px-3 h-8 rounded-lg hover:bg-white/[0.04] transition-colors"
                  style={{ fontSize: 12.5, color: 'var(--text-secondary)' }}
                  onClick={() => { setAvatarOpen(false); router.push('/settings') }}>
                  <Settings size={14} /> Settings
                </button>
                <button
                  className="w-full flex items-center gap-2.5 px-3 h-8 rounded-lg hover:bg-red-500/10 transition-colors"
                  style={{ fontSize: 12.5, color: '#EF4444' }}
                  onClick={() => { setAvatarOpen(false); toast('Signed out of OrchestrAI (demo mode)', 'info') }}>
                  <LogOut size={14} /> Sign Out
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
