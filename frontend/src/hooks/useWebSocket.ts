'use client'
import { useEffect, useRef, useCallback, useState } from 'react'

export type WSEvent =
  | { type: 'connected'; data: { message: string; ts: string } }
  | { type: 'ping'; data: { ts: string } }
  | { type: 'pipeline_status'; data: { pipeline_id: string; status: string; [key: string]: string | number | boolean | null | undefined } }
  | { type: 'incident_update'; data: { incident_id: string; status: string; [key: string]: string | number | boolean | null | undefined } }
  | { type: string; data: Record<string, unknown> }

type WSStatus = 'connecting' | 'connected' | 'disconnected' | 'error'

interface UseWebSocketOptions {
  /** Called on every event received from the server */
  onEvent?: (event: WSEvent) => void
  /** Auto-reconnect delay in ms (default 3000). Set 0 to disable. */
  reconnectDelay?: number
}

/**
 * useWebSocket — connects to OrchestrAI real-time feed at /ws.
 *
 * Handles:
 *  - Auto-reconnect with exponential back-off (max 30 s)
 *  - Pong response to server pings
 *  - Cleanup on unmount
 */
export function useWebSocket(options: UseWebSocketOptions = {}) {
  const { onEvent, reconnectDelay = 3000 } = options
  const [status, setStatus] = useState<WSStatus>('connecting')
  const [lastEvent, setLastEvent] = useState<WSEvent | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const retryCount = useRef(0)
  const retryTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const mountedRef = useRef(true)

  const getWsUrl = () => {
    const base = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000')
      .replace(/^http/, 'ws')
    return `${base}/ws`
  }

  const connect = useCallback(() => {
    if (!mountedRef.current) return
    try {
      const ws = new WebSocket(getWsUrl())
      wsRef.current = ws
      setStatus('connecting')

      ws.onopen = () => {
        if (!mountedRef.current) return
        retryCount.current = 0
        setStatus('connected')
      }

      ws.onmessage = (e) => {
        if (!mountedRef.current) return
        try {
          const event: WSEvent = JSON.parse(e.data)
          setLastEvent(event)
          onEvent?.(event)
          // Respond to pings
          if (event.type === 'ping') {
            ws.send(JSON.stringify({ type: 'pong' }))
          }
        } catch {
          // ignore parse errors
        }
      }

      ws.onerror = () => {
        if (!mountedRef.current) return
        setStatus('error')
      }

      ws.onclose = () => {
        if (!mountedRef.current) return
        setStatus('disconnected')
        wsRef.current = null
        if (reconnectDelay > 0) {
          const delay = Math.min(reconnectDelay * Math.pow(1.5, retryCount.current), 30000)
          retryCount.current += 1
          retryTimer.current = setTimeout(connect, delay)
        }
      }
    } catch {
      setStatus('error')
    }
  }, [onEvent, reconnectDelay])

  useEffect(() => {
    mountedRef.current = true
    connect()
    return () => {
      mountedRef.current = false
      if (retryTimer.current) clearTimeout(retryTimer.current)
      wsRef.current?.close()
    }
  }, [connect])

  const send = useCallback((data: object) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data))
    }
  }, [])

  return { status, lastEvent, send }
}
