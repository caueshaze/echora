import {
  AlertTriangle,
  BookOpen,
  Building2,
  CheckCircle2,
  Clock,
  GraduationCap,
  MessageSquare,
  Users,
} from 'lucide-react'
import type { AdminMetricsOverview } from '../../lib/types'

type AdminMetricsGridProps = {
  metrics: AdminMetricsOverview | null
  loading: boolean
  onRefresh: () => void
}

export function AdminMetricsGrid({ metrics }: AdminMetricsGridProps) {
  const primaryCards = [
    {
      label: 'Escolas ativas',
      value: metrics?.counts.total_schools ?? 0,
      icon: Building2,
      tone: 'text-brand-700 bg-brand-50',
    },
    {
      label: 'Usuários cadastrados',
      value: metrics?.counts.total_users ?? 0,
      icon: Users,
      tone: 'text-slate-700 bg-slate-100',
    },
    {
      label: 'Turmas',
      value: metrics?.counts.total_classrooms ?? 0,
      icon: GraduationCap,
      tone: 'text-slate-700 bg-slate-100',
    },
    {
      label: 'Matérias',
      value: metrics?.counts.total_subjects ?? 0,
      icon: BookOpen,
      tone: 'text-slate-700 bg-slate-100',
    },
  ]

  const activityCards = [
    {
      label: 'Total de relatos',
      value: metrics?.counts.total_feedbacks ?? 0,
      icon: MessageSquare,
      accent: 'border-l-brand-600',
    },
    {
      label: 'Nas últimas 24h',
      value: metrics?.feedback.feedbacks_24h ?? 0,
      icon: Clock,
      accent: 'border-l-slate-400',
    },
    {
      label: 'Nos últimos 7 dias',
      value: metrics?.feedback.feedbacks_7d ?? 0,
      icon: Clock,
      accent: 'border-l-slate-300',
    },
    {
      label: 'Alertas em aberto',
      value: metrics?.triggers.active_alerts ?? 0,
      icon: AlertTriangle,
      accent:
        (metrics?.triggers.active_alerts ?? 0) > 0
          ? 'border-l-rose-600'
          : 'border-l-slate-200',
    },
    {
      label: 'Atendidos (30d)',
      value: metrics?.triggers.resolved_alerts_30d ?? 0,
      icon: CheckCircle2,
      accent: 'border-l-emerald-500',
    },
  ]

  return (
    <div className="space-y-6">
      <section className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
        {primaryCards.map((card) => {
          const Icon = card.icon
          return (
            <article key={card.label} className="card p-4 sm:p-5 flex items-start justify-between">
              <div>
                <p className="text-xs font-medium text-slate-500">{card.label}</p>
                <p className="text-2xl sm:text-3xl font-bold text-slate-900 mt-1.5 tabular-nums">
                  {card.value}
                </p>
              </div>
              <span className={`h-9 w-9 rounded-lg grid place-items-center shrink-0 ${card.tone}`}>
                <Icon className="h-4 w-4" strokeWidth={1.75} />
              </span>
            </article>
          )
        })}
      </section>

      <section className="card p-5 sm:p-6 space-y-4">
        <div>
          <h2 className="text-base font-semibold text-slate-900">Volume e acompanhamento</h2>
          <p className="text-sm text-slate-500">
            Movimentação de relatos e alertas nas unidades conectadas.
          </p>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          {activityCards.map((card) => (
            <div
              key={card.label}
              className={`rounded-lg border border-slate-200/80 border-l-4 ${card.accent} bg-slate-50/40 p-3.5`}
            >
              <p className="text-xs font-medium text-slate-500">{card.label}</p>
              <p className="text-2xl font-bold text-slate-900 mt-1 tabular-nums">{card.value}</p>
            </div>
          ))}
        </div>

        <p className="text-xs text-slate-400">
          Último relato registrado:{' '}
          {metrics?.feedback.last_feedback_at
            ? new Date(metrics.feedback.last_feedback_at).toLocaleString('pt-BR')
            : 'Nenhum registro ainda'}
        </p>
      </section>
    </div>
  )
}
