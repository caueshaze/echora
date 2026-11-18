type OverviewStats = {
  total: number
  positivo: number
  neutro: number
  negativo: number
  triggers: number
}

export function OverviewMetricsGrid({ stats }: { stats: OverviewStats }) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
      <MetricCard label="Total monitorado" value={stats.total} accent="border-l-slate-400" />
      <MetricCard label="Positivos" value={stats.positivo} accent="border-l-emerald-500" />
      <MetricCard label="Neutros" value={stats.neutro} accent="border-l-slate-300" />
      <MetricCard label="Atenção" value={stats.negativo} accent="border-l-amber-500" />
      <MetricCard
        label="Alertas ativos"
        value={stats.triggers}
        accent={stats.triggers > 0 ? 'border-l-rose-600' : 'border-l-slate-200'}
        highlight={stats.triggers > 0}
      />
    </div>
  )
}

function MetricCard({
  label,
  value,
  accent,
  highlight = false,
}: {
  label: string
  value: number
  accent: string
  highlight?: boolean
}) {
  return (
    <div
      className={`rounded-lg border border-l-4 ${accent} p-3.5 ${
        highlight
          ? 'border-rose-200 bg-rose-50/40'
          : 'border-slate-200/80 bg-slate-50/40'
      }`}
    >
      <p className="text-xs font-medium text-slate-500">{label}</p>
      <p
        className={`text-2xl font-bold mt-1 tabular-nums ${
          highlight ? 'text-rose-700' : 'text-slate-900'
        }`}
      >
        {value}
      </p>
    </div>
  )
}
