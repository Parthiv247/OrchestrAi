'use client'

import { AlertCircle, RefreshCw } from 'lucide-react'
import { motion } from 'framer-motion'

interface ApiErrorStateProps {
  title?: string
  message?: string
  onRetry?: () => void
}

export function ApiErrorState({ 
  title = 'Failed to load data',
  message = 'There was a problem connecting to the server. Check your connection and try again.',
  onRetry,
}: ApiErrorStateProps) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="flex flex-col items-center justify-center text-center p-10"
      role="alert">
      
      <div style={{
        width: 56, height: 56, borderRadius: 16,
        background: 'rgba(239,68,68,0.08)',
        border: '1px solid rgba(239,68,68,0.2)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        marginBottom: 16,
      }}>
        <AlertCircle size={24} style={{ color: '#EF4444' }} />
      </div>

      <p style={{ fontSize: 15, fontWeight: 600, color: '#F1F5F9', marginBottom: 6 }}>{title}</p>
      <p style={{ fontSize: 13, color: '#64748B', maxWidth: 300, lineHeight: 1.6, marginBottom: 20 }}>{message}</p>

      {onRetry && (
        <button
          onClick={onRetry}
          className="flex items-center gap-2 px-4 h-8 rounded-lg text-[12px] font-semibold transition-all hover:opacity-90 active:scale-95"
          style={{ background: 'rgba(239,68,68,0.1)', color: '#EF4444', border: '1px solid rgba(239,68,68,0.2)' }}>
          <RefreshCw size={12} />
          Try again
        </button>
      )}
    </motion.div>
  )
}
