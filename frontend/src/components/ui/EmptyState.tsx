'use client'

import type { LucideIcon } from 'lucide-react'

interface EmptyStateProps {
  icon: LucideIcon
  title: string
  description: string
  action?: {
    label: string
    onClick: () => void
  }
  secondaryAction?: {
    label: string
    onClick: () => void
  }
  size?: 'sm' | 'md' | 'lg'
  accent?: 'blue' | 'violet' | 'emerald' | 'amber'
}

const ACCENT_COLORS = {
  blue:    { base: '#0EA5E9', bg: 'rgba(14,165,233,0.06)',   border: 'rgba(14,165,233,0.15)',   glow: 'rgba(14,165,233,0.1)'  },
  violet:  { base: '#7C3AED', bg: 'rgba(124,58,237,0.06)',  border: 'rgba(124,58,237,0.15)',  glow: 'rgba(124,58,237,0.1)' },
  emerald: { base: '#10B981', bg: 'rgba(16,185,129,0.06)',  border: 'rgba(16,185,129,0.15)',  glow: 'rgba(16,185,129,0.1)' },
  amber:   { base: '#F59E0B', bg: 'rgba(245,158,11,0.06)',  border: 'rgba(245,158,11,0.15)',  glow: 'rgba(245,158,11,0.1)' },
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  secondaryAction,
  size = 'md',
  accent = 'blue',
}: EmptyStateProps) {
  const sizes = {
    sm: { iconBox: 48, icon: 20, title: 14, desc: 12.5, padding: '24px 16px' },
    md: { iconBox: 68, icon: 28, title: 15,  desc: 13,   padding: '48px 24px' },
    lg: { iconBox: 88, icon: 36, title: 17,  desc: 14,   padding: '64px 24px' },
  }
  const s = sizes[size]
  const c = ACCENT_COLORS[accent]

  return (
    <div
      className="animate-fade-in flex flex-col items-center justify-center text-center"
      style={{ padding: s.padding }}
      role="status"
      aria-label={title}
    >
      {/* Layered icon with glow */}
      <div className="relative mb-5 animate-float" style={{ animationDuration: '4s' }}>
        {/* outer ring */}
        <div style={{
          position: 'absolute',
          inset: -10,
          borderRadius: s.iconBox / 2.5 + 10,
          background: `radial-gradient(circle, ${c.glow}, transparent 70%)`,
          pointerEvents: 'none',
        }} />
        {/* icon box */}
        <div style={{
          width: s.iconBox,
          height: s.iconBox,
          borderRadius: s.iconBox / 3,
          background: c.bg,
          border: `1.5px solid ${c.border}`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          boxShadow: `0 8px 32px ${c.glow}`,
          position: 'relative',
          zIndex: 1,
        }}>
          <Icon size={s.icon} style={{ color: c.base }} />
        </div>
      </div>

      {/* Text */}
      <p style={{ fontSize: s.title, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 8 }}>
        {title}
      </p>
      <p style={{ fontSize: s.desc, color: 'var(--text-muted)', maxWidth: 300, lineHeight: 1.65 }}>
        {description}
      </p>

      {/* Actions */}
      {(action || secondaryAction) && (
        <div style={{ display: 'flex', gap: 10, marginTop: 24, flexWrap: 'wrap', justifyContent: 'center' }}>
          {action && (
            <button
              onClick={action.onClick}
              className="btn-primary"
              style={{ fontSize: 13, padding: '8px 20px' }}
            >
              {action.label}
            </button>
          )}
          {secondaryAction && (
            <button
              onClick={secondaryAction.onClick}
              className="btn-ghost"
              style={{ fontSize: 13, padding: '8px 20px' }}
            >
              {secondaryAction.label}
            </button>
          )}
        </div>
      )}
    </div>
  )
}
