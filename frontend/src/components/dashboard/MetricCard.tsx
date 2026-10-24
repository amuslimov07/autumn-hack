import type { LucideIcon } from 'lucide-react'
import { ArrowDownRight, ArrowUpRight, Minus } from 'lucide-react'
import type { ReactNode } from 'react'

export function MetricCard({ title, value, detail, icon: Icon, tone = 'mint', trend }: {
  title: string; value: ReactNode; detail?: string; icon: LucideIcon; tone?: 'mint' | 'blue' | 'amber' | 'rose'; trend?: 'up' | 'down' | 'flat'
}) {
  const Trend = trend === 'up' ? ArrowUpRight : trend === 'down' ? ArrowDownRight : Minus
  return <article className="metric-card">
    <div className={`metric-icon ${tone}`}><Icon size={19} /></div>
    <div className="metric-title">{title}</div>
    <div className="metric-value">{value}</div>
    <div className="metric-detail">{trend && <Trend size={14} />} {detail}</div>
  </article>
}
