import { ArrowRight, EyeOff, Inbox, RefreshCw, Trash2 } from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import { FeedbackSkeletonList } from '../feedback/FeedbackSkeletonList'
import type { FeedbackPublic } from '../../lib/types'

type RecentFeedbackTableProps = {
  feedbacks: FeedbackPublic[]
  loading: boolean
  message: string | null
  onRefresh: () => void
  onDeleteAll?: () => void
  purgeStatus?: string | null
  purgeLoading?: boolean
  canPurge: boolean
  onDeleteFeedback?: (feedbackId: number) => void
  statusMessage?: string | null
  tone?: 'light' | 'dark'
}

export function RecentFeedbackTable({
  feedbacks,
  loading,
  message,
  onRefresh,
  canPurge,
  onDeleteAll,
  purgeStatus,
  purgeLoading,
  onDeleteFeedback,
  statusMessage,
}: RecentFeedbackTableProps) {
  const { session } = useAuth()
  const isAdminViewer = session?.backendRole === 'admin'

  const formatSender = (feedback: FeedbackPublic) => {
    if (feedback.sender_id === 'anonymous') {
      return 'Estudante (Anônimo)'
    }
    return feedback.sender_name || feedback.sender_id.slice(0, 8)
  }

  const formatTarget = (feedback: FeedbackPublic) =>
    feedback.target_type === 'class'
      ? `Turma · ${feedback.target_name || feedback.target_id}`
      : feedback.target_type === 'subject'
        ? `${feedback.target_name || `Matéria #${feedback.target_id}`}`
        : feedback.target_name || feedback.target_id

  const renderSentimentTag = (feedback: FeedbackPublic) => {
    const label = (feedback.sentiment_label || feedback.sentiment || '').toLowerCase()
    const score =
      typeof feedback.sentiment_score === 'number'
        ? ` · ${Math.round(feedback.sentiment_score * 100)}%`
        : ''
    if (label === 'positivo') {
      return <span className="tag tag-pos">Positivo{score}</span>
    }
    if (label === 'negativo') {
      return <span className="tag tag-neg">Atenção{score}</span>
    }
    if (label) {
      return <span className="tag tag-neu">Neutro{score}</span>
    }
    return <span className="text-xs text-slate-400">—</span>
  }

  return (
    <section className="card p-5 sm:p-6 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-base sm:text-lg font-semibold text-slate-900">
            Registros recentes
          </h3>
          <p className="text-xs sm:text-sm text-slate-500">
            Últimos relatos recebidos na plataforma.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            className="btn-secondary text-xs py-1.5 px-3 min-h-[36px]"
            onClick={onRefresh}
            disabled={loading}
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
            Atualizar
          </button>
          {canPurge && onDeleteAll && feedbacks.length > 0 && (
            <button
              type="button"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 min-h-[36px] rounded-lg border border-rose-200 text-xs font-medium text-rose-700 hover:bg-rose-50 disabled:opacity-50"
              onClick={onDeleteAll}
              disabled={purgeLoading}
            >
              <Trash2 className="h-3.5 w-3.5" />
              {purgeLoading ? 'Limpando...' : 'Limpar tudo'}
            </button>
          )}
        </div>
      </div>

      {(purgeStatus || statusMessage) && (
        <p className="text-xs font-medium text-slate-600 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2">
          {statusMessage || purgeStatus}
        </p>
      )}

      {message && !loading && <p className="text-sm text-slate-500">{message}</p>}

      {loading && <FeedbackSkeletonList label="Carregando registros..." />}

      {!loading && feedbacks.length === 0 && !message && (
        <div className="py-10 flex flex-col items-center justify-center text-center gap-2 border border-dashed border-slate-200 rounded-xl bg-slate-50/40">
          <Inbox className="h-7 w-7 text-slate-300" strokeWidth={1.5} />
          <p className="text-sm text-slate-500">Nenhum feedback registrado até o momento.</p>
        </div>
      )}

      {!loading && feedbacks.length > 0 && (
        <>
          {/* Mobile Stacked Cards */}
          <div className="md:hidden space-y-3">
            {feedbacks.slice(0, 15).map((feedback) => {
              const isAnon = Boolean(feedback.is_anonymous) || feedback.sender_id === 'anonymous'
              return (
                <article
                  key={feedback.id}
                  className="rounded-xl border border-slate-200/80 p-4 space-y-2.5 bg-white"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="text-xs text-slate-600 flex flex-wrap items-center gap-1 font-medium">
                      <span className="inline-flex items-center gap-1 text-slate-900">
                        {isAnon && <EyeOff className="h-3 w-3 text-slate-400 shrink-0" />}
                        {formatSender(feedback)}
                      </span>
                      <ArrowRight className="h-3 w-3 text-slate-400" />
                      <span>{formatTarget(feedback)}</span>
                    </div>
                    <time className="text-[11px] text-slate-400 tabular-nums shrink-0">
                      {new Date(feedback.created_at).toLocaleDateString('pt-BR', {
                        day: '2-digit',
                        month: '2-digit',
                      })}
                    </time>
                  </div>
                  <p className="text-sm text-slate-800 leading-relaxed">{feedback.content}</p>
                  <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
                    <div className="flex flex-wrap items-center gap-1.5">
                      {renderSentimentTag(feedback)}
                      {isAnon && isAdminViewer && feedback.sender_id !== 'anonymous' && (
                        <span className="tag bg-amber-50 text-amber-800 border border-amber-200">
                          Anônimo (auditoria Admin)
                        </span>
                      )}
                    </div>
                    {onDeleteFeedback && (
                      <button
                        type="button"
                        className="inline-flex items-center gap-1 text-xs font-medium text-rose-600 hover:text-rose-800 py-1"
                        onClick={() => onDeleteFeedback(feedback.id)}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                        Excluir
                      </button>
                    )}
                  </div>
                </article>
              )
            })}
          </div>

          {/* Desktop Table */}
          <div className="hidden md:block overflow-x-auto rounded-lg border border-slate-200/80">
            <table className="min-w-full divide-y divide-slate-200/80 text-sm">
              <thead className="bg-slate-50/80 text-left text-xs font-semibold text-slate-500">
                <tr>
                  <th className="px-4 py-3">Autor / Destino</th>
                  <th className="px-4 py-3">Relato</th>
                  <th className="px-4 py-3 whitespace-nowrap">Clima</th>
                  <th className="px-4 py-3 whitespace-nowrap">Data</th>
                  {onDeleteFeedback && <th className="px-4 py-3 text-right">Ação</th>}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 bg-white">
                {feedbacks.slice(0, 15).map((feedback) => {
                  const isAnon =
                    Boolean(feedback.is_anonymous) || feedback.sender_id === 'anonymous'
                  return (
                    <tr key={feedback.id} className="hover:bg-slate-50/50 transition-colors">
                      <td className="px-4 py-3 align-top whitespace-nowrap">
                        <div className="flex items-center gap-1.5">
                          {isAnon && (
                            <span title="Enviado em modo anônimo">
                              <EyeOff className="h-3.5 w-3.5 text-slate-400 shrink-0" />
                            </span>
                          )}
                          <p className="font-medium text-slate-900">{formatSender(feedback)}</p>
                        </div>
                        {isAnon && isAdminViewer && feedback.sender_id !== 'anonymous' && (
                          <span className="inline-block mt-1 text-[10px] font-medium px-1.5 py-0.5 rounded bg-amber-50 text-amber-800 border border-amber-200">
                            Modo anônimo · só Admin vê
                          </span>
                        )}
                        <p className="text-xs text-slate-500 mt-0.5">→ {formatTarget(feedback)}</p>
                      </td>
                      <td className="px-4 py-3 align-top text-slate-700 max-w-md">
                        <p className="line-clamp-3 leading-relaxed">{feedback.content}</p>
                      </td>
                      <td className="px-4 py-3 align-top whitespace-nowrap">
                        {renderSentimentTag(feedback)}
                      </td>
                      <td className="px-4 py-3 align-top whitespace-nowrap text-xs text-slate-500 tabular-nums">
                        {new Date(feedback.created_at).toLocaleString('pt-BR', {
                          day: '2-digit',
                          month: '2-digit',
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </td>
                      {onDeleteFeedback && (
                        <td className="px-4 py-3 align-top text-right whitespace-nowrap">
                          <button
                            className="text-xs font-medium text-slate-400 hover:text-rose-600 transition-colors"
                            type="button"
                            onClick={() => onDeleteFeedback(feedback.id)}
                          >
                            Remover
                          </button>
                        </td>
                      )}
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  )
}
