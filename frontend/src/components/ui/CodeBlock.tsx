'use client'
import { useState } from 'react'
import { Copy, Check, ChevronDown, ChevronUp } from 'lucide-react'

interface CodeBlockProps {
  code: string
  language?: string
  maxLines?: number
}

export function CodeBlock({ code, language = 'python', maxLines = 20 }: CodeBlockProps) {
  const [copied, setCopied] = useState(false)
  const [expanded, setExpanded] = useState(false)

  const lines = (code || '').split('\n')
  const visible = expanded ? lines : lines.slice(0, maxLines)
  const hasMore = lines.length > maxLines

  const copy = () => {
    navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="rounded-lg overflow-hidden" style={{ background: 'rgba(0,0,0,0.4)', border: '1px solid hsl(var(--border))' }}>
      <div className="flex items-center justify-between px-4 py-2" style={{ borderBottom: '1px solid hsl(var(--border))' }}>
        <span className="text-xs font-mono px-2 py-0.5 rounded"
          style={{ background: 'hsl(var(--muted))', color: 'hsl(var(--muted-foreground))' }}>
          {language}
        </span>
        <button onClick={copy}
          className="flex items-center gap-1.5 text-xs px-2 py-1 rounded hover:bg-white/5 transition-colors"
          style={{ color: 'hsl(var(--muted-foreground))' }}>
          {copied ? <><Check size={12} style={{ color: '#4ADE80' }} /> Copied</> : <><Copy size={12} /> Copy</>}
        </button>
      </div>
      <pre className="p-4 text-sm font-mono overflow-x-auto leading-relaxed"
        style={{ color: '#e2e8f0' }}>
        <code>{visible.map((line, i) => (
          <span key={i} className="block">
            <span className="select-none mr-4 text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>
              {String(i + 1).padStart(3, ' ')}
            </span>
            {line}
          </span>
        ))}</code>
      </pre>
      {hasMore && (
        <button onClick={() => setExpanded(!expanded)}
          className="w-full flex items-center justify-center gap-1 py-2 text-xs hover:bg-white/5 transition-colors"
          style={{ color: 'hsl(var(--muted-foreground))', borderTop: '1px solid hsl(var(--border))' }}>
          {expanded ? <><ChevronUp size={12} /> Show less</> : <><ChevronDown size={12} /> Show {lines.length - maxLines} more lines</>}
        </button>
      )}
    </div>
  )
}
