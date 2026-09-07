'use client'

interface SkeletonProps {
  className?: string
  width?: string | number
  height?: string | number
  rounded?: boolean
  circle?: boolean
  style?: React.CSSProperties
}

export function Skeleton({ className = '', width, height, rounded = false, circle = false, style }: SkeletonProps) {
  return (
    <div
      className={`shimmer ${circle ? 'rounded-full' : rounded ? 'rounded-full' : 'rounded-lg'} ${className}`}
      style={{ width, height: height ?? '1rem', flexShrink: 0, ...style }}
    />
  )
}

export function SkeletonMetricCard() {
  return (
    <div className="metric-hero p-6" style={{ opacity: 0.6 }}>
      <div className="flex items-start justify-between mb-4">
        <Skeleton width={36} height={36} circle />
        <Skeleton width={52} height={20} />
      </div>
      <Skeleton height={36} className="mb-2" style={{ width: '50%' }} />
      <Skeleton height={13} style={{ width: '70%' }} />
    </div>
  )
}

export function SkeletonTableRow({ cols = 5 }: { cols?: number }) {
  return (
    <tr>
      {Array.from({ length: cols }).map((_, i) => (
        <td key={i} className="px-4 py-3">
          <Skeleton height={13} style={{ width: i === 0 ? '70%' : '50%' }} />
        </td>
      ))}
    </tr>
  )
}

export function SkeletonTable({ rows = 5, cols = 5 }: { rows?: number; cols?: number }) {
  return (
    <div className="card overflow-hidden" style={{ opacity: 0.7 }}>
      <div className="flex items-center gap-3 px-4 py-3 border-b" style={{ borderColor: 'var(--border)' }}>
        <Skeleton height={13} style={{ width: 128 }} />
        <div className="ml-auto">
          <Skeleton height={32} style={{ width: 96 }} />
        </div>
      </div>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            {Array.from({ length: cols }).map((_, i) => (
              <th key={i} style={{ padding: '10px 16px' }}>
                <Skeleton height={11} style={{ width: i === 0 ? 96 : 64 }} />
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {Array.from({ length: rows }).map((_, i) => (
            <SkeletonTableRow key={i} cols={cols} />
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function SkeletonCard({ lines = 3 }: { lines?: number }) {
  return (
    <div className="card p-5" style={{ opacity: 0.7 }}>
      <div className="flex items-center gap-3 mb-4">
        <Skeleton width={32} height={32} circle />
        <div style={{ flex: 1 }}>
          <Skeleton height={14} className="mb-2" style={{ width: '55%' }} />
          <Skeleton height={11} style={{ width: '75%' }} />
        </div>
      </div>
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton key={i} height={12} className="mb-2" style={{ width: i === lines - 1 ? '60%' : '100%' }} />
      ))}
    </div>
  )
}

export function SkeletonList({ items = 4 }: { items?: number }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {Array.from({ length: items }).map((_, i) => (
        <div key={i} className="card p-4" style={{ display: 'flex', alignItems: 'center', gap: 16, opacity: 0.7 }}>
          <Skeleton width={40} height={40} circle />
          <div style={{ flex: 1 }}>
            <Skeleton height={14} className="mb-2" style={{ width: '60%' }} />
            <Skeleton height={11} style={{ width: '45%' }} />
          </div>
          <Skeleton height={24} style={{ width: 80 }} />
        </div>
      ))}
    </div>
  )
}
