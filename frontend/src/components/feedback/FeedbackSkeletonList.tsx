export function FeedbackSkeletonList({
  count = 3,
  label = 'Carregando registros...',
}: {
  count?: number
  label?: string
}) {
  return (
    <div className="space-y-3" role="status" aria-live="polite">
      <span className="sr-only">{label}</span>
      {Array.from({ length: count }).map((_, index) => (
        <div
          key={`skeleton-${index}`}
          aria-hidden="true"
          className="rounded-xl border border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 sm:p-5 space-y-3 animate-pulse"
        >
          <div className="flex items-center justify-between gap-3">
            <div className="h-3.5 w-44 rounded bg-slate-200/80 dark:bg-slate-800" />
            <div className="h-3 w-20 rounded bg-slate-200/70 dark:bg-slate-800/80" />
          </div>
          <div className="space-y-2">
            <div className="h-3.5 w-full rounded bg-slate-200/70 dark:bg-slate-800" />
            <div className="h-3.5 w-4/5 rounded bg-slate-200/60 dark:bg-slate-800/70" />
          </div>
          <div className="flex items-center gap-2 pt-1">
            <div className="h-5 w-16 rounded-md bg-slate-200/70 dark:bg-slate-800" />
            <div className="h-5 w-24 rounded-md bg-slate-200/60 dark:bg-slate-800/80" />
          </div>
        </div>
      ))}
    </div>
  )
}
