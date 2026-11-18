import { Sparkles } from 'lucide-react'
import type { FeedbackSummary } from '../../lib/types'

type PersonalSummaryCardProps = {
  summary: FeedbackSummary | null
  summaryLoading: boolean
  summaryStatus: string | null
  onGenerate: () => void
}

export function PersonalSummaryCard({
  summary,
  summaryLoading,
  summaryStatus,
  onGenerate,
}: PersonalSummaryCardProps) {
  return (
    <section className="card p-5 sm:p-6 space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="space-y-0.5">
          <div className="inline-flex items-center gap-1.5 text-brand-700 text-xs font-semibold">
            <Sparkles className="h-3.5 w-3.5" />
            <span>Síntese Assistida</span>
          </div>
          <h2 className="text-base sm:text-lg font-semibold text-slate-900">
            Leitura consolidada dos feedbacks
          </h2>
          <p className="text-sm text-slate-500">
            Agrupa os pontos recorrentes dos relatos recebidos em uma leitura rápida.
          </p>
        </div>
        <button
          type="button"
          className="btn w-full sm:w-auto shrink-0"
          onClick={onGenerate}
          disabled={summaryLoading}
        >
          <Sparkles className="h-4 w-4" strokeWidth={1.75} />
          {summaryLoading ? 'Analisando relatos...' : 'Gerar síntese'}
        </button>
      </div>

      {summaryStatus && (
        <div className="rounded-lg bg-slate-50 border border-slate-200 px-3.5 py-2.5 text-sm text-slate-600">
          {summaryStatus}
        </div>
      )}

      {summary && (
        <div className="space-y-4 pt-2 border-t border-slate-100">
          <div className="rounded-xl bg-brand-50/50 border border-brand-100 p-4 text-sm leading-relaxed text-slate-800 whitespace-pre-line">
            {summary.summary_text}
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            {summary.positives.length > 0 && (
              <InsightList
                title="Pontos elogiados"
                items={summary.positives}
                tone="positive"
              />
            )}
            {summary.opportunities.length > 0 && (
              <InsightList
                title="Oportunidades de ajuste"
                items={summary.opportunities}
                tone="attention"
              />
            )}
          </div>
        </div>
      )}

      {!summary && !summaryLoading && !summaryStatus && (
        <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50/40 p-6 text-center text-sm text-slate-500">
          Quando houver feedbacks recebidos, clique em <strong className="text-slate-700">Gerar síntese</strong> para consolidar os principais temas.
        </div>
      )}
    </section>
  )
}

function InsightList({
  title,
  items,
  tone,
}: {
  title: string
  items: string[]
  tone: 'positive' | 'attention'
}) {
  const dotColor = tone === 'positive' ? 'bg-emerald-500' : 'bg-amber-500'
  return (
    <div className="rounded-lg border border-slate-200/80 p-4 space-y-2 bg-white">
      <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">{title}</p>
      <ul className="space-y-2 text-sm text-slate-700">
        {items.map((item, index) => (
          <li key={`${title}-${index}`} className="flex items-start gap-2">
            <span className={`h-1.5 w-1.5 rounded-full ${dotColor} mt-2 shrink-0`} />
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
