'use client'
import { motion } from 'framer-motion'
import type { LucideIcon } from 'lucide-react'

type Color = 'blue' | 'green' | 'violet' | 'amber' | 'red'

const COLOR_MAP: Record<Color, { hex: string; pulse: string }> = {
  blue:   { hex: '#0EA5E9', pulse: 'pulse-blue' },
  green:  { hex: '#10B981', pulse: 'pulse-green' },
  violet: { hex: '#7C3AED', pulse: 'pulse-blue' },
  amber:  { hex: '#F59E0B', pulse: 'pulse-amber' },
  red:    { hex: '#EF4444', pulse: 'pulse-amber' },
}

interface StatCardProps {
  title: string
  value: string | number
  unit?: string
  sub?: string
  delta?: { value: string; positive?: boolean }
  icon: LucideIcon
  color?: Color
  delay?: number
  live?: boolean     // shows pulsing dot
  onClick?: () => void
}

export function StatCard({
  title, value, unit, sub, delta, icon: Icon,
  color = 'blue', delay = 0, live, onClick,
}: StatCardProps) {
  const c = COLOR_MAP[color]
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay, ease: [0.25, 0.46, 0.45, 0.94] }}
      onClick={onClick}
      style={{
        position: 'relative', overflow: 'hidden',
        background: 'var(--card-bg)', border: '1px solid var(--border)',
        borderRadius: 16, padding: '22px 24px',
        cursor: onClick ? 'pointer' : 'default',
        transition: 'all 0.25s ease',
      }}
      whileHover={onClick ? { y: -3, boxShadow: `0 12px 40px rgba(0,0,0,0.25), 0 0 0 1px ${c.hex}30` } : { y: -2 }}
    >
      {/* Top accent line */}
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, height: 2, borderRadius: '16px 16px 0 0',
        background: `linear-gradient(90deg, ${c.hex}, ${c.hex}55)`,
      }} />

      {/* Header row */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
          <span style={{
            fontSize: 10.5, fontWeight: 700, letterSpacing: '0.09em',
            textTransform: 'uppercase', color: 'var(--text-label)',
          }}>
            {title}
          </span>
          {live && (
            <span style={{
              display: 'inline-block', width: 6, height: 6, borderRadius: '50%',
              background: c.hex, animation: `${c.pulse} 2s infinite`,
            }} />
          )}
        </div>
        <div style={{
          width: 32, height: 32, borderRadius: 9, display: 'flex',
          alignItems: 'center', justifyContent: 'center',
          background: `${c.hex}15`, border: `1px solid ${c.hex}25`,
        }}>
          <Icon size={15} style={{ color: c.hex }} />
        </div>
      </div>

      {/* Value */}
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 5, marginBottom: sub ? 6 : 0 }}>
        <span style={{
          fontSize: 30, fontWeight: 800, letterSpacing: '-0.04em',
          color: 'var(--text-primary)', lineHeight: 1,
        }}>
          {value}
        </span>
        {unit && <span style={{ fontSize: 13, color: 'var(--text-muted)', fontWeight: 500 }}>{unit}</span>}
        {delta && (
          <span style={{
            fontSize: 11, fontWeight: 700, marginLeft: 4,
            color: delta.positive !== false ? '#10B981' : '#EF4444',
          }}>
            {delta.positive !== false ? '↑' : '↓'} {delta.value}
          </span>
        )}
      </div>

      {sub && (
        <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: 0, lineHeight: 1.4 }}>{sub}</p>
      )}

      {/* Background glow */}
      <div style={{
        position: 'absolute', right: -20, bottom: -20, width: 80, height: 80,
        borderRadius: '50%', background: `${c.hex}08`, pointerEvents: 'none',
      }} />
    </motion.div>
  )
}
