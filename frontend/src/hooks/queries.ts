import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'

export const keys = {
  health: ['health'] as const,
  companies: (search: string) => ['companies', search] as const,
  overview: ['companies-overview'] as const,
  summary: (id: string, horizon: number, reserve: number) => ['summary', id, horizon, reserve] as const,
  operations: (id: string, params: string) => ['operations', id, params] as const,
  categories: (id: string) => ['categories', id] as const,
  recurring: (id: string) => ['recurring', id] as const,
  forecast: (id: string, horizon: number, reserve: number) => ['forecast', id, horizon, reserve] as const,
  evaluation: (id: string) => ['evaluation', id] as const,
  events: (id: string) => ['events', id] as const,
}

export function useHealth() {
  return useQuery({ queryKey: keys.health, queryFn: api.health, retry: 1 })
}

export function useCompanies(search = '') {
  return useQuery({ queryKey: keys.companies(search), queryFn: () => api.companies(search) })
}

export function useSummary(id: string | undefined, horizon: number, reserve: number) {
  return useQuery({ queryKey: keys.summary(id ?? '', horizon, reserve), queryFn: () => api.summary(id!, horizon, reserve), enabled: Boolean(id) })
}

export function useForecast(id: string | undefined, horizon: number, reserve: number) {
  return useQuery({ queryKey: keys.forecast(id ?? '', horizon, reserve), queryFn: () => api.forecast(id!, horizon, reserve), enabled: Boolean(id) })
}
