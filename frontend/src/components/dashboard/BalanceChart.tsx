import { Area, AreaChart, CartesianGrid, Legend, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { ForecastPoint } from '../../types/api'
import { currency, dateRu } from '../../utils/format'

export function BalanceChart({ points, history = [], reserve = 0 }: { points: ForecastPoint[]; history?: { date: string; balance: number; inflow: number; outflow: number }[]; reserve?: number }) {
  const data = [
    ...history.map((point) => ({ date: point.date, actualBalance: point.balance, balance: null, lower: null, upper: null, inflow: point.inflow, outflow: point.outflow, event_flow: 0 })),
    ...points.map((point) => ({ ...point, actualBalance: null })),
  ].sort((left, right) => left.date.localeCompare(right.date)).map((point) => ({
    ...point, shortDate: new Date(point.date).toLocaleDateString('ru-RU', { day: '2-digit', month: 'short' }),
  }))
  if (!data.length) return <div className="empty-state">Нет прогноза для отображения.</div>
  return <div className="chart-wrap">
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={data} margin={{ top: 12, right: 12, left: 12, bottom: 0 }}>
        <defs><linearGradient id="balanceFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#28a879" stopOpacity={0.19} /><stop offset="100%" stopColor="#28a879" stopOpacity={0.01} /></linearGradient></defs>
        <CartesianGrid stroke="#edf0f5" vertical={false} />
        <XAxis dataKey="shortDate" tickLine={false} axisLine={false} minTickGap={32} />
        <YAxis tickFormatter={(value: number) => `${Math.round(value / 1000)} тыс.`} tickLine={false} axisLine={false} width={64} />
        <Tooltip labelFormatter={(_, entries) => dateRu(entries[0]?.payload.date)} formatter={(value, name) => [currency(Number(value)), String(name)]} />
        <Legend />
        <ReferenceLine y={0} stroke="#db6c6c" strokeDasharray="5 5" label="Ноль" />
        {reserve > 0 && <ReferenceLine y={reserve} stroke="#e5a53d" strokeDasharray="4 4" label="Резерв" />}
        <Area type="monotone" dataKey="upper" stroke="none" fill="transparent" name="Верхняя оценка" connectNulls />
        <Area type="monotone" dataKey="lower" stroke="none" fill="url(#balanceFill)" name="Диапазон оценки" connectNulls />
        <Line type="monotone" dataKey="actualBalance" stroke="#3978c5" strokeWidth={2} dot={false} name="Фактический остаток" connectNulls={false} />
        <Line type="monotone" dataKey="balance" stroke="#258a6a" strokeWidth={2.5} dot={false} name="Прогноз остатка" connectNulls />
        <Line type="monotone" dataKey="event_flow" stroke="#d4952e" strokeWidth={1} dot={false} name="События, чистый поток" />
      </AreaChart>
    </ResponsiveContainer>
  </div>
}
