import { AlertCircle, LoaderCircle } from 'lucide-react'
import type { ReactNode } from 'react'

export function Loading({ label = 'Загружаем данные…' }: { label?: string }) {
  return <div className="state"><LoaderCircle className="spin" size={20} />{label}</div>
}

export function ErrorState({ message }: { message: string }) {
  return <div className="error-state"><AlertCircle size={20} /><span>{message}</span></div>
}

export function EmptyState({ children }: { children: ReactNode }) {
  return <div className="empty-state">{children}</div>
}

export function QueryState({ isLoading, error, children }: { isLoading: boolean; error: Error | null; children: ReactNode }) {
  if (isLoading) return <Loading />
  if (error) return <ErrorState message={error.message} />
  return children
}
