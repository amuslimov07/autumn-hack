import { useState } from 'react'
import { AlertTriangle, CalendarDays, ShieldAlert } from 'lucide-react'
import { BalanceChart } from '../components/dashboard/BalanceChart'
import { QueryState } from '../components/State'
import { useCompanyContext } from '../components/CompanyContext'
import { useForecast } from '../hooks/queries'
import { currency, dateRu, percent } from '../utils/format'

export function ForecastPage() {
  const { company } = useCompanyContext()
  const [horizon, setHorizon] = useState(90)
  const [reserve, setReserve] = useState(250000)
  const result = useForecast(company?.company_id, horizon, reserve)
  return <div className="page-stack">
    <div className="page-heading"><div><div className="eyebrow">ПЛАНИРОВАНИЕ</div><h1>Прогноз и риски</h1><p>Потоки компании прогнозируются раздельно; подтверждённые события добавляются отдельным слоем.</p></div></div>
    <div className="card filter-card"><label>Горизонт прогноза<select value={horizon} onChange={(event) => setHorizon(Number(event.target.value))}><option value={30}>30 дней</option><option value={60}>60 дней</option><option value={90}>90 дней</option></select></label><label>Минимальный резерв, ₽<input aria-label="Минимальный резерв" type="number" min={0} step={50000} value={reserve} onChange={(event) => setReserve(Math.max(0, Number(event.target.value)))} /></label></div>
    <QueryState isLoading={result.isLoading} error={result.error as Error | null}>{result.data && <>
      <section className="card chart-card"><div className="card-heading"><div><h2>Ожидаемый остаток</h2><p>Последний остаток на {dateRu(result.data.balance_date)} · метод: {result.data.method}</p></div><span className="tag">{horizon} дней</span></div><BalanceChart points={result.data.items} history={result.data.history} reserve={reserve} /><p className="small-note">{result.data.uncertainty_note}</p></section>
      <div className="metrics-grid">
        <article className="metric-card"><div className="metric-icon amber"><CalendarDays size={19} /></div><div className="metric-title">Поступления прогноза</div><div className="metric-value">{currency(result.data.items.reduce((sum, item) => sum + item.inflow, 0))}</div><div className="metric-detail">статистический прогноз</div></article>
        <article className="metric-card"><div className="metric-icon rose"><CalendarDays size={19} /></div><div className="metric-title">Расходы прогноза</div><div className="metric-value">{currency(result.data.items.reduce((sum, item) => sum + item.outflow, 0))}</div><div className="metric-detail">известные события отдельно</div></article>
        <article className="metric-card"><div className="metric-icon blue"><ShieldAlert size={19} /></div><div className="metric-title">Риск нарушения резерва</div><div className="metric-value">{result.data.risk.risk_level}</div><div className="metric-detail">вероятность: {percent(result.data.risk.probability)}</div></article>
      </div>
      {result.data.warning ? <section className="card warning-card"><div className="warning-heading"><AlertTriangle size={20} /><h2>Возможное снижение остатка ниже резерва</h2></div><p><strong>{dateRu(result.data.warning.date)}</strong> — прогнозная нехватка {currency(result.data.warning.deficit)}. {result.data.warning.reasons}</p><p>{result.data.warning.action}</p><p className="small-note">Риск рассчитан методом: {result.data.risk.method}</p></section> : <div className="notice"><ShieldAlert size={17} /> Детерминированный прогноз не показывает пересечения выбранного резерва.</div>}
    </>}</QueryState>
  </div>
}
