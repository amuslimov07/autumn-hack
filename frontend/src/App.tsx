import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { lazy, Suspense, useState } from 'react'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { Shell } from './components/Shell'
import './styles.css'

const Dashboard = lazy(() => import('./pages/Dashboard').then((module) => ({ default: module.Dashboard })))
const ForecastPage = lazy(() => import('./pages/ForecastPage').then((module) => ({ default: module.ForecastPage })))
const OperationsPage = lazy(() => import('./pages/OperationsPage').then((module) => ({ default: module.OperationsPage })))
const CategoriesPage = lazy(() => import('./pages/CategoriesPage').then((module) => ({ default: module.CategoriesPage })))
const RecurringPage = lazy(() => import('./pages/RecurringPage').then((module) => ({ default: module.RecurringPage })))
const EventsPage = lazy(() => import('./pages/EventsPage').then((module) => ({ default: module.EventsPage })))
const QualityPage = lazy(() => import('./pages/QualityPage').then((module) => ({ default: module.QualityPage })))
const CompaniesPage = lazy(() => import('./pages/CompaniesPage').then((module) => ({ default: module.CompaniesPage })))

function Application() {
  const [client] = useState(() => new QueryClient({
    defaultOptions: { queries: { staleTime: 30_000, refetchOnWindowFocus: false, retry: 1 } },
  }))
  return <QueryClientProvider client={client}><BrowserRouter><Suspense fallback={<div className="state">Загружаем страницу…</div>}><Routes><Route element={<Shell />}>
    <Route index element={<Dashboard />} />
    <Route path="forecast" element={<ForecastPage />} />
    <Route path="operations" element={<OperationsPage />} />
    <Route path="categories" element={<CategoriesPage />} />
    <Route path="recurring" element={<RecurringPage />} />
    <Route path="events" element={<EventsPage />} />
    <Route path="quality" element={<QualityPage />} />
    <Route path="companies" element={<CompaniesPage />} />
    <Route path="*" element={<Dashboard />} />
  </Route></Routes></Suspense></BrowserRouter></QueryClientProvider>
}

export default Application
