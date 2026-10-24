import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Search, SlidersHorizontal } from 'lucide-react'
import { api } from '../api/client'
import { QueryState, EmptyState } from '../components/State'
import { useCompanyContext } from '../components/CompanyContext'
import { keys } from '../hooks/queries'
import { currency, dateRu } from '../utils/format'

const CATEGORIES = ['Выручка и поступления от клиентов','Закупки и поставщики','Фонд оплаты труда','Налоги и обязательные платежи','Аренда','Маркетинг и реклама','Логистика и транспорт','Комиссии банка','Кредиты и проценты','Лизинг','Оборудование и капитальные расходы','Переводы между собственными счетами','Прочие поступления','Прочие расходы','Требует проверки']

export function OperationsPage() {
  const { company } = useCompanyContext()
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [direction, setDirection] = useState('')
  const [category, setCategory] = useState('')
  const [counterparty, setCounterparty] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc')
  const params = new URLSearchParams({ page: String(page), page_size: '30', sort: 'operation_date', order: sortOrder })
  if (search) params.set('search', search)
  if (direction) params.set('direction', direction)
  if (category) params.set('category', category)
  if (counterparty) params.set('counterparty', counterparty)
  if (startDate) params.set('start_date', startDate)
  if (endDate) params.set('end_date', endDate)
  const queryKey = params.toString()
  const result = useQuery({ queryKey: keys.operations(company?.company_id ?? '', queryKey), queryFn: () => api.operations(company!.company_id, params) })
  const pageCount = Math.ceil((result.data?.total ?? 0) / 30)
  const setFilter = (action: () => void) => { action(); setPage(1) }
  return <div className="page-stack">
    <div className="page-heading"><div><div className="eyebrow">ИСТОРИЯ КОМПАНИИ</div><h1>Операции</h1><p>Категории определяются автоматически по назначению и данным контрагента.</p></div><span className="tag">{result.data?.total.toLocaleString('ru-RU') ?? '…'} операций</span></div>
    <section className="card">
      <div className="operation-filters">
        <label className="search-box"><Search size={17} /><input placeholder="Поиск: контрагент или назначение" value={search} onChange={(event) => setFilter(() => setSearch(event.target.value))} /></label>
        <label><SlidersHorizontal size={15} /><select aria-label="Направление" value={direction} onChange={(event) => setFilter(() => setDirection(event.target.value))}><option value="">Все направления</option><option value="поступление">Поступления</option><option value="списание">Списания</option></select></label>
        <label><select aria-label="Категория" value={category} onChange={(event) => setFilter(() => setCategory(event.target.value))}><option value="">Все категории</option>{CATEGORIES.map((item) => <option key={item}>{item}</option>)}</select></label>
        <input aria-label="Контрагент" placeholder="Контрагент" value={counterparty} onChange={(event) => setFilter(() => setCounterparty(event.target.value))} />
        <input aria-label="Дата с" type="date" value={startDate} onChange={(event) => setFilter(() => setStartDate(event.target.value))} />
        <input aria-label="Дата по" type="date" value={endDate} onChange={(event) => setFilter(() => setEndDate(event.target.value))} />
        <button className="button secondary" onClick={() => { setSortOrder(sortOrder === 'desc' ? 'asc' : 'desc'); setPage(1) }}>Дата {sortOrder === 'desc' ? '↓' : '↑'}</button>
      </div>
      <QueryState isLoading={result.isLoading} error={result.error as Error | null}>
        {result.data?.items.length ? <div className="table-scroll"><table><thead><tr><th>Дата</th><th>Контрагент / назначение</th><th>Направление</th><th>Сумма</th><th>Остаток дня</th><th>Категория</th></tr></thead><tbody>{result.data.items.map((operation) => <tr key={operation.operation_id}>
          <td className="nowrap">{dateRu(operation.operation_date)}</td><td><strong>{operation.counterparty_name || 'Не указан'}</strong><small className="table-subtitle">{operation.payment_purpose || '—'}</small><small className="table-subtitle">ИНН: {operation.counterparty_inn || '—'}</small></td>
          <td><span className={`direction-tag ${operation.direction === 'поступление' ? 'income' : 'expense'}`}>{operation.direction}</span></td><td className={operation.signed_amount > 0 ? 'positive nowrap' : 'negative nowrap'}>{currency(operation.signed_amount)}</td><td className="nowrap">{currency(operation.balance_eod)}</td><td><span className="tag">{operation.category}</span></td>
        </tr>)}</tbody></table></div> : <EmptyState>По этим фильтрам операций нет.</EmptyState>}
      </QueryState>
      <div className="pagination"><span>Страница {page} из {Math.max(pageCount, 1)} · всего {result.data?.total ?? 0}</span><div><button className="button secondary" disabled={page <= 1} onClick={() => setPage(page - 1)}>Назад</button><button className="button secondary" disabled={page >= pageCount} onClick={() => setPage(page + 1)}>Далее</button></div></div>
    </section>
  </div>
}
