'use client'

import { useEffect, useRef, useState, type ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'
import { TrendingUp, TrendingDown } from 'lucide-react'
import { Area, AreaChart } from 'recharts'

type MetricColor = 'blue' | 'green' | 'amber' | 'purple' | 'red'

interface MetricCardProps {
  title: string
  value: string | number
  subtitle?: string
  icon: LucideIcon
  color?: MetricColor
  trend?: number
  /** Optional tiny inline sparkline (recent series values) */
  sparkline?: number[]
  children?: ReactNode
}

const COLOR_MAP: Record<MetricColor, { hex: string; bg: string; ring: string }> = {
  blue:   { hex: '#0EA5E9', bg: 'rgba(14,165,233,0.12)',  ring: 'rgba(14,165,233,0.25)' },
  green:  { hex: '#10B981', bg: 'rgba(16,185,129,0.12)',  ring: 'rgba(16,185,129,0.25)' },
  amber:  { hex: '#F59E0B', bg: 'rgba(245,158,11,0.12)',  ring: 'rgba(245,158,11,0.25)' },
  purple: { hex: '#7C3AED', bg: 'rgba(124,58,237,0.12)',  ring: 'rgba(124,58,237,0.25)' },
  red:    { hex: '#EF4444', bg: 'rgba(239,68,68,0.12)',   ring: 'rgba(239,68,68,0.25)' },
}

/** Ease-out count-up for purely numeric values. Strings render as-is. */
function useCountUp(target: number, durationMs = 900): number {
  const [display, setDisplay] = useState(0)
  const raf = useRef<number>(0)

  useEffect(() => {
    const start = performance.now()
    const from = 0
    const step = (now: number) => {
      const t = Math.min((now - start) / durationMs, 1)
      const eased = 1 - Math.pow(1 - t, 3)
      setDisplay(from + (target - from) * eased)
      if (t < 1) raf.current = requestAnimationFrame(step)
    }
    raf.current = requestAnimationFrame(step)
    return () => cancelAnimationFrame(raf.current)
  }, [target, durationMs])

  return display
}

function AnimatedNumber({ value }: { value: number }) {
  const animated = useCountUp(value)
  const isInt = Number.isInteger(value)
  return <>{isInt ? Math.round(animated).toLocaleString() : animated.toFixed(1)}</>
}

function Sparkline({ data, color }: { data: number[]; color: string }) {
  const points = data.map((v, i) => ({ i, v }))
  const gradId = `spark-${color.replace('#', '')}`
  return (
    <AreaChart width={60} height={26} data={points} margin={{ top: 2, right: 0, bottom: 0, left: 0 }}>
      <defs>
        <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity={0.35} />
          <stop offset="100%" stopColor={color} stopOpacity={0} />
        </linearGradient>
      </defs>
      <Area
        type="monotone"
        dataKey="v"
        stroke={color}
        strokeWidth={1.5}
        fill={`url(#${gradId})`}
        isAnimationActive={false}
        dot={false}
      />
    </AreaChart>
  )
}

export function MetricCard({
  title, value, subtitle, icon: Icon, color = 'blue', trend, sparkline, children,
}: MetricCardProps) {
  const c = COLOR_MAP[color]
  const [hovered, setHovered] = useState(false)

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      className="relative overflow-hidden cursor-default"
      style={{
        background: 'var(--card-bg)',
        border: `1px solid ${hovered ? c.ring : 'var(--border)'}`,
        borderRadius: 14,
        padding: '20px 20px 18px',
        transform: hovered ? 'translateY(-3px)' : 'translateY(0)',
        boxShadow: hovered ? `0 16px 40px rgba(0,0,0,0.35), 0 0 0 1px ${c.ring}` : '0 2px 8px rgba(0,0,0,0.12)',
        transition: 'all 0.22s cubic-bezier(0.2, 0.8, 0.2, 1)',
      }}>

      {/* Colored top accent bar */}
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, height: 2.5,
        background: `linear-gradient(90deg, ${c.hex}, ${c.hex}88)`,
        borderRadius: '14px 14px 0 0',
      }} />

      {/* Subtle gradient wash on hover */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background: `radial-gradient(480px 160px at 85% -5%, ${c.bg}, transparent 65%)`,
          opacity: hovered ? 1 : 0.4,
          transition: 'opacity 0.25s ease',
        }}
      />

      <div className="relative flex items-start justify-between">
        <p className="metric-label" style={{ color: 'var(--text-muted)' }}>{title}</p>
        <div
          className="flex items-center justify-center flex-shrink-0"
          style={{ width: 32, height: 32, borderRadius: 9, background: c.bg }}>
          <Icon size={15} style={{ color: c.hex }} />
        </div>
      </div>

      <div className="relative flex items-end justify-between gap-2 mt-1">
        <p style={{ fontSize: 28, fontWeight: 700, lineHeight: '34px', color: 'var(--text-primary)', letterSpacing: '-0.02em' }}>
          {typeof value === 'number' ? <AnimatedNumber value={value} /> : value}
        </p>
        {sparkline && sparkline.length > 1 && (
          <div className="flex-shrink-0 pb-1">
            <Sparkline data={sparkline} color={c.hex} />
          </div>
        )}
      </div>

      {(trend !== undefined || subtitle) && (
        <div className="relative flex items-center gap-2 mt-1.5">
          {trend !== undefined && (
            <span
              className="flex items-center gap-1"
              style={{ fontSize: 12, fontWeight: 600, color: trend >= 0 ? '#10B981' : '#EF4444' }}>
              {trend >= 0 ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
              {Math.abs(trend)}%
            </span>
          )}
          {subtitle && (
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{subtitle}</span>
          )}
        </div>
      )}

      {children && <div className="relative mt-2">{children}</div>}
    </div>
  )
}
