import { Pencil, Trash2 } from 'lucide-react'
import type { School, SchoolCreateInput } from '../../lib/types'

type SchoolsCatalogCardProps = {
  schools: School[]
  loading: boolean
  error: string | null
  form: SchoolCreateInput
  onChange: (updates: Partial<SchoolCreateInput>) => void
  formMode: 'create' | 'edit'
  submitting: boolean
  statusMessage: string | null
  onSubmit: (event: React.FormEvent<HTMLFormElement>) => void
  onEdit: (school: School) => void
  onDelete: (schoolId: number) => void
  onReset: () => void
}

export function SchoolsCatalogCard({
  schools,
  loading,
  error,
  form,
  onChange,
  formMode,
  submitting,
  statusMessage,
  onSubmit,
  onEdit,
  onDelete,
  onReset,
}: SchoolsCatalogCardProps) {
  return (
    <div className="space-y-6">
      <div className="card p-5 sm:p-6 space-y-5">
        <div>
          <h3 className="text-base sm:text-lg font-semibold text-slate-900">
            {formMode === 'edit' ? 'Editar unidade escolar' : 'Cadastrar unidade escolar'}
          </h3>
          <p className="text-sm text-slate-500">
            Registre novas unidades ou atualize os dados institucionais.
          </p>
        </div>

        <form className="grid gap-4 sm:grid-cols-2" onSubmit={onSubmit}>
          <div>
            <label className="label" htmlFor="school_name">
              Nome da instituição
            </label>
            <input
              id="school_name"
              className="input"
              value={form.name}
              onChange={(event) => onChange({ name: event.target.value })}
              disabled={submitting}
              required
            />
          </div>
          <div>
            <label className="label" htmlFor="school_code">
              Código identificador
            </label>
            <input
              id="school_code"
              className="input"
              value={form.code ?? ''}
              onChange={(event) => onChange({ code: event.target.value })}
              disabled={submitting}
            />
          </div>
          <div className="sm:col-span-2 flex flex-wrap items-center justify-between gap-3 pt-1">
            <div>
              {statusMessage && <p className="text-sm text-slate-600">{statusMessage}</p>}
              {error && <p className="text-sm text-rose-600">{error}</p>}
            </div>
            <div className="flex gap-2 w-full sm:w-auto">
              {formMode === 'edit' && (
                <button
                  type="button"
                  className="btn-secondary flex-1 sm:flex-initial"
                  onClick={onReset}
                >
                  Cancelar
                </button>
              )}
              <button
                type="submit"
                className="btn flex-1 sm:flex-initial"
                disabled={submitting}
              >
                {submitting ? 'Salvando...' : formMode === 'edit' ? 'Atualizar' : 'Cadastrar'}
              </button>
            </div>
          </div>
        </form>
      </div>

      <div className="card p-5 sm:p-6 space-y-4">
        <h3 className="text-base font-semibold text-slate-900">
          Unidades cadastradas ({schools.length})
        </h3>
        {loading ? (
          <p className="text-sm text-slate-500">Carregando unidades...</p>
        ) : schools.length === 0 ? (
          <p className="text-sm text-slate-500 py-6 text-center border border-dashed border-slate-200 rounded-xl">
            Nenhuma unidade cadastrada.
          </p>
        ) : (
          <ul className="divide-y divide-slate-100 rounded-xl border border-slate-200/80 overflow-hidden bg-white">
            {schools.map((school) => (
              <li
                key={school.id}
                className="p-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 hover:bg-slate-50/40"
              >
                <div className="flex items-center gap-2 min-w-0">
                  <p className="text-sm font-semibold text-slate-900 truncate">{school.name}</p>
                  {school.code && (
                    <span className="text-[11px] font-medium px-2 py-0.5 rounded bg-slate-100 text-slate-600">
                      {school.code}
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  <button
                    className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-slate-200 text-xs font-medium text-slate-700 hover:bg-slate-50"
                    type="button"
                    onClick={() => onEdit(school)}
                  >
                    <Pencil className="h-3 w-3" />
                    Editar
                  </button>
                  <button
                    className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-rose-200 text-xs font-medium text-rose-700 hover:bg-rose-50"
                    type="button"
                    onClick={() => onDelete(school.id)}
                  >
                    <Trash2 className="h-3 w-3" />
                    Excluir
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
