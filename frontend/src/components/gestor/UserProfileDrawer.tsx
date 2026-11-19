import { useEffect } from 'react'
import { X } from 'lucide-react'
import { FeedbackCard } from '../feedback/FeedbackCard'
import type { FeedbackPublic } from '../../lib/types'
import type { UserAggregate } from '../../hooks/useGestorOverview'

type UserProfileDrawerProps = {
  profile: UserAggregate | null
  onClose: () => void
  sentFeedbacks: FeedbackPublic[]
  receivedFeedbacks: FeedbackPublic[]
}

const ROLE_LABELS: Record<string, string> = {
  admin: 'Administrador',
  gestor: 'Gestor(a)',
  professor: 'Professor(a)',
  aluno: 'Aluno(a)',
}

export function UserProfileDrawer({
  profile,
  onClose,
  sentFeedbacks,
  receivedFeedbacks,
}: UserProfileDrawerProps) {
  useEffect(() => {
    if (!profile) return
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => {
      document.body.style.overflow = previousOverflow
      window.removeEventListener('keydown', handleKeyDown)
    }
  }, [profile, onClose])

  if (!profile) return null

  const roleLabel = profile.role ? ROLE_LABELS[profile.role] || profile.role : 'Usuário'

  return (
    <div className="fixed inset-0 z-50 flex justify-end" role="dialog" aria-modal="true">
      <button
        type="button"
        className="fixed inset-0 bg-slate-900/40 dark:bg-slate-950/70 backdrop-blur-[1px] animate-fadeIn"
        onClick={onClose}
        aria-label="Fechar histórico do usuário"
      />
      <div className="relative z-10 w-full max-w-md bg-white dark:bg-slate-900 shadow-elevated h-full overflow-y-auto p-5 sm:p-6 space-y-6 animate-slideInRight">
        <div className="flex items-start justify-between gap-4 border-b border-slate-100 pb-4">
          <div className="min-w-0">
            <span className="inline-block text-[11px] font-semibold px-2 py-0.5 rounded bg-brand-50 text-brand-800 mb-1">
              {roleLabel}
            </span>
            <h3 className="text-xl font-bold text-slate-900 truncate">{profile.name}</h3>
            {profile.email && <p className="text-xs text-slate-500 truncate">{profile.email}</p>}
          </div>
          <button
            type="button"
            className="p-2 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100"
            onClick={onClose}
            aria-label="Fechar"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="grid grid-cols-2 gap-2.5">
          <div className="rounded-lg border border-slate-200 p-3 bg-slate-50/50">
            <p className="text-xs text-slate-500">Enviados</p>
            <p className="text-xl font-bold text-slate-900 tabular-nums">{profile.sent}</p>
          </div>
          <div className="rounded-lg border border-slate-200 p-3 bg-slate-50/50">
            <p className="text-xs text-slate-500">Recebidos</p>
            <p className="text-xl font-bold text-slate-900 tabular-nums">{profile.received}</p>
          </div>
          <div className="rounded-lg border border-emerald-200/80 bg-emerald-50/40 p-3">
            <p className="text-xs text-emerald-700">Positivos</p>
            <p className="text-xl font-bold text-emerald-800 tabular-nums">
              {profile.positiveReceived}
            </p>
          </div>
          <div className="rounded-lg border border-rose-200/80 bg-rose-50/40 p-3">
            <p className="text-xs text-rose-700">Atenção</p>
            <p className="text-xl font-bold text-rose-800 tabular-nums">
              {profile.negativeReceived}
            </p>
          </div>
        </div>

        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <h4 className="text-sm font-semibold text-slate-900">Últimos recebidos</h4>
            <span className="text-xs text-slate-400">Até 5 registros</span>
          </div>
          {receivedFeedbacks.length === 0 ? (
            <p className="text-sm text-slate-500">Nenhum relato recebido.</p>
          ) : (
            <div className="space-y-2.5">
              {receivedFeedbacks.slice(0, 5).map((feedback) => (
                <FeedbackCard key={feedback.id} feedback={feedback} badge="Recebido" />
              ))}
            </div>
          )}
        </section>

        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <h4 className="text-sm font-semibold text-slate-900">Últimos enviados</h4>
            <span className="text-xs text-slate-400">Até 5 registros</span>
          </div>
          {sentFeedbacks.length === 0 ? (
            <p className="text-sm text-slate-500">Nenhum relato enviado.</p>
          ) : (
            <div className="space-y-2.5">
              {sentFeedbacks.slice(0, 5).map((feedback) => (
                <FeedbackCard key={feedback.id} feedback={feedback} badge="Enviado" />
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  )
}
