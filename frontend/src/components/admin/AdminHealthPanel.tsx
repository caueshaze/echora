import { Activity, Cpu, Database, RefreshCw, Sparkles } from 'lucide-react'
import type { AdminHealthMetrics } from '../../lib/types'

type AdminHealthPanelProps = {
  health: AdminHealthMetrics | null
  loading: boolean
  onRefresh: () => void
}

export function AdminHealthPanel({ health, loading, onRefresh }: AdminHealthPanelProps) {
  const items = [
    {
      label: 'Banco de dados',
      value: health ? `${health.db_latency_ms.toFixed(1)} ms` : '—',
      hint: 'Tempo de resposta de leitura SQL',
      online: Boolean(health),
      icon: Database,
    },
    {
      label: 'Servidor de API',
      value: health ? `${health.api_latency_ms.toFixed(1)} ms` : '—',
      hint: 'Processamento HTTP interno',
      online: Boolean(health),
      icon: Activity,
    },
    {
      label: 'Classificador ONNX',
      value:
        health?.onnx_latency_ms != null ? `${health.onnx_latency_ms.toFixed(1)} ms` : 'Modo léxico',
      hint: 'Análise local de sentimento',
      online: health?.onnx_latency_ms != null,
      icon: Cpu,
    },
    {
      label: 'Motor de Síntese (IA)',
      value:
        health?.gemma_latency_ms != null
          ? `${health.gemma_latency_ms.toFixed(1)} ms`
          : 'Sob demanda (API)',
      hint: 'Serviço de geração de relatórios',
      online: true,
      icon: Sparkles,
    },
  ]

  return (
    <section className="card p-5 sm:p-6 space-y-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-base sm:text-lg font-semibold text-slate-900">
            Diagnóstico de serviços
          </h2>
          <p className="text-sm text-slate-500">
            Verificação em tempo real da latência do banco e dos módulos de análise.
          </p>
        </div>
        <button
          type="button"
          className="btn-secondary text-xs py-2 min-h-[38px] self-start sm:self-auto"
          onClick={onRefresh}
          disabled={loading}
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
          {loading ? 'Verificando...' : 'Testar latência'}
        </button>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        {items.map((item) => {
          const Icon = item.icon
          return (
            <article
              key={item.label}
              className="rounded-xl border border-slate-200/80 bg-slate-50/40 p-4 flex items-start justify-between gap-3"
            >
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span
                    className={`h-2 w-2 rounded-full ${
                      item.online ? 'bg-emerald-500' : 'bg-amber-400'
                    }`}
                  />
                  <p className="text-xs font-semibold text-slate-600">{item.label}</p>
                </div>
                <p className="text-2xl font-bold text-slate-900 tabular-nums">{item.value}</p>
                <p className="text-xs text-slate-500">{item.hint}</p>
              </div>
              <span className="h-9 w-9 rounded-lg bg-white border border-slate-200/80 text-slate-500 grid place-items-center shrink-0">
                <Icon className="h-4 w-4" strokeWidth={1.75} />
              </span>
            </article>
          )
        })}
      </div>

      <p className="text-xs text-slate-400">
        Última checagem:{' '}
        {health?.timestamp ? new Date(health.timestamp).toLocaleString('pt-BR') : '—'}
      </p>
    </section>
  )
}
