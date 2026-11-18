import { RefreshCw } from 'lucide-react'
import { OverviewMetricsGrid } from './OverviewMetricsGrid'

type GestorOverviewSectionProps = {
  stats: { total: number; positivo: number; neutro: number; negativo: number; triggers: number }
  loading: boolean
  notice: string | null
  onRefresh: () => void
}

export function GestorOverviewSection({
  stats,
  loading,
  notice,
  onRefresh,
}: GestorOverviewSectionProps) {
  return (
    <section className="card p-5 sm:p-6 space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-base sm:text-lg font-semibold text-slate-900">
            Clima da unidade escolar
          </h2>
          <p className="text-sm text-slate-500">
            Consolidado dos relatos registrados recentemente.
          </p>
        </div>
        <button
          type="button"
          className="btn-secondary text-xs py-2 min-h-[36px] shrink-0"
          onClick={onRefresh}
          disabled={loading}
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span className="hidden sm:inline">{loading ? 'Atualizando...' : 'Atualizar'}</span>
        </button>
      </div>
      {notice && <p className="text-sm text-slate-500">{notice}</p>}
      <OverviewMetricsGrid stats={stats} />
    </section>
  )
}
