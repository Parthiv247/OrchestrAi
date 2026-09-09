'use client'

export const dynamic = 'force-dynamic'
import './globals.css'
import { Providers } from './providers'
import { Sidebar } from '@/components/layout/Sidebar'
import { TopBar } from '@/components/layout/TopBar'
import { GlobalSearch } from '@/components/ui/GlobalSearch'
import { ErrorBoundary } from '@/components/ui/ErrorBoundary'
import { ThemeProvider } from '@/lib/theme'

// System font fallback — avoids Google Fonts network fetch in CI/offline builds
const inter = { className: '' }

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={inter.className} style={{ background: 'var(--bg)' }}>
        <a href="#main-content" className="skip-link">Skip to main content</a>
        <ThemeProvider>
        <Providers>
          <Sidebar />
          <TopBar sidebarWidth={220} onMobileMenuOpen={() => {}} />
          <main
            id="main-content"
            style={{
              marginLeft: 220,
              paddingTop: 56,
              minHeight: '100vh',
              transition: 'margin-left 0.25s cubic-bezier(0.25,0.46,0.45,0.94)',
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
