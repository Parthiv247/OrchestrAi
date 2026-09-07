import axios from 'axios'

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  timeout: 30000,
})

// Add X-Dev-Mode header in non-production environments for auth bypass
api.interceptors.request.use((config) => {
  if (process.env.NODE_ENV !== 'production') {
    config.headers['X-Dev-Mode'] = 'true'
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status
    const msg = error.response?.data?.detail || error.message || 'Unknown error'
    // Log all errors; 5xx errors are surfaced to the console as warnings so
    // developers see them without needing the Network tab open.
    if (status && status >= 500) {
      console.warn(`[OrchestrAI] Server error ${status}:`, msg)
    } else if (!status) {
      // Network error (no response) — backend may be down
      console.warn('[OrchestrAI] Network error — backend unreachable:', error.message)
    } else {
      console.debug(`[OrchestrAI] API ${status}:`, msg)
    }
    return Promise.reject(error)
  }
)

export const pipelineApi = {
  getAll: () => api.get('/api/pipelines'),
  trigger: (id: string) => api.post(`/api/pipelines/${id}/trigger`),
  remove: (id: string) => api.delete(`/api/pipelines/${id}`),
  getRuns: (id: string) => api.get(`/api/pipelines/${id}/runs`),
  // healthAll, health, injectAnomaly removed — /pipeline/* routes retired (old Phase-1 router)
  getConnections: () => api.get('/api/connections'),
}

export const healingApi = {
  getIncidents: (params?: { limit?: number; offset?: number; status?: string }) =>
    api.get('/api/incidents', { params }),
  getIncident: (id: string) => api.get(`/api/incidents/${id}`),
  triggerHealing: (name: string) => api.post(`/api/healing/trigger/${name}`),
  getStatus: () => api.get('/api/healing/status'),
  // token is the one-time token stored on the incident; fall back to the incident id
  // (backend accepts any token when no approval_token was set on the incident)
  approve: (id: string, token?: string) =>
    api.post(`/api/incidents/${id}/approve?token=${encodeURIComponent(token || id)}`),
  reject: (id: string, token?: string, reason?: string) =>
    api.post(`/api/incidents/${id}/reject?token=${encodeURIComponent(token || id)}`, { reason }),
}

export const analystApi = {
  query: (question: string, sessionId?: string) =>
    api.post('/api/analyst/query', { question, session_id: sessionId }),
  execute: (sql: string) =>
    api.post('/api/analyst/execute', { sql, user_role: 'viewer' }),
  getTables: () => api.get('/api/analyst/tables'),
  getSchema: (table: string, schema = 'marts') =>
    api.get(`/api/analyst/tables/${table}/schema?schema=${schema}`),
  feedback: (id: string, value: number) =>
    api.post(`/api/analyst/query/${id}/feedback`, { feedback: value }),
}

export const insightsApi = {
  get: () => api.get('/api/insights'),
  refresh: () => api.post('/api/insights/refresh', {}),
  getData: (id: string) => api.get(`/api/insights/${id}/data`),
}

export const optimizerApi = {
  optimize: (sql: string) => api.post('/api/optimize/query', { sql }),
  getSavings: () => api.get('/api/optimize/savings'),
}

export const dbtApi = {
  generate: () => api.post('/api/dbt/generate', {}),
  getModels: () => api.get('/api/dbt/models'),
  getRuns: () => api.get('/api/dbt/runs'),
}

export const learningApi = {
  getStats: () => api.get('/api/learning/stats'),
  getMttrTrend: (days = 30) => api.get(`/api/learning/mttr-trend?days=${days}`),
}

export const mlApi = {
  getMetrics: () => api.get('/api/ml/metrics'),
  train: () => api.post('/api/ml/train', {}),
}

export const statsApi = {
  getOverview: () => api.get('/api/stats/overview'),
  getMetricsHistory: () => api.get('/api/metrics/history'),
}

export const connectorApi = {
  getCatalog: () => api.get('/api/connectors/catalog'),
  getSaved: () => api.get('/api/connectors/saved'),
  create: (body: Record<string, unknown>) => api.post('/api/connectors/saved', body),
  remove: (id: string) => api.delete(`/api/connectors/saved/${id}`),
  test: (id: string) => api.post(`/api/connectors/saved/${id}/test`),
  upload: (formData: FormData) => api.post('/api/connectors/upload', formData, { headers: { 'Content-Type': 'multipart/form-data' } }),
}

export const qualityApi = {
  getSummary: () => api.get('/api/quality/summary'),
  getTables: () => api.get('/api/quality/tables'),
  getRules: () => api.get('/api/quality/rules'),
  createRule: (body: Record<string, unknown>) => api.post('/api/quality/rules', body),
  deleteRule: (id: string) => api.delete(`/api/quality/rules/${id}`),
  runRule: (id: string) => api.post(`/api/quality/rules/${id}/run`),
  toggleRule: (id: string) => api.post(`/api/quality/rules/${id}/toggle`),
  getDrift: () => api.get('/api/quality/drift'),
  scanPii: (table: string) => api.post('/api/quality/pii-scan', { table }),
}

export const reportApi = {
  list: () => api.get('/api/reports'),
  create: (body: Record<string, unknown>) => api.post('/api/reports', body),
  remove: (id: string) => api.delete(`/api/reports/${id}`),
  send: (id: string) => api.post(`/api/reports/${id}/send`),
}

export const notificationApi = {
  getConfig: () => api.get('/api/settings/notifications'),
  updateConfig: (body: Record<string, unknown>) => api.post('/api/settings/notifications', body),
  getAlertRules: () => api.get('/api/notifications/alert-rules'),
  getHistory: () => api.get('/api/notifications/history'),
  toggleRule: (id: string) => api.post(`/api/notifications/alert-rules/${id}/toggle`),
  deleteRule: (id: string) => api.delete(`/api/notifications/alert-rules/${id}`),
  dispatch: (body: Record<string, unknown>) => api.post('/api/notifications/dispatch', body),
  test: (channel: string) => api.post('/api/notifications/test', { channel }),
}

export default api
