/**
 * Shimmer-based loading skeletons.
 * The `.shimmer` class (globals.css) sweeps a #1A3A5C → #1E4468 gradient
 * left-to-right over a #0F2540 base.
 */

interface SkeletonLineProps {
  width?: string | number
  height?: string | number
  className?: string
  radius?: number
}

export function SkeletonLine({ width = '100%', height = 12, className = '', radius = 6 }: SkeletonLineProps) {
  return (
    <div
      className={`shimmer ${className}`}
      style={{ width, height, borderRadius: radius }}
    />
  )
}

/** Backwards-compatible multi-line skeleton (used across pages) */
export function LoadingSkeleton({ rows = 3, className = '' }: { rows?: number; className?: string }) {
  return (
    <div className={`space-y-3 ${className}`}>
      {Array.from({ length: rows }).map((_, i) => (
        <SkeletonLine key={i} height={14} width={`${70 + (i % 3) * 10}%`} />
      ))}
    </div>
  )
}

/** Full card placeholder */
export function SkeletonCard({ className = '' }: { className?: string }) {
  return (
    <div className={`card p-5 ${className}`}>
      <div className="flex items-start justify-between mb-4">
        <SkeletonLine width={110} height={11} />
        <SkeletonLine width={32} height={32} radius={9} />
      </div>
      <SkeletonLine width={140} height={26} className="mb-3" radius={7} />
      <SkeletonLine width="80%" height={11} className="mb-2" />
      <SkeletonLine width="55%" height={11} />
    </div>
  )
}

/** Metric card placeholder (matches MetricCard layout) */
export function SkeletonMetric({ className = '' }: { className?: string }) {
  return (
    <div className={`card ${className}`} style={{ padding: 20 }}>
      <div className="flex items-start justify-between">
        <SkeletonLine width={96} height={10} />
        <SkeletonLine width={32} height={32} radius={9} />
      </div>
      <SkeletonLine width={120} height={30} className="mt-2 mb-2" radius={7} />
      <SkeletonLine width={80} height={10} />
    </div>
  )
}

/** Table placeholder with shimmering rows */
export function SkeletonTable({ rows = 5, className = '' }: { rows?: number; className?: string }) {
  return (
    <div className={`card overflow-hidden ${className}`}>
      {/* Header */}
      <div className="flex items-center gap-6 px-4" style={{ height: 40, borderBottom: '1px solid #1A3A5C' }}>
        <SkeletonLine width="18%" height={9} />
        <SkeletonLine width="26%" height={9} />
        <SkeletonLine width="14%" height={9} />
        <SkeletonLine width="20%" height={9} />
      </div>
      {/* Rows */}
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="flex items-center gap-6 px-4"
          style={{ height: 46, borderBottom: i === rows - 1 ? 'none' : '1px solid #0F2A48' }}>
          <SkeletonLine width="18%" height={12} />
          <SkeletonLine width="30%" height={12} />
          <SkeletonLine width={64} height={18} radius={9} />
          <SkeletonLine width="16%" height={12} />
        </div>
      ))}
    </div>
  )
}

/** Full page loading state: 4 metric cards + table */
export function PageSkeleton() {
  return (
    <div className="page-container space-y-5">
      <div className="space-y-2">
        <SkeletonLine width={200} height={22} radius={7} />
        <SkeletonLine width={320} height={12} />
      </div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <SkeletonMetric />
        <SkeletonMetric />
        <SkeletonMetric />
        <SkeletonMetric />
      </div>
      <SkeletonTable rows={6} />
    </div>
  )
}

/** Backwards-compatible alias — several pages import CardSkeleton */
export function CardSkeleton({ className = '' }: { className?: string }) {
  return <SkeletonMetric className={className} />
}
