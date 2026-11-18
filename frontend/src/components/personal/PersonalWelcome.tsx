import { ArrowUpRight, Check } from 'lucide-react'

type PersonalWelcomeProps<T extends string> = {
  roleLabel: string
  tips: string[]
  actions: Array<{ label: string; target: T; description: string }>
  onNavigate: (target: T) => void
}

export function PersonalWelcome<T extends string>({
  roleLabel,
  tips,
  actions,
  onNavigate,
}: PersonalWelcomeProps<T>) {
  const firstName = roleLabel.split(' ')[0] || roleLabel

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2">
        {actions.map((action) => (
          <button
            key={action.target}
            type="button"
            className="card p-5 text-left group hover:border-brand-500/60 transition-all flex items-start justify-between gap-3"
            onClick={() => onNavigate(action.target)}
          >
            <div className="space-y-1">
              <p className="text-base font-semibold text-slate-900 group-hover:text-brand-700 transition-colors">
                {action.label}
              </p>
              <p className="text-sm text-slate-500 leading-relaxed">{action.description}</p>
            </div>
            <span className="h-8 w-8 rounded-lg bg-slate-50 group-hover:bg-brand-50 text-slate-400 group-hover:text-brand-700 grid place-items-center shrink-0 transition-colors">
              <ArrowUpRight className="h-4 w-4" strokeWidth={2} />
            </span>
          </button>
        ))}
      </div>

      <section className="card p-5 space-y-3">
        <p className="text-sm font-semibold text-slate-800">
          Bom dia de trabalho, {firstName}. Orientações rápidas:
        </p>
        <ul className="grid gap-2.5 text-sm text-slate-600 sm:grid-cols-3">
          {tips.map((tip, index) => (
            <li
              key={`tip-${index}`}
              className="flex items-start gap-2.5 rounded-lg bg-slate-50/80 p-3 border border-slate-100"
            >
              <Check className="h-4 w-4 text-brand-600 shrink-0 mt-0.5" strokeWidth={2} />
              <span className="leading-snug">{tip}</span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}
