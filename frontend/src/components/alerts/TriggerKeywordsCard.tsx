import { useState } from 'react'
import { Plus, Shield, X } from 'lucide-react'

import type { TriggerKeyword } from '../../lib/types'

type TriggerKeywordsCardProps = {
  keywords: TriggerKeyword[]
  loading: boolean
  error: string | null
  status: string | null
  submitting: boolean
  scopeLabel: string
  onAdd: (keyword: string) => Promise<void> | void
  onDelete: (keywordId: number) => Promise<void> | void
}

export function TriggerKeywordsCard({
  keywords,
  loading,
  error,
  status,
  submitting,
  scopeLabel,
  onAdd,
  onDelete,
}: TriggerKeywordsCardProps) {
  const [keywordInput, setKeywordInput] = useState('')

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const trimmed = keywordInput.trim().toLowerCase()
    if (!trimmed) return
    await onAdd(trimmed)
    setKeywordInput('')
  }

  return (
    <div className="card p-5 sm:p-6 flex flex-col gap-4">
      <div>
        <div className="flex items-center gap-2 text-slate-900 font-semibold">
          <Shield className="h-4 w-4 text-brand-700 shrink-0" />
          <h3 className="text-base">Termos sensíveis monitorados</h3>
        </div>
        <p className="text-sm text-slate-500 mt-1">
          Palavras que geram sinalização preventiva automática para {scopeLabel}.
        </p>
      </div>

      <form className="flex flex-col sm:flex-row gap-2" onSubmit={handleSubmit}>
        <input
          className="input flex-1"
          placeholder="Adicionar termo (ex.: bullying, ameaça)..."
          value={keywordInput}
          onChange={(event) => setKeywordInput(event.target.value)}
          disabled={submitting}
          aria-label="Novo termo monitorado"
          required
        />
        <button type="submit" className="btn shrink-0" disabled={submitting}>
          <Plus className="h-4 w-4" />
          {submitting ? 'Salvando...' : 'Adicionar'}
        </button>
      </form>

      {status && <p className="text-xs text-slate-500">{status}</p>}
      {error && <p className="text-xs text-rose-600">{error}</p>}
      {loading && <p className="text-sm text-slate-500">Carregando termos...</p>}

      {!loading && keywords.length === 0 && (
        <p className="text-sm text-slate-500">
          Nenhum termo personalizado cadastrado. Os termos padrão de segurança seguem ativos.
        </p>
      )}

      {!loading && keywords.length > 0 && (
        <ul className="flex flex-wrap gap-2">
          {keywords.map((keyword) => (
            <li
              key={keyword.id}
              className="inline-flex items-center gap-1.5 rounded-lg bg-slate-100 border border-slate-200 px-2.5 py-1 text-xs font-medium text-slate-700"
            >
              <span>{keyword.keyword}</span>
              <button
                type="button"
                className="p-0.5 rounded text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors"
                onClick={() => onDelete(keyword.id)}
                disabled={submitting}
                aria-label={`Remover ${keyword.keyword}`}
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
