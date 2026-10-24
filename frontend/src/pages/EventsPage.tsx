import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CalendarPlus, FileUp, Pencil, X } from 'lucide-react'
import { useRef, useState } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { api } from '../api/client'
import { QueryState, EmptyState } from '../components/State'
import { useCompanyContext } from '../components/CompanyContext'
import { keys } from '../hooks/queries'
import { currency, dateRu } from '../utils/format'

const schema = z.object({
  date: z.string().min(1, 'Укажите дату'),
  amount: z.coerce.number().positive('Сумма должна быть больше нуля'),
  direction: z.enum(['поступление', 'списание']),
  category: z.string().min(1),
  event_type: z.string().min(1),
  description: z.string().max(1000),
  source: z.string().min(1),
  status: z.enum(['Ожидается', 'Подтверждено', 'Исполнено', 'Отменено']),
})
type EventValues = z.output<typeof schema>
type EventFormInput = z.input<typeof schema>

export function EventsPage() {
  const { company } = useCompanyContext()
  const client = useQueryClient()
  const fileInput = useRef<HTMLInputElement>(null)
  const [message, setMessage] = useState('')
  const [editingId, setEditingId] = useState<number | null>(null)
  const result = useQuery({ queryKey: keys.events(company?.company_id ?? ''), queryFn: () => api.events(company!.company_id), enabled: Boolean(company) })
  const form = useForm<EventFormInput, unknown, EventValues>({
    resolver: zodResolver(schema),
    defaultValues: { date: new Date().toISOString().slice(0, 10), amount: 10000, direction: 'списание', category: 'Прочие расходы', event_type: 'Пользовательское событие', description: '', source: 'ручной ввод', status: 'Ожидается' },
  })
  const refresh = () => client.invalidateQueries({ queryKey: keys.events(company?.company_id ?? '') })
  const create = useMutation({ mutationFn: (values: EventValues) => api.createEvent(company!.company_id, values), onSuccess: () => { form.reset({ ...form.getValues(), description: '' }); setMessage('Событие сохранено.'); refresh() } })
  const update = useMutation({ mutationFn: ({ id, event }: { id: number; event: Partial<EventValues> }) => api.updateEvent(company!.company_id, id, event), onSuccess: refresh })
  const cancel = useMutation({ mutationFn: (id: number) => api.cancelEvent(company!.company_id, id), onSuccess: refresh })
  const importFile = useMutation({ mutationFn: (file: File) => api.importEvents(company!.company_id, file), onSuccess: (response) => { setMessage(`Импортировано событий: ${response.imported}`); refresh() } })
  const onSubmit = form.handleSubmit((values) => {
    if (editingId !== null) {
      update.mutate({ id: editingId, event: values }, { onSuccess: () => { setEditingId(null); form.reset(); setMessage('Событие обновлено.') } })
    } else {
      create.mutate(values)
    }
  })
  const categories = ['Выручка и поступления от клиентов','Закупки и поставщики','Фонд оплаты труда','Налоги и обязательные платежи','Аренда','Маркетинг и реклама','Логистика и транспорт','Комиссии банка','Кредиты и проценты','Лизинг','Оборудование и капитальные расходы','Прочие поступления','Прочие расходы']
  const types = ['Счёт клиенту','Ожидаемое поступление','Счёт поставщика','Зарплата','Налоговый платёж (ввод пользователя)','Аренда','Кредит или лизинг','Пользовательское событие']
  return <div className="page-stack"><div className="page-heading"><div><div className="eyebrow">ПЛАНИРУЕМЫЕ ДВИЖЕНИЯ</div><h1>Будущие события</h1><p>События сохраняются локально в SQLite отдельно для каждой компании.</p></div><button className="button secondary" onClick={() => fileInput.current?.click()}><FileUp size={16} />Импорт CSV</button><input ref={fileInput} hidden type="file" accept=".csv,text/csv" onChange={(event) => { const file = event.target.files?.[0]; if (file) importFile.mutate(file); event.currentTarget.value = '' }} /></div>
    {message && <div className="notice success-notice">{message}<button aria-label="Закрыть сообщение" onClick={() => setMessage('')}><X size={15} /></button></div>}
    {(create.isError || importFile.isError || update.isError || cancel.isError) && <div className="inline-error">{[create.error, importFile.error, update.error, cancel.error].filter(Boolean).map((error) => (error as Error).message).join(' · ')}</div>}
    <div className="content-grid event-grid">
      <section className="card"><div className="card-heading"><div><h2>Добавить событие</h2><p>Налоговые суммы вводятся только пользователем или из файла.</p></div><CalendarPlus className="heading-icon" size={20} /></div>
        <form className="event-form" onSubmit={onSubmit}>
          <label>Дата<input type="date" {...form.register('date')} />{form.formState.errors.date && <small className="field-error">{form.formState.errors.date.message}</small>}</label>
          <label>Направление<select {...form.register('direction')}><option value="списание">Списание</option><option value="поступление">Поступление</option></select></label>
          <label>Сумма, ₽<input type="number" step="0.01" min="0.01" {...form.register('amount')} />{form.formState.errors.amount && <small className="field-error">{form.formState.errors.amount.message}</small>}</label>
          <label>Тип события<select {...form.register('event_type')}>{types.map((type) => <option key={type}>{type}</option>)}</select></label>
          <label>Категория<select {...form.register('category')}>{categories.map((category) => <option key={category}>{category}</option>)}</select></label>
          <label>Статус<select {...form.register('status')}><option>Ожидается</option><option>Подтверждено</option><option>Исполнено</option><option>Отменено</option></select></label>
          <label className="full-field">Описание<input placeholder="Например: счёт поставщика за сырьё" {...form.register('description')} /></label>
          <button className="button primary full-field" type="submit" disabled={create.isPending || update.isPending}>{editingId !== null ? 'Сохранить изменения' : 'Сохранить событие'}</button>
          {editingId !== null && <button className="button secondary full-field" type="button" onClick={() => { setEditingId(null); form.reset() }}>Отменить редактирование</button>}
        </form>
      </section>
      <section className="card"><div className="card-heading"><div><h2>Список событий</h2><p>Добавление будущего платежа не изменяет историю операций.</p></div></div>
        <QueryState isLoading={result.isLoading} error={result.error as Error | null}>{!result.data?.items.length ? <EmptyState>События ещё не добавлены.</EmptyState> : <div className="event-list">{result.data.items.map((event) => <article className="event-card" key={event.id}><div className="event-card-head"><span className={`direction-tag ${event.direction === 'поступление' ? 'income' : 'expense'}`}>{event.direction}</span><select aria-label={`Статус события ${event.id}`} value={event.status} onChange={(change) => update.mutate({ id: event.id, event: { status: change.target.value as EventValues['status'] } })}><option>Ожидается</option><option>Подтверждено</option><option>Исполнено</option><option>Отменено</option></select></div><div className="event-card-title">{event.description || event.event_type}</div><div className="event-card-meta">{dateRu(event.date)} · {event.category} · {event.source}</div><div className="event-card-foot"><strong className={event.direction === 'поступление' ? 'positive' : 'negative'}>{currency(event.direction === 'поступление' ? event.amount : -event.amount)}</strong><div className="event-actions">{event.status !== 'Отменено' && <><button aria-label={`Редактировать событие ${event.id}`} className="icon-button edit" onClick={() => { setEditingId(event.id); form.reset({ date: event.date, amount: event.amount, direction: event.direction, category: event.category, event_type: event.event_type, description: event.description, source: event.source, status: event.status }) }}><Pencil size={15} /></button><button aria-label={`Отменить событие ${event.id}`} className="icon-button" onClick={() => cancel.mutate(event.id)}><X size={17} /></button></>}</div></div></article>)}</div>}</QueryState>
      </section>
    </div>
  </div>
}
