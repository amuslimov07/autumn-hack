export const currency = (value: number | null | undefined) =>
  value == null || !Number.isFinite(value)
    ? '—'
    : new Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'RUB', maximumFractionDigits: 0 }).format(value)

export const dateRu = (value?: string | null) => value && Number.isFinite(Date.parse(value)) ? new Intl.DateTimeFormat('ru-RU').format(new Date(value)) : '—'
export const percent = (value?: number | null) => value == null ? 'Недостаточно данных' : `${(value * 100).toFixed(1)}%`
