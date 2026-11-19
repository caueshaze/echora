import { Sparkles } from 'lucide-react'
import type { FeedbackSummary } from '../../lib/types'
import { ExecutiveReport } from './ExecutiveReport'

type InsightSummaryCardProps = {
  summary: FeedbackSummary | null
  summaryLoading: boolean
  summaryStatus: string | null
  onGenerate: () => void
}

export function InsightSummaryCard({
  summary,
  summaryLoading,
  summaryStatus,
  onGenerate,
}: InsightSummaryCardProps) {
  return (
    <div className="card p-5 sm:p-6 space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="space-y-0.5">
          <div className="inline-flex items-center gap-1.5 text-brand-700 text-xs font-semibold">
            <Sparkles className="h-3.5 w-3.5" />
            <span>Maya</span>
          </div>
          <h3 className="text-base sm:text-lg font-semibold text-slate-900">
            Análise da Maya
          </h3>
          <p className="text-sm text-slate-500">
            Diagnóstico do clima escolar e recomendações para a gestão, com base nos relatos selecionados.
          </p>
        </div>
        <button
          type="button"
          className="btn w-full sm:w-auto shrink-0"
          onClick={onGenerate}
          disabled={summaryLoading}
        >
          <Sparkles className={`h-4 w-4 ${summaryLoading ? 'animate-pulse' : ''}`} strokeWidth={1.75} />
          {summaryLoading ? 'Gerando análise...' : 'Gerar análise'}
        </button>
      </div>

      {summaryStatus && (
        <div role="alert" className="rounded-lg bg-rose-50 border border-rose-200/80 px-3.5 py-2.5 text-sm text-rose-700">
          {summaryStatus}
        </div>
      )}

      {summaryLoading && (
        <p role="status" className="inline-flex items-center gap-2 text-sm text-slate-600 animate-fadeIn">
          <Sparkles className="h-4 w-4 text-brand-600 animate-pulse shrink-0" />
          <span>A Maya está analisando os relatos selecionados.</span>
        </p>
      )}

      {summary && (
        <div className="space-y-4 pt-2 border-t border-slate-100 animate-fadeUp">
          {summary.summary_text?.trim() ? <ExecutiveReport text={summary.summary_text} /> : (
            <p className="text-sm text-slate-600">Nenhuma análise foi disponibilizada. Tente gerar novamente.</p>
          )}
        </div>
      )}

      {!summary && !summaryLoading && !summaryStatus && (
        <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50/40 p-6 text-center text-sm text-slate-500">
          Acione <strong className="text-slate-700">Gerar análise</strong> para obter uma leitura dos relatos da escola.
        </div>
      )}
    </div>
  )
}
