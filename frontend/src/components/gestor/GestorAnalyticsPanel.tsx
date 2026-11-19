import type { GestorAnalytics, UserAggregate } from '../../hooks/useGestorOverview'

type GestorAnalyticsPanelProps = {
  loading: boolean
  analytics: GestorAnalytics
  onSelectUser: (userId: string) => void
}

type ChartCardProps = {
  title: string
  subtitle: string
  dataset: UserAggregate[]
  metricLabel: string
  metricAccessor: (item: UserAggregate) => number
  colorClass?: string
  onSelectUser: (userId: string) => void
}

function ChartCard({
  title,
  subtitle,
  dataset,
  metricLabel,
  metricAccessor,
  colorClass = 'bg-brand-600',
  onSelectUser,
}: ChartCardProps) {
  const maxValue = dataset.reduce((max, item) => Math.max(max, metricAccessor(item)), 1)
  return (
    <div className="card p-5 space-y-3.5">
      <div>
        <h4 className="text-sm font-semibold text-slate-900">{title}</h4>
        <p className="text-xs text-slate-500 mt-0.5">{subtitle}</p>
      </div>
      {dataset.length === 0 ? (
        <p className="text-xs text-slate-400 py-3">Ainda não há volume suficiente.</p>
      ) : (
        <ul className="space-y-3">
          {dataset.map((item, index) => {
            const value = metricAccessor(item)
            return (
              <li key={item.id} className="space-y-1.5">
                <div className="flex items-center justify-between gap-2 text-sm">
                  <button
                    type="button"
                    className="font-medium text-left text-slate-800 hover:text-brand-700 truncate transition-colors"
                    onClick={() => onSelectUser(item.id)}
                  >
                    {index + 1}. {item.name}
                  </button>
                  <span className="text-xs text-slate-500 tabular-nums shrink-0">
                    {value} {metricLabel}
                  </span>
                </div>
                <div className="h-1.5 rounded-full bg-slate-100 overflow-hidden">
                  <div
                    className={`h-full rounded-full ${colorClass} transition-all duration-700 ease-out`}
                    style={{ width: `${(value / maxValue) * 100}%` }}
                  />
                </div>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}

function ProfessorSentimentCard({
  dataset,
  onSelectUser,
}: {
  dataset: UserAggregate[]
  onSelectUser: (userId: string) => void
}) {
  return (
    <div className="card p-5 space-y-4">
      <div>
        <h4 className="text-sm font-semibold text-slate-900">
          Distribuição de retornos por docente
        </h4>
        <p className="text-xs text-slate-500 mt-0.5">
          Proporção entre relatos positivos, neutros e pontos de atenção.
        </p>
      </div>
      {dataset.length === 0 ? (
        <p className="text-xs text-slate-400 py-3">Sem relatos vinculados a docentes ainda.</p>
      ) : (
        <ul className="space-y-4">
          {dataset.map((item) => {
            const toPercent = (value: number) =>
              item.received === 0 ? 0 : (value / item.received) * 100
            return (
              <li key={item.id} className="space-y-1.5">
                <div className="flex items-center justify-between text-sm">
                  <button
                    type="button"
                    className="font-medium text-left text-slate-800 hover:text-brand-700 transition-colors"
                    onClick={() => onSelectUser(item.id)}
                  >
                    {item.name}
                  </button>
                  <span className="text-xs text-slate-500 tabular-nums">
                    {item.received} relato(s)
                  </span>
                </div>
                <div className="h-2 rounded-full bg-slate-100 overflow-hidden flex">
                  <div
                    className="h-full bg-emerald-500 transition-all duration-700 ease-out"
                    style={{ width: `${toPercent(item.positiveReceived)}%` }}
                    title="Positivos"
                  />
                  <div
                    className="h-full bg-slate-300 dark:bg-slate-600 transition-all duration-700 ease-out"
                    style={{ width: `${toPercent(item.neutralReceived)}%` }}
                    title="Neutros"
                  />
                  <div
                    className="h-full bg-rose-500 transition-all duration-700 ease-out"
                    style={{ width: `${toPercent(item.negativeReceived)}%` }}
                    title="Atenção"
                  />
                </div>
                <div className="flex flex-wrap gap-3 text-[11px] text-slate-500 tabular-nums">
                  <span className="inline-flex items-center gap-1">
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                    Positivos: {item.positiveReceived}
                  </span>
                  <span className="inline-flex items-center gap-1">
                    <span className="h-1.5 w-1.5 rounded-full bg-slate-300" />
                    Neutros: {item.neutralReceived}
                  </span>
                  <span className="inline-flex items-center gap-1">
                    <span className="h-1.5 w-1.5 rounded-full bg-rose-500" />
                    Atenção: {item.negativeReceived}
                  </span>
                </div>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}

export function GestorAnalyticsPanel({
  loading,
  analytics,
  onSelectUser,
}: GestorAnalyticsPanelProps) {
  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between gap-2">
        <div>
          <h3 className="text-base sm:text-lg font-semibold text-slate-900">
            Participação e demanda de acompanhamento
          </h3>
          <p className="text-xs sm:text-sm text-slate-500">
            Toque em qualquer nome para consultar o histórico individual.
          </p>
        </div>
        {loading && <span className="text-xs text-slate-400">Sincronizando...</span>}
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <ChartCard
          title="Maior participação (envios)"
          subtitle="Quem mais registrou percepções recentemente."
          dataset={analytics.topSenders}
          metricLabel="envios"
          metricAccessor={(item) => item.sent}
          onSelectUser={onSelectUser}
        />
        <ChartCard
          title="Mais mencionados (recebidos)"
          subtitle="Pessoas com maior volume de retornos diretos."
          dataset={analytics.topRecipients}
          metricLabel="recebidos"
          metricAccessor={(item) => item.received}
          onSelectUser={onSelectUser}
        />
        <ChartCard
          title="Estudantes com destaques positivos"
          subtitle="Alunos que mais receberam reconhecimentos."
          dataset={analytics.praisedStudents}
          metricLabel="elogios"
          metricAccessor={(item) => item.positiveReceived}
          colorClass="bg-emerald-500"
          onSelectUser={onSelectUser}
        />
        <ChartCard
          title="Docentes mais reconhecidos"
          subtitle="Professores com maior volume de elogios."
          dataset={analytics.praisedTeachers}
          metricLabel="elogios"
          metricAccessor={(item) => item.positiveReceived}
          colorClass="bg-emerald-600"
          onSelectUser={onSelectUser}
        />
        <ChartCard
          title="Estudantes que pedem atenção"
          subtitle="Alunos com maior incidência de apontamentos críticos."
          dataset={analytics.pressuredStudents}
          metricLabel="alertas"
          metricAccessor={(item) => item.negativeReceived}
          colorClass="bg-amber-500"
          onSelectUser={onSelectUser}
        />
        <ChartCard
          title="Docentes sob maior demanda"
          subtitle="Educadores que podem precisar de apoio pedagógico."
          dataset={analytics.pressuredTeachers}
          metricLabel="apontamentos"
          metricAccessor={(item) => item.negativeReceived}
          colorClass="bg-rose-500"
          onSelectUser={onSelectUser}
        />
      </div>

      <ProfessorSentimentCard
        dataset={analytics.professorSentiments}
        onSelectUser={onSelectUser}
      />
    </section>
  )
}
