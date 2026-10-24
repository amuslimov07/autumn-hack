import type {
  CategoryResponse, Company, Evaluation, EventItem, ForecastResult, Operation, Page, RecurringItem, Summary,
} from '../types/api'

const API_ROOT = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api'

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message)
    this.name = 'ApiError'
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_ROOT}${path}`, init)
  if (!response.ok) {
    let message = `Ошибка API (${response.status})`
    try {
      const payload = await response.json() as { detail?: string }
      if (payload.detail) message = payload.detail
    } catch {
      message = response.statusText || message
    }
    throw new ApiError(message, response.status)
  }
  return response.json() as Promise<T>
}

export const api = {
  health: () => request<{ status: string; data_available: boolean; companies: number; operations: number; message: string }>('/health'),
  companies: (search = '') => request<Page<Company>>(`/companies?page=1&page_size=200${search ? `&search=${encodeURIComponent(search)}` : ''}`),
  overview: () => request<{ companies: number; operations: number; rows: Company[] }>('/companies/overview'),
  summary: (id: string, horizon: number, reserve: number) => request<Summary>(`/companies/${id}/summary?horizon=${horizon}&reserve=${reserve}`),
  operations: (id: string, params: URLSearchParams) => request<Page<Operation>>(`/companies/${id}/operations?${params}`),
  categories: (id: string) => request<CategoryResponse>(`/companies/${id}/categories`),
  recurring: (id: string) => request<{ items: RecurringItem[] }>(`/companies/${id}/recurring`),
  forecast: (id: string, horizon: number, reserve: number) => request<ForecastResult>(`/companies/${id}/forecast?horizon=${horizon}&reserve=${reserve}`),
  evaluation: (id: string) => request<Evaluation>(`/companies/${id}/model-evaluation`),
  events: (id: string) => request<{ items: EventItem[] }>(`/companies/${id}/events`),
  changeCategory: (companyId: string, operationId: string, category: string) =>
    request(`/companies/${companyId}/operations/${encodeURIComponent(operationId)}/category`, {
      method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ category }),
    }),
  confirmRecurring: (companyId: string, recurringId: string, confirmed: boolean) =>
    request(`/companies/${companyId}/recurring/${recurringId}`, {
      method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ confirmed }),
    }),
  createEvent: (companyId: string, event: Omit<EventItem, 'id' | 'company_id'>) =>
    request<EventItem>(`/companies/${companyId}/events`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(event),
    }),
  updateEvent: (companyId: string, eventId: number, event: Partial<EventItem>) =>
    request<EventItem>(`/companies/${companyId}/events/${eventId}`, {
      method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(event),
    }),
  cancelEvent: (companyId: string, eventId: number) =>
    request<EventItem>(`/companies/${companyId}/events/${eventId}`, { method: 'DELETE' }),
  importEvents: (companyId: string, file: File) => {
    const body = new FormData()
    body.append('file', file)
    return request<{ imported: number }>(`/companies/${companyId}/events/import`, { method: 'POST', body })
  },
}
