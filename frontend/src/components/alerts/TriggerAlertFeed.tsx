import { CheckCircle2, RefreshCw, ShieldAlert, Trash2 } from 'lucide-react'
import { FeedbackCard } from '../feedback/FeedbackCard'
import type { FeedbackPublic } from '../../lib/types'

type TriggerAlertFeedProps = {
  title: string
  subtitle?: string
  alerts: FeedbackPublic[]
  loading: boolean
  infoMessage?: string | null
  statusMessage?: string | null
  onRefresh?: () => void
  onDeleteFeedback?: (feedbackId: number) => void
  onResolveAlert?: (feedback: FeedbackPublic) => void
  resolvingId?: number | null
  badgeLabel?: string
}

export function TriggerAlertFeed({
  title,
  subtitle,
  alerts,
  loading,
  infoMessage,
  statusMessage,
  onRefresh,
  onDeleteFeedback,
  onResolveAlert,
  resolvingId,
  badgeLabel = 'Prioridade',
}: TriggerAlertFeedProps) {
  return (
    <div className="card p-5 sm:p-6 flex flex-col gap-4">
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-0.5">
          <div className="flex items-center gap-2">
            <ShieldAlert className="h-4 w-4 text-rose-600 shrink-0" />
            <h3 className="text-base font-semibold text-slate-900">{title}</h3>
          </div>
          <p className="text-xs sm:text-sm text-slate-500">
            {subtitle || `${alerts.length} ocorrência(s) listada(s).`}
          </p>
        </div>
        {onRefresh && (
          <button
            type="button"
            className="btn-secondary py-1.5 px-2.5 min-h-[34px] text-xs shrink-0"
            onClick={onRefresh}
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span className="hidden sm:inline">Atualizar</span>
          </button>
        )}
      </div>

      {loading && <p className="text-sm text-slate-500 py-4">Verificando ocorrências...</p>}

      {statusMessage && (
        <p className="text-xs font-medium text-slate-700 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2">
          {statusMessage}
        </p>
      )}

      {!loading && infoMessage && (
        <p className="text-sm text-slate-600 bg-slate-50 border border-slate-200 rounded-lg px-3.5 py-2.5">
          {infoMessage}
        </p>
      )}

      {!loading && alerts.length === 0 && !infoMessage && (
        <div className="py-8 text-center border border-dashed border-slate-200 rounded-xl bg-slate-50/40 px-4">
          <p className="text-sm text-slate-500">Nenhuma ocorrência pendente nesta lista.</p>
        </div>
      )}

      {!loading && alerts.length > 0 && (
        <div className="space-y-3">
          {alerts.map((feedback) => (
            <div
              key={feedback.id}
              className="rounded-xl border border-slate-200/90 bg-slate-50/50 p-3 space-y-2.5"
            >
              <FeedbackCard feedback={feedback} badge={badgeLabel} />
              {feedback.trigger_resolved_at && (
                <p className="text-xs text-slate-500 px-1">
                  Concluído em {new Date(feedback.trigger_resolved_at).toLocaleString('pt-BR')}
                  {feedback.trigger_resolved_note ? ` · ${feedback.trigger_resolved_note}` : ''}
                </p>
              )}
              {(onResolveAlert || onDeleteFeedback) && (
                <div className="flex flex-wrap justify-end gap-3 px-1">
                  {onResolveAlert && (
                    <button
                      type="button"
                      className="inline-flex items-center gap-1.5 text-xs font-medium text-emerald-700 hover:text-emerald-900 disabled:text-slate-400 py-1"
                      onClick={() => onResolveAlert(feedback)}
                      disabled={resolvingId === feedback.id}
                    >
                      <CheckCircle2 className="h-3.5 w-3.5" />
                      {resolvingId === feedback.id ? 'Registrando...' : 'Concluir atendimento'}
                    </button>
                  )}
                  {onDeleteFeedback && (
                    <button
                      type="button"
                      className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-500 hover:text-rose-600 py-1"
                      onClick={() => onDeleteFeedback(feedback.id)}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                      Remover
                    </button>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
