'use client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useState } from 'react'
import { ToastProvider } from '@/components/ui/Toaster'

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        // Retry up to 2 times with exponential backoff before surfacing an error
        retry: 2,
        retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 10000),
        staleTime: 10_000,
        refetchOnWindowFocus: false,
        // Surface network errors as structured objects so error boundaries can render them
        throwOnError: false,
      },
      mutations: {
        retry: 0,
      },
    },
  })
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(makeQueryClient)
  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        {children}
      </ToastProvider>
    </QueryClientProvider>
  )
}
