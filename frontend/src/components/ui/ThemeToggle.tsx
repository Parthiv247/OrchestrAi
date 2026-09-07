'use client'

import { Sun, Moon } from 'lucide-react'
import { useTheme } from '@/lib/theme'

export function ThemeToggle() {
  const { theme, toggleTheme, isDark } = useTheme()
  return (
    <button
      onClick={toggleTheme}
      aria-label={`Switch to ${isDark ? 'light' : 'dark'} mode`}
      title={`Switch to ${isDark ? 'light' : 'dark'} mode`}
      className="flex items-center justify-center w-8 h-8 rounded-lg transition-colors hover:bg-white/5"
      style={{ color: isDark ? '#64748B' : '#64748B' }}>
      {isDark
        ? <Sun size={15} style={{ color: '#F59E0B' }} />
        : <Moon size={15} style={{ color: '#7C3AED' }} />}
    </button>
  )
}
