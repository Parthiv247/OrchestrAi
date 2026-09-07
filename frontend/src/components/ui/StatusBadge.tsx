type Status =
  | 'healthy' | 'success' | 'approved'
  | 'failed' | 'error' | 'anomaly' | 'rejected'
  | 'warning'
  | 'pending'
  | 'running'
  | 'idle' | 'inactive' | 'paused'
  | string

interface BadgeStyle {
  bg: string
  text: string
  dot: string
  /** CSS class applied to the dot: pulse-green | pulse-amber | pulse-blue | spin | '' */
  dotClass: string
}

const EMERALD: BadgeStyle = { bg: 'rgba(16,185,129,0.10)',  text: '#34D399', dot: '#10B981', dotClass: 'pulse-green' }
const RED: BadgeStyle     = { bg: 'rgba(239,68,68,0.10)',   text: '#F87171', dot: '#EF4444', dotClass: '' }
const AMBER: BadgeStyle   = { bg: 'rgba(245,158,11,0.10)',  text: '#FBBF24', dot: '#F59E0B', dotClass: 'pulse-amber' }
const BLUE: BadgeStyle    = { bg: 'rgba(59,130,246,0.10)',  text: '#60A5FA', dot: '#3B82F6', dotClass: 'pulse-blue' }
const SKY: BadgeStyle     = { bg: 'rgba(14,165,233,0.10)',  text: '#38BDF8', dot: '#0EA5E9', dotClass: 'spin' }
const GRAY: BadgeStyle    = { bg: 'rgba(100,116,139,0.10)', text: '#94A3B8', dot: '#64748B', dotClass: '' }

const CONFIG: Record<string, BadgeStyle> = {
  healthy: EMERALD,
  success: EMERALD,
  approved: EMERALD,
  failed: RED,
  error: RED,
  anomaly: RED,
  rejected: RED,
  warning: AMBER,
  pending: BLUE,
  running: SKY,
  idle: GRAY,
  inactive: GRAY,
  paused: GRAY,
}

export function StatusBadge({ status }: { status: Status }) {
  const key = (status ?? '').toLowerCase()
  const c = CONFIG[key] ?? GRAY
  const label = status ? status.charAt(0).toUpperCase() + status.slice(1) : 'Unknown'

  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full"
      style={{
        background: c.bg,
        color: c.text,
        padding: '2px 10px',
        fontSize: 11,
        fontWeight: 600,
        letterSpacing: '0.01em',
        whiteSpace: 'nowrap',
      }}>
      {c.dotClass === 'spin' ? (
        <span
          className="inline-block rounded-full animate-spin flex-shrink-0"
          style={{
            width: 8,
            height: 8,
            border: `1.5px solid ${c.dot}`,
            borderTopColor: 'transparent',
          }}
        />
      ) : (
        <span
          className={`status-dot flex-shrink-0 ${c.dotClass}`}
          style={{ background: c.dot, width: 7, height: 7 }}
        />
      )}
      {label}
    </span>
  )
}
