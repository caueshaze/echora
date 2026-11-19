import { useEffect, useState } from 'react'
import { AlertTriangle, X } from 'lucide-react'

type ActionModalProps = {
  open: boolean
  mode: 'confirm' | 'prompt'
  title: string
  description?: string
  confirmLabel?: string
  cancelLabel?: string
  tone?: 'brand' | 'danger'
  inputLabel?: string
  inputPlaceholder?: string
  minLength?: number
  optional?: boolean
  loading?: boolean
  onConfirm: (value: string) => void | Promise<void>
  onClose: () => void
}

export function ActionModal({
  open,
  mode,
  title,
  description,
  confirmLabel = 'Confirmar',
  cancelLabel = 'Cancelar',
  tone = 'brand',
  inputLabel,
  inputPlaceholder = 'Digite aqui...',
  minLength = 0,
  optional = false,
  loading = false,
  onConfirm,
  onClose,
}: ActionModalProps) {
  const [value, setValue] = useState('')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!open) return
    setValue('')
    setError(null)
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !loading) {
        onClose()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => {
      document.body.style.overflow = previousOverflow
      window.removeEventListener('keydown', handleKeyDown)
    }
  }, [open, loading, onClose])

  if (!open) return null

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const trimmed = value.trim()
    if (mode === 'prompt') {
      if (!optional && trimmed.length === 0) {
        setError('Preencha este campo antes de continuar.')
        return
      }
      if (!optional && minLength > 0 && trimmed.length < minLength) {
        setError(`Informe pelo menos ${minLength} caracteres.`)
        return
      }
    }
    setError(null)
    void onConfirm(trimmed)
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="action-modal-title"
    >
      <button
        type="button"
        className="fixed inset-0 bg-slate-900/45 dark:bg-slate-950/70 backdrop-blur-[1px] animate-fadeIn"
        onClick={() => {
          if (!loading) onClose()
        }}
        aria-label="Fechar janela"
      />

      <form
        onSubmit={handleSubmit}
        className="relative z-10 w-full sm:max-w-md bg-white dark:bg-slate-900 rounded-t-2xl sm:rounded-2xl shadow-elevated border border-slate-200 dark:border-slate-800 overflow-hidden animate-slideUpModal"
      >
        <div className="px-5 py-4 border-b border-slate-100 dark:border-slate-800 flex items-start justify-between gap-3">
          <div className="flex items-start gap-2.5">
            {tone === 'danger' && (
              <span className="h-8 w-8 rounded-lg bg-rose-50 dark:bg-rose-950/60 text-rose-600 dark:text-rose-400 grid place-items-center shrink-0 mt-0.5">
                <AlertTriangle className="h-4 w-4" />
              </span>
            )}
            <div>
              <h3 id="action-modal-title" className="text-base font-bold text-slate-900 dark:text-slate-100">
                {title}
              </h3>
              {description && (
                <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1 leading-relaxed">
                  {description}
                </p>
              )}
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={loading}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            aria-label="Fechar"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {mode === 'prompt' && (
          <div className="p-5 space-y-2">
            {inputLabel && (
              <label htmlFor="action-modal-input" className="label">
                {inputLabel}
              </label>
            )}
            <textarea
              id="action-modal-input"
              className="input min-h-[92px] resize-y"
              placeholder={inputPlaceholder}
              value={value}
              onChange={(event) => {
                setValue(event.target.value)
                if (error) setError(null)
              }}
              disabled={loading}
              autoFocus
            />
            {error && <p className="text-xs font-medium text-rose-600">{error}</p>}
          </div>
        )}

        <div className="px-5 py-3.5 border-t border-slate-100 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-900/60 flex flex-col-reverse sm:flex-row sm:justify-end gap-2 pb-safe">
          <button
            type="button"
            onClick={onClose}
            disabled={loading}
            className="btn-secondary w-full sm:w-auto"
          >
            {cancelLabel}
          </button>
          <button
            type="submit"
            disabled={loading}
            className={
              tone === 'danger'
                ? 'inline-flex items-center justify-center gap-2 min-h-[42px] px-4 py-2.5 rounded-lg text-sm font-medium text-white bg-rose-600 hover:bg-rose-700 active:bg-rose-800 transition-all duration-150 active:scale-[0.98] disabled:opacity-50 w-full sm:w-auto'
                : 'btn w-full sm:w-auto'
            }
          >
            {loading ? 'Processando...' : confirmLabel}
          </button>
        </div>
      </form>
    </div>
  )
}
