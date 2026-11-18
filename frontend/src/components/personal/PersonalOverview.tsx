type PersonalOverviewProps = {
  stats: { total: number; positivo: number; neutro: number; negativo: number }
  notice: string | null
  loading: boolean
}

export function PersonalOverview({ stats, notice, loading }: PersonalOverviewProps) {
  return (
    <section className="card p-5 sm:p-6 space-y-4">
      <div>
        <h2 className="text-base sm:text-lg font-semibold text-slate-900">Panorama de retornos</h2>
        <p className="text-sm text-slate-500">Distribuição dos relatos recebidos no seu perfil.</p>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <MetricCard label="Total recebidos" value={stats.total} accent="border-l-slate-400" />
        <MetricCard label="Positivos" value={stats.positivo} accent="border-l-emerald-500" />
        <MetricCard label="Neutros" value={stats.neutro} accent="border-l-slate-300" />
        <MetricCard label="Atenção" value={stats.negativo} accent="border-l-rose-500" />
      </div>

      {loading && <p className="text-xs text-slate-500">Atualizando indicadores...</p>}
      {notice && !loading && <p className="text-sm text-slate-500">{notice}</p>}
    </section>
  )
}

function MetricCard({
  label,
  value,
  accent,
}: {
  label: string
  value: number
  accent: string
}) {
  return (
    <div className={`rounded-lg border border-slate-200/80 border-l-4 ${accent} bg-slate-50/40 p-3.5`}>
      <p className="text-xs font-medium text-slate-500">{label}</p>
      <p className="text-2xl font-bold text-slate-900 mt-1 tabular-nums">{value}</p>
    </div>
  )
}
