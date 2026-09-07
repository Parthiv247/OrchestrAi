'use client'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import type { Incident } from './types'
import api, {
  pipelineApi, healingApi, analystApi, insightsApi,
  optimizerApi, dbtApi, learningApi, statsApi, connectorApi,
} from './api'

export const usePipelines = () =>
  useQuery({ queryKey: ['pipelines'], queryFn: () => pipelineApi.getAll().then(r => r.data), refetchInterval: 30000 })

// usePipelineHealth removed — /pipeline/health-all route was retired with old pipeline.py router

/** Unwrap paginated incidents response — returns the incidents array regardless of response shape. */
const _unwrapIncidents = (data: { incidents?: Incident[] } | Incident[]): Incident[] => {
  if (Array.isArray(data)) return data          // legacy flat array (shouldn't happen after upgrade)
  return Array.isArray((data as { incidents?: Incident[] })?.incidents) ? (data as { incidents: Incident[] }).incidents : []
}

export const useIncidents = (params?: { limit?: number; offset?: number; status?: string }) =>
  useQuery({
    queryKey: ['incidents', params],
    queryFn: () => healingApi.getIncidents(params).then(r => ({
      incidents: _unwrapIncidents(r.data),
      total: r.data?.total ?? 0,
      has_more: r.data?.has_more ?? false,
    })),
    refetchInterval: 15000,
  })

export const useIncident = (id: string) =>
  useQuery({ queryKey: ['incident', id], queryFn: () => healingApi.getIncident(id).then(r => r.data), enabled: !!id })

export const useHealingStatus = () =>
  useQuery({ queryKey: ['healing-status'], queryFn: () => healingApi.getStatus().then(r => r.data), refetchInterval: 15000 })

export const useInsights = () =>
  useQuery({ queryKey: ['insights'], queryFn: () => insightsApi.get().then(r => r.data) })

export const useSavings = () =>
  useQuery({ queryKey: ['savings'], queryFn: () => optimizerApi.getSavings().then(r => r.data), refetchInterval: 60000 })

export const useLearningStats = () =>
  useQuery({ queryKey: ['learning'], queryFn: () => learningApi.getStats().then(r => r.data), refetchInterval: 60000 })

export const useDbtModels = () =>
  useQuery({ queryKey: ['dbt-models'], queryFn: () => dbtApi.getModels().then(r => r.data) })

export const useDbtRuns = () =>
  useQuery({ queryKey: ['dbt-runs'], queryFn: () => dbtApi.getRuns().then(r => r.data) })

export const useTables = () =>
  useQuery({ queryKey: ['tables'], queryFn: () => analystApi.getTables().then(r => r.data) })

export const useTriggerHealing = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (name: string) => healingApi.triggerHealing(name),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['incidents'] }) },
  })
}

export const useRefreshInsights = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => insightsApi.refresh(),
    onSuccess: () => setTimeout(() => qc.invalidateQueries({ queryKey: ['insights'] }), 5000),
  })
}

export const useOverviewStats = () =>
  useQuery({ queryKey: ['overview-stats'], queryFn: () => statsApi.getOverview().then(r => r.data), refetchInterval: 60000 })

export const useMetricsHistory = () =>
  useQuery({ queryKey: ['metrics-history'], queryFn: () => statsApi.getMetricsHistory().then(r => r.data), refetchInterval: 60000 })

export const useGenerateDbt = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => dbtApi.generate(),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['dbt-models'] }); qc.invalidateQueries({ queryKey: ['dbt-runs'] }) },
  })
}

export const useConnectorCatalog = () =>
  useQuery({ queryKey: ['connector-catalog'], queryFn: () => connectorApi.getCatalog().then(r => r.data), staleTime: Infinity })

export const useSavedConnections = () =>
  useQuery({ queryKey: ['connector-saved'], queryFn: () => connectorApi.getSaved().then(r => r.data), refetchInterval: 30000 })

/** Backend liveness — polls /health every 30 s to show connection status in UI. */
export const useBackendHealth = () =>
  useQuery({
    queryKey: ['backend-health'],
    queryFn: () => api.get('/health').then(r => r.data as { status: string; components: Record<string, string> }),
    refetchInterval: 30_000,
    retry: 1,
    staleTime: 15_000,
  })

