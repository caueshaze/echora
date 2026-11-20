import { useMemo, useState } from 'react'
import { AlertTriangle, ArrowRight, EyeOff, Inbox, RefreshCw, Search, Trash2, X } from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import { FeedbackSkeletonList } from '../feedback/FeedbackSkeletonList'
import type { AdminRole, FeedbackPublic, FeedbackTargetType } from '../../lib/types'

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

type SentimentOrAlertFilter = 'all' | 'positivo' | 'neutro' | 'negativo' | 'triggered'
type TargetTypeFilter = 'all' | FeedbackTargetType
type TargetRoleFilter = 'all' | AdminRole
type AnonymityFilter = 'all' | 'identified' | 'anonymous'
type SortOrder = 'desc' | 'asc'

const SENTIMENT_FILTER_OPTIONS: Array<{ id: SentimentOrAlertFilter; label: string }> = [
  { id: 'all', label: 'Todos' },
  { id: 'positivo', label: 'Positivos' },
  { id: 'neutro', label: 'Neutros' },
  { id: 'negativo', label: 'Atenção' },
  { id: 'triggered', label: 'Com alerta' },
]

function getSentimentKey(feedback: FeedbackPublic) {
  return (feedback.sentiment_label || feedback.sentiment || '').toLowerCase()
}

function isFeedbackAnonymous(feedback: FeedbackPublic) {
  return Boolean(feedback.is_anonymous) || feedback.sender_id === 'anonymous'
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

  const [search, setSearch] = useState('')
  const [sentimentFilter, setSentimentFilter] = useState<SentimentOrAlertFilter>('all')
  const [targetTypeFilter, setTargetTypeFilter] = useState<TargetTypeFilter>('all')
  const [targetRoleFilter, setTargetRoleFilter] = useState<TargetRoleFilter>('all')
  const [anonymityFilter, setAnonymityFilter] = useState<AnonymityFilter>('all')
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc')

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

  const counts = useMemo(() => {
    const summary = {
      all: feedbacks.length,
      positivo: 0,
      neutro: 0,
      negativo: 0,
      triggered: 0,
    }
    for (const item of feedbacks) {
      const key = getSentimentKey(item)
      if (key === 'positivo') summary.positivo += 1
      else if (key === 'negativo') summary.negativo += 1
      else if (key) summary.neutro += 1
      if (item.has_trigger) summary.triggered += 1
    }
    return summary
  }, [feedbacks])

  const filteredFeedbacks = useMemo(() => {
    const query = search.trim().toLowerCase()
    const filtered = feedbacks.filter((feedback) => {
      if (sentimentFilter === 'triggered') {
        if (!feedback.has_trigger) return false
      } else if (sentimentFilter !== 'all') {
        const key = getSentimentKey(feedback)
        if (sentimentFilter === 'neutro') {
          if (key === 'positivo' || key === 'negativo' || !key) return false
        } else if (key !== sentimentFilter) {
          return false
        }
      }

      if (targetTypeFilter !== 'all' && feedback.target_type !== targetTypeFilter) {
        return false
      }

      if (targetTypeFilter === 'user' && targetRoleFilter !== 'all') {
        if (feedback.target_role !== targetRoleFilter) {
          return false
        }
      }

      const isAnon = isFeedbackAnonymous(feedback)
      if (anonymityFilter === 'anonymous' && !isAnon) return false
      if (anonymityFilter === 'identified' && isAnon) return false

      if (query) {
        const searchable = [
          feedback.content,
          formatSender(feedback),
          feedback.sender_email ?? '',
          formatTarget(feedback),
          feedback.target_email ?? '',
          feedback.category ?? '',
          isAnon ? 'anonimo anônimo' : '',
        ]
          .join(' ')
          .toLowerCase()
        if (!searchable.includes(query)) return false
      }

      return true
    })

    return [...filtered].sort((a, b) => {
      const diff = new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
      return sortOrder === 'asc' ? diff : -diff
    })
  }, [feedbacks, search, sentimentFilter, targetTypeFilter, targetRoleFilter, anonymityFilter, sortOrder])

  const hasActiveFilters =
    Boolean(search.trim()) ||
    sentimentFilter !== 'all' ||
    targetTypeFilter !== 'all' ||
    targetRoleFilter !== 'all' ||
    anonymityFilter !== 'all' ||
    sortOrder !== 'desc'

  const resetFilters = () => {
    setSearch('')
    setSentimentFilter('all')
    setTargetTypeFilter('all')
    setTargetRoleFilter('all')
    setAnonymityFilter('all')
    setSortOrder('desc')
  }

  const renderSentimentTag = (feedback: FeedbackPublic) => {
    const label = getSentimentKey(feedback)
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
            Todos os relatos
          </h3>
          <p className="text-xs sm:text-sm text-slate-500">
            Visualize, busque e filtre os relatos registrados na plataforma.
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

      {!loading && feedbacks.length > 0 && (
        <div className="space-y-3 pt-1">
          {/* Pill Filters */}
          <div className="flex items-center gap-1.5 overflow-x-auto pb-1">
            {SENTIMENT_FILTER_OPTIONS.map((option) => {
              const active = sentimentFilter === option.id
              const count = counts[option.id]
              return (
                <button
                  key={option.id}
                  type="button"
                  onClick={() => setSentimentFilter(option.id)}
                  className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium whitespace-nowrap transition-colors ${
                    active
                      ? 'bg-brand-700 dark:bg-brand-600 text-white'
                      : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-200/70 dark:hover:bg-slate-700/70'
                  }`}
                >
                  <span>{option.label}</span>
                  <span
                    className={`px-1.5 py-0.5 rounded text-[11px] tabular-nums ${
                      active
                        ? 'bg-white/20 text-white'
                        : 'bg-white dark:bg-slate-900 text-slate-500 dark:text-slate-300'
                    }`}
                  >
                    {count}
                  </span>
                </button>
              )
            })}
          </div>

          {/* Search & Select Filters */}
          <div
            className={`grid gap-2.5 sm:grid-cols-2 ${
              targetTypeFilter === 'user' ? 'lg:grid-cols-5' : 'lg:grid-cols-4'
            }`}
          >
            <div className="relative">
              <Search className="h-4 w-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
              <input
                type="search"
                className="input pl-9"
                placeholder="Buscar relato, autor ou destino..."
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                aria-label="Buscar relatos"
              />
            </div>

            <select
              className="input"
              value={targetTypeFilter}
              onChange={(event) => {
                const nextType = event.target.value as TargetTypeFilter
                setTargetTypeFilter(nextType)
                if (nextType !== 'user') {
                  setTargetRoleFilter('all')
                }
              }}
              aria-label="Filtrar por tipo de alvo"
            >
              <option value="all">Todos os alvos</option>
              <option value="user">Pessoa (Docente / Gestão / Aluno)</option>
              <option value="class">Turma</option>
              <option value="subject">Matéria</option>
            </select>

            {targetTypeFilter === 'user' && (
              <select
                className="input animate-fadeUp"
                value={targetRoleFilter}
                onChange={(event) => setTargetRoleFilter(event.target.value as TargetRoleFilter)}
                aria-label="Filtrar por perfil do alvo"
              >
                <option value="all">Todos os perfis</option>
                <option value="professor">Docente (Professor)</option>
                <option value="aluno">Aluno (Estudante)</option>
                <option value="gestor">Gestor / Coordenação</option>
                <option value="admin">Administrador</option>
              </select>
            )}

            <select
              className="input"
              value={anonymityFilter}
              onChange={(event) => setAnonymityFilter(event.target.value as AnonymityFilter)}
              aria-label="Filtrar por identificação"
            >
              <option value="all">Todas as origens</option>
              <option value="identified">Identificados</option>
              <option value="anonymous">Anônimos</option>
            </select>

            <select
              className="input"
              value={sortOrder}
              onChange={(event) => setSortOrder(event.target.value as SortOrder)}
              aria-label="Ordenar relatos"
            >
              <option value="desc">Mais recentes primeiro</option>
              <option value="asc">Mais antigos primeiro</option>
            </select>
          </div>

          {/* Result Summary & Clear Action */}
          <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500 dark:text-slate-400">
            <span className="tabular-nums">
              Exibindo {filteredFeedbacks.length} de {feedbacks.length} relato(s)
            </span>
            {hasActiveFilters && (
              <button
                type="button"
                onClick={resetFilters}
                className="inline-flex items-center gap-1 font-medium text-brand-700 dark:text-brand-400 hover:underline"
              >
                <X className="h-3.5 w-3.5" />
                Limpar filtros
              </button>
            )}
          </div>
        </div>
      )}

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

      {!loading && feedbacks.length > 0 && filteredFeedbacks.length === 0 && (
        <div className="py-10 flex flex-col items-center justify-center text-center gap-3 border border-dashed border-slate-200 dark:border-slate-700 rounded-xl bg-slate-50/40 dark:bg-slate-900/40 px-4">
          <Inbox className="h-7 w-7 text-slate-300 dark:text-slate-600" strokeWidth={1.5} />
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Nenhum relato corresponde aos filtros selecionados.
          </p>
          <button type="button" className="btn-secondary text-xs py-1.5 min-h-[34px]" onClick={resetFilters}>
            Limpar filtros
          </button>
        </div>
      )}

      {!loading && filteredFeedbacks.length > 0 && (
        <>
          {/* Mobile Stacked Cards */}
          <div className="md:hidden space-y-3">
            {filteredFeedbacks.map((feedback) => {
              const isAnon = isFeedbackAnonymous(feedback)
              return (
                <article
                  key={feedback.id}
                  className="rounded-xl border border-slate-200/80 dark:border-slate-800 p-4 space-y-2.5 bg-white dark:bg-slate-900"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="text-xs text-slate-600 dark:text-slate-400 flex flex-wrap items-center gap-1 font-medium">
                      <span className="inline-flex items-center gap-1 text-slate-900 dark:text-slate-100">
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
                  <p className="text-sm text-slate-800 dark:text-slate-200 whitespace-pre-line break-words leading-relaxed">
                    {feedback.content}
                  </p>
                  <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
                    <div className="flex flex-wrap items-center gap-1.5">
                      {renderSentimentTag(feedback)}
                      {feedback.has_trigger && !feedback.trigger_resolved_at && (
                        <span className="tag bg-rose-50 text-rose-700 border border-rose-200">
                          <AlertTriangle className="h-3 w-3" />
                          Alerta
                        </span>
                      )}
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
          <div className="hidden md:block overflow-x-auto rounded-lg border border-slate-200/80 dark:border-slate-800">
            <table className="min-w-full divide-y divide-slate-200/80 dark:divide-slate-800 text-sm">
              <thead className="bg-slate-50/80 dark:bg-slate-800/70 text-left text-xs font-semibold text-slate-500 dark:text-slate-400">
                <tr>
                  <th className="px-4 py-3">Autor / Destino</th>
                  <th className="px-4 py-3">Relato</th>
                  <th className="px-4 py-3 whitespace-nowrap">Clima</th>
                  <th className="px-4 py-3 whitespace-nowrap">Data</th>
                  {onDeleteFeedback && <th className="px-4 py-3 text-right">Ação</th>}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800 bg-white dark:bg-slate-900">
                {filteredFeedbacks.map((feedback) => {
                  const isAnon = isFeedbackAnonymous(feedback)
                  return (
                    <tr
                      key={feedback.id}
                      className="hover:bg-slate-50/50 dark:hover:bg-slate-800/60 transition-colors"
                    >
                      <td className="px-4 py-3 align-top whitespace-nowrap">
                        <div className="flex items-center gap-1.5">
                          {isAnon && (
                            <span title="Enviado em modo anônimo">
                              <EyeOff className="h-3.5 w-3.5 text-slate-400 shrink-0" />
                            </span>
                          )}
                          <p className="font-medium text-slate-900 dark:text-slate-100">
                            {formatSender(feedback)}
                          </p>
                        </div>
                        {isAnon && isAdminViewer && feedback.sender_id !== 'anonymous' && (
                          <span className="inline-block mt-1 text-[10px] font-medium px-1.5 py-0.5 rounded bg-amber-50 text-amber-800 border border-amber-200">
                            Modo anônimo · só Admin vê
                          </span>
                        )}
                        <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                          → {formatTarget(feedback)}
                        </p>
                      </td>
                      <td className="px-4 py-3 align-top text-slate-700 dark:text-slate-200 max-w-md">
                        <p className="whitespace-pre-line break-words leading-relaxed">
                          {feedback.content}
                        </p>
                      </td>
                      <td className="px-4 py-3 align-top whitespace-nowrap">
                        <div className="flex flex-wrap items-center gap-1.5">
                          {renderSentimentTag(feedback)}
                          {feedback.has_trigger && !feedback.trigger_resolved_at && (
                            <span className="tag bg-rose-50 text-rose-700 border border-rose-200">
                              <AlertTriangle className="h-3 w-3" />
                              Alerta
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3 align-top whitespace-nowrap text-xs text-slate-500 dark:text-slate-400 tabular-nums">
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
