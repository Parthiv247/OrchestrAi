'use client'

import React, { createContext, useContext, useEffect, useState } from 'react'

type Theme = 'dark' | 'light'

interface ThemeContextValue {
  theme: Theme
  toggleTheme: () => void
  isDark: boolean
}

const ThemeContext = createContext<ThemeContextValue>({
  theme: 'dark',
  toggleTheme: () => {},
  isDark: true,
})

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setTheme] = useState<Theme>('dark')

  useEffect(() => {
    try {
      const saved = localStorage.getItem('orchestrai-theme') as Theme | null
      if (saved === 'light' || saved === 'dark') {
        setTheme(saved)
        document.documentElement.setAttribute('data-theme', saved)
      }
    } catch {}
  }, [])

  const toggleTheme = () => {
    const next: Theme = theme === 'dark' ? 'light' : 'dark'
    setTheme(next)
    document.documentElement.setAttribute('data-theme', next)
    try { localStorage.setItem('orchestrai-theme', next) } catch {}
  }

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
  }, [theme])

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme, isDark: theme === 'dark' }}>
      {children}
    </ThemeContext.Provider>
  )
}

export const useTheme = () => useContext(ThemeContext)

// ── Design tokens per theme ─────────────────────────────────────────────────
export function useTokens() {
  const { isDark } = useTheme()
  return isDark ? DARK : LIGHT
}

const DARK = {
  bodyBg:      '#080F1C',
  sidebarBg:   '#09111E',
  cardBg:      '#0F2540',
  cardElevated:'#112B47',
  border:      '#1A3A5C',
  borderLight: '#0F2A48',
  textPrimary: '#F1F5F9',
  textSecondary:'#94A3B8',
  textMuted:   '#64748B',
  textLabel:   '#4B6B8E',
  accent:      '#0EA5E9',
  violet:      '#7C3AED',
  emerald:     '#10B981',
  amber:       '#F59E0B',
  red:         '#EF4444',
  topbarBg:    'rgba(8,15,28,0.85)',
  inputBg:     'rgba(15,37,64,0.6)',
  // Chart colors
  chartGrid:   '#1A3A5C',
  tooltipBg:   '#112B47',
}

const LIGHT = {
  bodyBg:      '#F0F4F8',
  sidebarBg:   '#FFFFFF',
  cardBg:      '#FFFFFF',
  cardElevated:'#F8FAFC',
  border:      '#E2E8F0',
  borderLight: '#EDF2F7',
  textPrimary: '#0F172A',
  textSecondary:'#475569',
  textMuted:   '#94A3B8',
  textLabel:   '#64748B',
  accent:      '#0284C7',
  violet:      '#6D28D9',
  emerald:     '#059669',
  amber:       '#D97706',
  red:         '#DC2626',
  topbarBg:    'rgba(255,255,255,0.92)',
  inputBg:     'rgba(248,250,252,0.9)',
  // Chart colors
  chartGrid:   '#E2E8F0',
  tooltipBg:   '#FFFFFF',
}
