'use client'
import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import {
  Zap, Database, Layers, GitBranch, CheckCircle2,
  ChevronRight, ArrowRight, Plug, Play,
} from 'lucide-react'

const STEPS = [
  {
    id: 'welcome',
    title: 'Welcome to OrchestrAI',
    subtitle: 'Your autonomous AI platform for self-healing data pipelines',
    icon: Zap,
    color: '#0EA5E9',
    action: null,
  },
  {
    id: 'connect-source',
    title: 'Connect a Data Source',
    subtitle: 'Add your first source — PostgreSQL, S3, REST API, Google Sheets and more',
    icon: Database,
    color: '#7C3AED',
    action: { label: 'Open Connector Gallery', href: '/connectors' },
  },
  {
    id: 'connect-destination',
    title: 'Add a Destination',
    subtitle: 'Choose where your data lands — Snowflake, BigQuery, Redshift, or PostgreSQL',
    icon: Layers,
    color: '#10B981',
    action: { label: 'Add Destination', href: '/connectors' },
  },
  {
    id: 'build-pipeline',
    title: 'Build Your First Pipeline',
    subtitle: 'Connect source → destination in 5 steps with field mappings, filters, and schedule',
    icon: GitBranch,
    color: '#f59e0b',
    action: { label: 'Create Pipeline', href: '/pipelines/new' },
  },
  {
    id: 'done',
    title: "You're all set!",
    subtitle: 'OrchestrAI will monitor your pipeline, detect anomalies, and self-heal automatically',
    icon: CheckCircle2,
    color: '#10B981',
    action: { label: 'Go to Dashboard', href: '/' },
  },
]

export default function OnboardingPage() {
  const router = useRouter()
  const [step, setStep] = useState(0)
  const [completed, setCompleted] = useState<Set<number>>(new Set())

  const current = STEPS[step]
  const Icon = current.icon
  const isLast = step === STEPS.length - 1

  const advance = (href?: string) => {
    if (href && href !== '/') {
      // Mark step as in-progress and navigate
      const next = new Set(completed)
      next.add(step)
      setCompleted(next)
      router.push(href)
      return
    }
    if (isLast) {
      localStorage.setItem('onboarding_complete', 'true')
      router.push('/')
      return
    }
    const next = new Set(completed)
    next.add(step)
    setCompleted(next)
    setStep(s => s + 1)
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-6"
      style={{ background: '#0B1E35' }}>

      {/* Logo */}
      <div className="flex items-center gap-3 mb-12">
        <div className="w-10 h-10 rounded-xl flex items-center justify-center font-black text-xl text-white"
          style={{ background: 'linear-gradient(135deg, #0EA5E9, #7C3AED)' }}>O</div>
        <span className="text-xl font-bold text-white">OrchestrAI</span>
      </div>

      {/* Step dots */}
      <div className="flex items-center gap-2 mb-10">
        {STEPS.map((_, i) => (
          <button key={i} onClick={() => setStep(i)}
            className="transition-all rounded-full"
            style={{
              width: i === step ? 24 : 10,
              height: i === step ? 10 : 10,
              background: i === step ? '#3B82F6' : completed.has(i) ? '#22C55E' : '#374151',
            }}
          />
        ))}
      </div>

      {/* Card */}
      <div className="w-full max-w-md rounded-3xl p-8 text-center"
        style={{ background: 'hsl(var(--card))', border: '1px solid hsl(var(--border))' }}>

        {/* Icon */}
        <div className="w-20 h-20 rounded-3xl flex items-center justify-center mx-auto mb-6"
          style={{ background: current.color + '20' }}>
          <Icon size={40} style={{ color: current.color }} />
        </div>

        {/* Step label */}
        <p className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: current.color }}>
          Step {step + 1} of {STEPS.length}
        </p>

        <h1 className="text-2xl font-bold text-white mb-3">{current.title}</h1>
        <p className="text-sm leading-relaxed mb-8" style={{ color: 'hsl(var(--muted-foreground))' }}>
          {current.subtitle}
        </p>

        {/* Features list for welcome step */}
        {step === 0 && (
          <div className="grid grid-cols-2 gap-3 mb-8 text-left">
            {[
              { icon: Database,     label: '20+ connectors',       desc: 'Postgres, S3, Snowflake, BigQuery…' },
              { icon: GitBranch,    label: 'Visual pipeline builder', desc: '5-step wizard, no code needed' },
              { icon: Zap,          label: 'AI self-healing',       desc: 'Auto-detects and fixes anomalies' },
              { icon: CheckCircle2, label: 'Cost optimizer',        desc: 'Rewrites queries, saves money' },
            ].map(f => {
              const FIcon = f.icon
              return (
                <div key={f.label} className="p-3 rounded-xl" style={{ background: 'hsl(var(--muted))', border: '1px solid hsl(var(--border))' }}>
                  <FIcon size={14} className="mb-1.5" style={{ color: '#60A5FA' }} />
                  <p className="text-xs font-semibold text-white">{f.label}</p>
                  <p className="text-[10px] mt-0.5" style={{ color: 'hsl(var(--muted-foreground))' }}>{f.desc}</p>
                </div>
              )
            })}
          </div>
        )}

        {/* What you'll do in each step */}
        {step > 0 && step < STEPS.length - 1 && (
          <div className="mb-8 p-4 rounded-xl text-left" style={{ background: 'hsl(var(--muted))', border: '1px solid hsl(var(--border))' }}>
            <p className="text-xs font-semibold text-white mb-2">What to do:</p>
            <ol className="space-y-1.5">
              {step === 1 && [
                'Go to Connector Gallery',
                'Click a connector card (e.g. PostgreSQL)',
                'Enter credentials and save',
              ].map((s, i) => (
                <li key={i} className="flex items-center gap-2 text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>
                  <span className="w-4 h-4 rounded-full flex items-center justify-center text-[9px] font-bold flex-shrink-0"
                    style={{ background: current.color + '30', color: current.color }}>{i + 1}</span>
                  {s}
                </li>
              ))}
              {step === 2 && [
                'Click a warehouse connector (Snowflake, BigQuery, etc.)',
                'Enter destination credentials',
                'Test the connection',
              ].map((s, i) => (
                <li key={i} className="flex items-center gap-2 text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>
                  <span className="w-4 h-4 rounded-full flex items-center justify-center text-[9px] font-bold flex-shrink-0"
                    style={{ background: current.color + '30', color: current.color }}>{i + 1}</span>
                  {s}
                </li>
              ))}
              {step === 3 && [
                'Choose source connector',
                'Pick table / write SQL query',
                'Choose destination, set schedule',
                'Click Deploy Pipeline',
              ].map((s, i) => (
                <li key={i} className="flex items-center gap-2 text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>
                  <span className="w-4 h-4 rounded-full flex items-center justify-center text-[9px] font-bold flex-shrink-0"
                    style={{ background: current.color + '30', color: current.color }}>{i + 1}</span>
                  {s}
                </li>
              ))}
            </ol>
          </div>
        )}

        {/* Done step — feature highlights */}
        {step === STEPS.length - 1 && (
          <div className="mb-8 space-y-2">
            {[
              'Pipeline health monitored every 15 minutes',
              'Anomalies auto-detected via ML agents',
              'Healing fixes queued for your approval',
              'Query optimizer saving money in background',
            ].map((s, i) => (
              <div key={i} className="flex items-center gap-2 text-xs text-left p-2.5 rounded-lg"
                style={{ background: 'rgba(34,197,94,0.08)', border: '1px solid rgba(34,197,94,0.15)' }}>
                <CheckCircle2 size={12} className="flex-shrink-0" style={{ color: '#4ADE80' }} />
                <span style={{ color: 'hsl(var(--muted-foreground))' }}>{s}</span>
              </div>
            ))}
          </div>
        )}

        {/* CTA buttons */}
        <div className="space-y-3">
          {current.action ? (
            <button
              onClick={() => advance(current.action!.href)}
              className="w-full flex items-center justify-center gap-2 py-3 rounded-2xl text-sm font-semibold text-white transition-all hover:opacity-90"
              style={{ background: current.color }}>
              {current.action.label} <ArrowRight size={16} />
            </button>
          ) : (
            <button
              onClick={() => advance()}
              className="w-full flex items-center justify-center gap-2 py-3 rounded-2xl text-sm font-semibold text-white transition-all hover:opacity-90"
              style={{ background: current.color }}>
              Get Started <ChevronRight size={16} />
            </button>
          )}

          {/* Skip / Next buttons */}
          {!isLast && (
            <button
              onClick={() => setStep(s => Math.min(s + 1, STEPS.length - 1))}
              className="w-full py-2.5 rounded-2xl text-sm font-medium transition-colors hover:bg-white/5"
              style={{ color: 'hsl(var(--muted-foreground))', border: '1px solid hsl(var(--border))' }}>
              {step === 0 ? 'Skip setup — go to dashboard' : 'Skip this step →'}
            </button>
          )}
        </div>
      </div>

      {/* Already set up? */}
      <button onClick={() => router.push('/')}
        className="mt-8 text-xs hover:underline" style={{ color: 'hsl(var(--muted-foreground))' }}>
        Already set up? Go to dashboard
      </button>
    </div>
  )
}
