'use client'

import React from 'react'
import { AlertTriangle, RefreshCw, Home } from 'lucide-react'

interface State { hasError: boolean; error?: Error }

export class ErrorBoundary extends React.Component<{ children: React.ReactNode }, State> {
  constructor(props: { children: React.ReactNode }) {
    super(props)
    this.state = { hasError: false }
  }
  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }
  render() {
    if (!this.state.hasError) return this.props.children
    return (
      <div
        className="flex flex-col items-center justify-center min-h-[400px] text-center p-12"
        role="alert"
        aria-live="assertive">
        
        {/* Dramatic error icon */}
        <div className="relative mb-6">
          <div style={{
            width: 72, height: 72, borderRadius: 20,
            background: 'rgba(239,68,68,0.08)',
            border: '1px solid rgba(239,68,68,0.2)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <AlertTriangle size={32} style={{ color: '#EF4444' }} />
          </div>
          <div className="absolute inset-0 pointer-events-none" style={{
            borderRadius: 20,
            boxShadow: '0 0 40px rgba(239,68,68,0.12)',
          }} />
        </div>

        <h2 style={{ fontSize: 18, fontWeight: 700, color: '#F1F5F9', marginBottom: 8 }}>
          Something went wrong
        </h2>
        <p style={{ fontSize: 13, color: '#64748B', maxWidth: 320, lineHeight: 1.7, marginBottom: 8 }}>
          An unexpected error occurred in this component. The error has been captured.
        </p>
        {this.state.error && (
          <code style={{
            display: 'block', fontSize: 11, color: '#EF4444',
            background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.15)',
            borderRadius: 8, padding: '8px 14px', maxWidth: 400, marginBottom: 24,
            fontFamily: 'monospace', wordBreak: 'break-all',
          }}>
            {this.state.error.message}
          </code>
        )}

        <div className="flex items-center gap-3">
          <button
            onClick={() => this.setState({ hasError: false })}
            className="flex items-center gap-2 px-4 h-9 rounded-lg text-[13px] font-semibold transition-all hover:opacity-90"
            style={{ background: 'rgba(14,165,233,0.12)', color: '#0EA5E9', border: '1px solid rgba(14,165,233,0.25)' }}>
            <RefreshCw size={13} /> Try again
          </button>
          <button
            onClick={() => window.location.href = '/'}
            className="flex items-center gap-2 px-4 h-9 rounded-lg text-[13px] font-semibold transition-all hover:opacity-90"
            style={{ background: 'rgba(255,255,255,0.04)', color: '#94A3B8', border: '1px solid #1A3A5C' }}>
            <Home size={13} /> Go home
          </button>
        </div>
      </div>
    )
  }
}

export default ErrorBoundary
