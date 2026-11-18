import { Pencil, Trash2 } from 'lucide-react'
import type { School, Subject } from '../../lib/types'
import type { SubjectFormState } from '../../hooks/useGestorDirectory'

type SubjectsCatalogCardProps = {
  subjects: Subject[]
  loading: boolean
  error: string | null
  form: SubjectFormState
  onChange: (updates: Partial<SubjectFormState>) => void
  formMode: 'create' | 'edit'
  submitting: boolean
  statusMessage: string | null
  onSubmit: (event: React.FormEvent<HTMLFormElement>) => void
  onEdit: (subject: Subject) => void
  onDelete: (subjectId: number) => void
  onReset: () => void
  visibleSchools: School[]
  schoolMap: Record<number, School>
}

export function SubjectsCatalogCard({
  subjects,
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
  visibleSchools,
  schoolMap,
}: SubjectsCatalogCardProps) {
  return (
    <div className="space-y-6">
      <div className="card p-5 sm:p-6 space-y-5">
        <div>
          <h3 className="text-base sm:text-lg font-semibold text-slate-900">
            {formMode === 'edit' ? 'Editar matéria' : 'Cadastrar matéria'}
          </h3>
          <p className="text-sm text-slate-500">
            Configure as disciplinas ofertadas na sua unidade escolar.
          </p>
        </div>

        <form className="grid gap-4 sm:grid-cols-2" onSubmit={onSubmit}>
          <div>
            <label className="label" htmlFor="subject_name">
              Nome da disciplina
            </label>
            <input
              id="subject_name"
              className="input"
              placeholder="Ex.: Matemática"
              value={form.name}
              onChange={(event) => onChange({ name: event.target.value })}
              disabled={submitting}
              required
            />
          </div>
          <div>
            <label className="label" htmlFor="subject_code">
              Sigla / Código
            </label>
            <input
              id="subject_code"
              className="input"
              placeholder="Ex.: MAT"
              value={form.code}
              onChange={(event) => onChange({ code: event.target.value })}
              disabled={submitting}
            />
          </div>
          <div>
            <label className="label" htmlFor="subject_school">
              Unidade escolar
            </label>
            {visibleSchools.length > 1 ? (
              <select
                id="subject_school"
                className="input"
                value={form.school_id}
                onChange={(event) => onChange({ school_id: event.target.value })}
                disabled={submitting}
                required
              >
                <option value="">Selecione...</option>
                {visibleSchools.map((school) => (
                  <option key={school.id} value={school.id}>
                    {school.name}
                  </option>
                ))}
              </select>
            ) : (
              <div className="input flex items-center bg-slate-50 text-slate-600">
                <span>{visibleSchools[0]?.name || 'Unidade vinculada'}</span>
              </div>
            )}
          </div>
          <div>
            <label className="label" htmlFor="subject_color">
              Cor de identificação
            </label>
            <input
              id="subject_color"
              type="color"
              className="h-[42px] w-20 rounded-lg border border-slate-200 bg-white p-1 cursor-pointer"
              value={form.color || '#0f766e'}
              onChange={(event) => onChange({ color: event.target.value })}
              disabled={submitting}
            />
          </div>
          <div className="sm:col-span-2">
            <label className="label" htmlFor="subject_description">
              Ementa / Observações (opcional)
            </label>
            <textarea
              id="subject_description"
              className="input min-h-[76px]"
              value={form.description}
              onChange={(event) => onChange({ description: event.target.value })}
              disabled={submitting}
              placeholder="Breve descrição da disciplina..."
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
          Matérias cadastradas ({subjects.length})
        </h3>
        {loading ? (
          <p className="text-sm text-slate-500">Carregando matérias...</p>
        ) : subjects.length === 0 ? (
          <p className="text-sm text-slate-500 py-6 text-center border border-dashed border-slate-200 rounded-xl">
            Nenhuma matéria cadastrada até o momento.
          </p>
        ) : (
          <ul className="divide-y divide-slate-100 rounded-xl border border-slate-200/80 overflow-hidden bg-white">
            {subjects.map((subject) => (
              <li
                key={subject.id}
                className="p-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 hover:bg-slate-50/40"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <span
                    className="h-3.5 w-3.5 rounded-full shrink-0 border border-black/10"
                    style={{ backgroundColor: subject.color || '#0f766e' }}
                  />
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-semibold text-slate-900 truncate">
                        {subject.name}
                      </p>
                      {subject.code && (
                        <span className="text-[11px] font-medium px-2 py-0.5 rounded bg-slate-100 text-slate-600">
                          {subject.code}
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-slate-500 truncate">
                      {schoolMap[subject.school_id]?.name ?? 'Unidade escolar'}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  <button
                    className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-slate-200 text-xs font-medium text-slate-700 hover:bg-slate-50"
                    type="button"
                    onClick={() => onEdit(subject)}
                  >
                    <Pencil className="h-3 w-3" />
                    Editar
                  </button>
                  <button
                    className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-rose-200 text-xs font-medium text-rose-700 hover:bg-rose-50"
                    type="button"
                    onClick={() => onDelete(subject.id)}
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
