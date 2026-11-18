import { AlertTriangle, ArrowRight, CheckCircle2, EyeOff, Flag } from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import type { FeedbackPublic } from '../../lib/types'

type FeedbackCardProps = {
  feedback: FeedbackPublic
  badge?: string
  hideClassification?: boolean
  showTriggerBadge?: boolean
}

const SENTIMENT_STYLES: Record<
  string,
  { dot: string; badge: string; text: string }
> = {
  positivo: {
    dot: 'bg-emerald-500',
    badge: 'tag-pos',
    text: 'Positivo',
  },
  neutro: {
    dot: 'bg-slate-400',
    badge: 'tag-neu',
    text: 'Neutro',
  },
  negativo: {
    dot: 'bg-rose-500',
    badge: 'tag-neg',
    text: 'Atenção',
  },
}

export function FeedbackCard({
  feedback,
  badge,
  hideClassification,
  showTriggerBadge = true,
}: FeedbackCardProps) {
  const { session } = useAuth()
  const isAdminViewer = session?.backendRole === 'admin'
  const isAnonymous = Boolean(feedback.is_anonymous) || feedback.sender_id === 'anonymous'
  const isMaskedSender = feedback.sender_id === 'anonymous'

  const timestamp = new Date(feedback.created_at)
  const sentimentKey = (feedback.sentiment_label || feedback.sentiment || '').toLowerCase()
  const sentimentStyle =
    SENTIMENT_STYLES[sentimentKey] ??
    (feedback.sentiment_label ? SENTIMENT_STYLES.neutro : null)
  const sentimentScore =
    typeof feedback.sentiment_score === 'number'
      ? `${Math.round(feedback.sentiment_score * 100)}%`
      : null

  const senderLabel = isMaskedSender
    ? 'Estudante (Anônimo)'
    : feedback.sender_name || `Usuário #${feedback.sender_id.slice(0, 6)}`
  const targetLabel =
    feedback.target_type === 'class'
      ? `Turma · ${feedback.target_name || `#${feedback.target_id}`}`
      : feedback.target_type === 'subject'
        ? `${feedback.target_name || `Matéria #${feedback.target_id}`}`
        : feedback.target_name || `Destinatário #${feedback.target_id.slice(0, 6)}`

  return (
    <article className="p-4 sm:p-5 rounded-xl border border-slate-200/80 bg-white space-y-3 transition-colors hover:border-slate-300/80">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between text-xs text-slate-500">
        <div className="flex flex-wrap items-center gap-1.5 font-medium text-slate-700">
          <span className="inline-flex items-center gap-1 truncate max-w-[210px] sm:max-w-none">
            {isAnonymous && <EyeOff className="h-3.5 w-3.5 text-slate-400 shrink-0" />}
            {senderLabel}
          </span>
          <ArrowRight className="h-3.5 w-3.5 text-slate-400 shrink-0" />
          <span className="text-slate-600 truncate max-w-[200px] sm:max-w-none">{targetLabel}</span>
        </div>
        <time className="text-[11px] text-slate-400 tabular-nums shrink-0">
          {timestamp.toLocaleDateString('pt-BR', {
            day: '2-digit',
            month: 'short',
            hour: '2-digit',
            minute: '2-digit',
          })}
        </time>
      </div>

      <p className="text-sm sm:text-[15px] leading-relaxed text-slate-800 whitespace-pre-line">
        {feedback.content}
      </p>

      <div className="flex flex-wrap items-center gap-2 pt-1">
        {badge && (
          <span className="tag bg-slate-100 text-slate-600 border border-slate-200/60">
            {badge}
          </span>
        )}
        {isAnonymous && !isMaskedSender && isAdminViewer && (
          <span className="tag bg-amber-50 text-amber-800 border border-amber-200">
            <EyeOff className="h-3 w-3" />
            Modo anônimo · autor visível só ao Admin
          </span>
        )}
        {isAnonymous && !isMaskedSender && !isAdminViewer && (
          <span className="tag bg-brand-50 text-brand-800 border border-brand-200/70">
            <EyeOff className="h-3 w-3" />
            Enviado como anônimo
          </span>
        )}
        {sentimentStyle && !hideClassification && (
          <span className={`tag ${sentimentStyle.badge}`}>
            <span className={`h-1.5 w-1.5 rounded-full ${sentimentStyle.dot}`} />
            {sentimentStyle.text}
            {sentimentScore ? ` · ${sentimentScore}` : ''}
          </span>
        )}
        {feedback.category && (
          <span className="tag bg-brand-50 text-brand-800 border border-brand-200/60 capitalize">
            {feedback.category}
          </span>
        )}
        {showTriggerBadge && feedback.has_trigger && !feedback.trigger_resolved_at && (
          <span className="tag bg-rose-50 text-rose-700 border border-rose-200">
            <AlertTriangle className="h-3 w-3" />
            Alerta de atenção
          </span>
        )}
        {showTriggerBadge && feedback.manual_trigger_reason && (
          <span className="tag bg-amber-50 text-amber-800 border border-amber-200">
            <Flag className="h-3 w-3" />
            Sinalizado: {feedback.manual_trigger_reason}
          </span>
        )}
        {showTriggerBadge && feedback.trigger_resolved_at && (
          <span className="tag bg-emerald-50 text-emerald-700 border border-emerald-200">
            <CheckCircle2 className="h-3 w-3" />
            Caso acompanhado
          </span>
        )}
      </div>
    </article>
  )
}
