'use client'

export const dynamic = 'force-dynamic'
import { Inter } from 'next/font/google'
import './globals.css'
import { useState, useEffect } from 'react'
import { Providers } from './providers'
import { Sidebar } from '@/components/layout/Sidebar'
import { TopBar } from '@/components/layout/TopBar'
import { GlobalSearch } from '@/components/ui/GlobalSearch'
import { ErrorBoundary } from '@/components/ui/ErrorBoundary'
import { ThemeProvider } from '@/lib/theme'

const inter = Inter({ subsets: ['latin'] })

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)

  // Auto-collapse on medium screens (1024–1279px), hide on mobile via CSS
  useEffect(() => {
    const mq = window.matchMedia('(max-width: 1279px)')
    setCollapsed(mq.matches)
    const handler = (e: MediaQueryListEvent) => setCollapsed(e.matches)
    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [])

  // Close mobile menu on resize to desktop
  useEffect(() => {
    const mq = window.matchMedia('(min-width: 768px)')
    const handler = (e: MediaQueryListEvent) => { if (e.matches) setMobileOpen(false) }
    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [])

  const sidebarWidth = collapsed ? 64 : 240

  return (
    <html lang="en" suppressHydrationWarning>
      <body className={inter.className} style={{ background: 'var(--bg)' }}>
        <a href="#main-content" className="skip-link">Skip to main content</a>
        <ThemeProvider>
        <Providers>
          {/* Mobile backdrop */}
          {mobileOpen && (
            <div
              className="fixed inset-0 z-40 md:hidden"
              style={{ background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(2px)' }}
              onClick={() => setMobileOpen(false)}
            />
          )}

          <Sidebar
            collapsed={collapsed}
            setCollapsed={setCollapsed}
            mobileOpen={mobileOpen}
            setMobileOpen={setMobileOpen}
          />

          <TopBar
            sidebarWidth={sidebarWidth}
            onMobileMenuOpen={() => setMobileOpen(true)}
          />

          <main
            id="main-content"
            style={{
              marginLeft: sidebarWidth,
              paddingTop: 56,
              minHeight: '100vh',
              transition: 'margin-left 0.2s cubic-bezier(0.2,0.8,0.2,1)',
            }}
            className="overflow-auto">
            <ErrorBoundary>
              {children}
            </ErrorBoundary>
          </main>

          <GlobalSearch />
        </Providers>
        </ThemeProvider>
      </body>
    </html>
  )
}
