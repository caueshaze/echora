import { EyeOff, Flag, Inbox, RefreshCw } from 'lucide-react'
import { FeedbackCard } from '../feedback/FeedbackCard'
import type { FeedbackPublic } from '../../lib/types'
import type { SentimentFilter } from '../../hooks/usePersonalFeedbacks'

type FeedbackListSectionProps = {
  title: string
  items: FeedbackPublic[]
  loading: boolean
  infoMessage?: string | null
  emptyMessage: string
  badgeLabel: string
  allowFilter?: boolean
  filter?: SentimentFilter
  onFilterChange?: (filter: SentimentFilter) => void
  hideClassification?: boolean
  onRefresh?: () => void
  onDeleteItem?: (feedback: FeedbackPublic) => void
  deleteLabel?: string
  actionStatus?: string | null
  onSecondaryAction?: (feedback: FeedbackPublic) => void
  secondaryActionLabel?: string
  secondaryActionDisabled?: boolean
  showTriggerBadge?: boolean
}

const FILTER_OPTIONS: Array<{ id: SentimentFilter; label: string }> = [
  { id: 'all', label: 'Todos' },
  { id: 'positivo', label: 'Positivos' },
  { id: 'neutro', label: 'Neutros' },
  { id: 'negativo', label: 'Atenção' },
]

export function FeedbackListSection({
  title,
  items,
  loading,
  infoMessage,
  emptyMessage,
  badgeLabel,
  allowFilter,
  filter = 'all',
  onFilterChange,
  hideClassification,
  onRefresh,
  onDeleteItem,
  deleteLabel = 'Ocultar',
  actionStatus,
  onSecondaryAction,
  secondaryActionLabel = 'Sinalizar',
  secondaryActionDisabled = false,
  showTriggerBadge = true,
}: FeedbackListSectionProps) {
  return (
    <section className="card p-5 sm:p-6 space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-base sm:text-lg font-semibold text-slate-900">
            {title}
            {!loading && (
              <span className="ml-2 text-xs font-normal text-slate-400 tabular-nums">
                ({items.length})
              </span>
            )}
          </h2>
          {onRefresh && (
            <button
              type="button"
              className="sm:hidden p-1.5 rounded-lg text-slate-500 hover:bg-slate-100"
              onClick={onRefresh}
              aria-label="Atualizar lista"
            >
              <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
          )}
        </div>

        <div className="flex items-center gap-2 overflow-x-auto pb-0.5 sm:pb-0">
          {allowFilter && (
            <div className="inline-flex rounded-lg bg-slate-100 p-1 gap-0.5">
              {FILTER_OPTIONS.map((option) => (
                <button
                  key={option.id}
                  type="button"
                  className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors whitespace-nowrap ${
                    filter === option.id
                      ? 'bg-white text-slate-900 shadow-xs'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                  onClick={() => onFilterChange?.(option.id)}
                >
                  {option.label}
                </button>
              ))}
            </div>
          )}
          {onRefresh && (
            <button
              type="button"
              className="hidden sm:inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium text-slate-600 hover:bg-slate-100"
              onClick={onRefresh}
            >
              <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
              Atualizar
            </button>
          )}
        </div>
      </div>

      {actionStatus && (
        <p className="text-xs font-medium text-brand-800 bg-brand-50 border border-brand-200/70 rounded-lg px-3 py-2">
          {actionStatus}
        </p>
      )}

      {loading && (
        <div className="py-10 text-center text-sm text-slate-500">Carregando registros...</div>
      )}

      {!loading && infoMessage && (
        <div className="py-8 text-center text-sm text-slate-500">{infoMessage}</div>
      )}

      {!loading && items.length === 0 && !infoMessage && (
        <div className="py-10 flex flex-col items-center justify-center text-center gap-2 border border-dashed border-slate-200 rounded-xl bg-slate-50/50 px-4">
          <Inbox className="h-7 w-7 text-slate-300" strokeWidth={1.5} />
          <p className="text-sm text-slate-500">{emptyMessage}</p>
        </div>
      )}

      {!loading && items.length > 0 && (
        <div className="space-y-3">
          {items.map((feedback) => (
            <div key={feedback.id} className="space-y-1.5">
              <FeedbackCard
                feedback={feedback}
                badge={badgeLabel}
                hideClassification={hideClassification}
                showTriggerBadge={showTriggerBadge}
              />
              {(onSecondaryAction || onDeleteItem) && (
                <div className="flex justify-end gap-3 px-1">
                  {onSecondaryAction && (
                    <button
                      type="button"
                      className="inline-flex items-center gap-1 text-xs font-medium text-amber-700 hover:text-amber-900 py-1"
                      onClick={() => onSecondaryAction(feedback)}
                      disabled={secondaryActionDisabled}
                    >
                      <Flag className="h-3 w-3" />
                      {secondaryActionLabel}
                    </button>
                  )}
                  {onDeleteItem && (
                    <button
                      type="button"
                      className="inline-flex items-center gap-1 text-xs font-medium text-slate-500 hover:text-rose-600 py-1"
                      onClick={() => onDeleteItem(feedback)}
                    >
                      <EyeOff className="h-3 w-3" />
                      {deleteLabel}
                    </button>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
