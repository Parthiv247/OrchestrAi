'use client'
import { createContext, useContext, useState, useCallback, ReactNode } from 'react'
import React from 'react'
import { CheckCircle, XCircle, Info, X } from 'lucide-react'

type ToastType = 'success' | 'error' | 'info'
interface Toast { id: number; message: string; type: ToastType }

const ToastCtx = createContext<(msg: string, type?: ToastType) => void>(() => {})
export const useToast = () => useContext(ToastCtx)

const iconMap = {
  success: CheckCircle,
  error: XCircle,
  info: Info,
}
const styleMap: Record<ToastType, React.CSSProperties> = {
  success: { color: '#86EFAC', borderColor: 'rgba(34,197,94,0.4)', background: 'rgba(34,197,94,0.12)' },
  error:   { color: '#FCA5A5', borderColor: 'rgba(239,68,68,0.4)',  background: 'rgba(239,68,68,0.12)' },
  info:    { color: '#93C5FD', borderColor: 'rgba(59,130,246,0.4)', background: 'rgba(59,130,246,0.12)' },
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])

  const show = useCallback((message: string, type: ToastType = 'success') => {
    const id = Date.now()
    setToasts(t => [...t, { id, message, type }])
    setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 4000)
  }, [])

  const dismiss = (id: number) => setToasts(t => t.filter(x => x.id !== id))

  return (
    <ToastCtx.Provider value={show}>
      {children}
      <div className="fixed bottom-6 right-6 z-[200] flex flex-col gap-2 pointer-events-none">
        {toasts.map(t => {
          const Icon = iconMap[t.type]
          return (
            <div key={t.id}
              className="flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium shadow-2xl border backdrop-blur-sm pointer-events-auto transition-all duration-300"
              style={{ minWidth: 260, ...styleMap[t.type] }}>
              <Icon size={16} className="flex-shrink-0" />
              <span className="flex-1">{t.message}</span>
              <button onClick={() => dismiss(t.id)} className="opacity-60 hover:opacity-100 transition-opacity">
                <X size={14} />
              </button>
            </div>
          )
        })}
      </div>
    </ToastCtx.Provider>
  )
}
