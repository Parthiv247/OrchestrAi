'use client'
import { motion } from 'framer-motion'
import Link from 'next/link'
import { ChevronRight } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

interface Crumb { label: string; href?: string }

interface PageHeaderProps {
  title: string
  subtitle?: string
  icon?: LucideIcon
  iconColor?: string
  breadcrumbs?: Crumb[]
  actions?: React.ReactNode
  badge?: { label: string; color?: 'blue' | 'green' | 'amber' | 'red' | 'violet' }
  meta?: string
}

const BADGE_COLORS = {
  blue:   { bg: 'rgba(14,165,233,0.12)',  border: 'rgba(14,165,233,0.3)',  text: '#0EA5E9' },
  green:  { bg: 'rgba(16,185,129,0.12)',  border: 'rgba(16,185,129,0.3)',  text: '#10B981' },
  amber:  { bg: 'rgba(245,158,11,0.12)',  border: 'rgba(245,158,11,0.3)',  text: '#F59E0B' },
  red:    { bg: 'rgba(239,68,68,0.12)',   border: 'rgba(239,68,68,0.3)',   text: '#EF4444' },
  violet: { bg: 'rgba(124,58,237,0.12)',  border: 'rgba(124,58,237,0.3)',  text: '#7C3AED' },
}

export function PageHeader({
  title, subtitle, icon: Icon, iconColor = '#0EA5E9',
  breadcrumbs, actions, badge, meta,
}: PageHeaderProps) {
  const badgeStyle = badge ? BADGE_COLORS[badge.color ?? 'blue'] : null

  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: [0.25, 0.46, 0.45, 0.94] }}
      style={{ marginBottom: 28 }}
    >
      {/* Breadcrumbs */}
      {breadcrumbs && breadcrumbs.length > 0 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginBottom: 10 }}>
          {breadcrumbs.map((crumb, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              {i > 0 && <ChevronRight size={12} style={{ color: 'var(--text-label)' }} />}
              {crumb.href ? (
                <Link href={crumb.href} style={{
                  fontSize: 12, color: 'var(--text-muted)', textDecoration: 'none',
                  transition: 'color 0.15s',
                }}
                  onMouseEnter={e => (e.currentTarget.style.color = 'var(--accent)')}
                  onMouseLeave={e => (e.currentTarget.style.color = 'var(--text-muted)')}
                >
                  {crumb.label}
                </Link>
              ) : (
                <span style={{ fontSize: 12, color: 'var(--text-label)' }}>{crumb.label}</span>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Main header row */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16 }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 14 }}>
          {Icon && (
            <div style={{
              width: 44, height: 44, borderRadius: 12, flexShrink: 0, marginTop: 2,
              background: `${iconColor}18`,
              border: `1px solid ${iconColor}30`,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <Icon size={20} style={{ color: iconColor }} />
            </div>
          )}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
              <h1 style={{
                fontSize: 22, fontWeight: 700, letterSpacing: '-0.02em',
                color: 'var(--text-primary)', margin: 0, lineHeight: 1.2,
              }}>
                {title}
              </h1>
              {badge && badgeStyle && (
                <span style={{
                  fontSize: 11, fontWeight: 600, padding: '3px 10px', borderRadius: 20,
                  background: badgeStyle.bg, border: `1px solid ${badgeStyle.border}`,
                  color: badgeStyle.text, letterSpacing: '0.04em',
                }}>
                  {badge.label}
                </span>
              )}
            </div>
            {subtitle && (
              <p style={{ fontSize: 13, color: 'var(--text-muted)', margin: '4px 0 0', lineHeight: 1.5 }}>
                {subtitle}
              </p>
            )}
            {meta && (
              <p style={{ fontSize: 11, color: 'var(--text-label)', margin: '3px 0 0', letterSpacing: '0.03em' }}>
                {meta}
              </p>
            )}
          </div>
        </div>
        {actions && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0, marginTop: 2 }}>
            {actions}
          </div>
        )}
      </div>

      {/* Divider */}
      <div style={{
        height: 1, marginTop: 20,
        background: 'linear-gradient(90deg, var(--border) 0%, transparent 80%)',
      }} />
    </motion.div>
  )
}
