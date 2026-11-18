import { Pencil, Trash2 } from 'lucide-react'
import type { Classroom, School, Subject } from '../../lib/types'
import type { ClassroomFormState } from '../../hooks/useGestorDirectory'

type ClassroomsCatalogCardProps = {
  classrooms: Classroom[]
  loading: boolean
  error: string | null
  form: ClassroomFormState
  onChange: (updates: Partial<ClassroomFormState>) => void
  formMode: 'create' | 'edit'
  submitting: boolean
  statusMessage: string | null
  onSubmit: (event: React.FormEvent<HTMLFormElement>) => void
  onEdit: (classroom: Classroom) => void
  onDelete: (classroomId: number) => void
  onReset: () => void
  visibleSchools: School[]
  subjects: Subject[]
  subjectMap: Record<number, Subject>
  schoolMap: Record<number, School>
}

export function ClassroomsCatalogCard({
  classrooms,
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
  subjects,
  subjectMap,
  schoolMap,
}: ClassroomsCatalogCardProps) {
  return (
    <div className="space-y-6">
      <div className="card p-5 sm:p-6 space-y-5">
        <div>
          <h3 className="text-base sm:text-lg font-semibold text-slate-900">
            {formMode === 'edit' ? 'Editar turma' : 'Cadastrar turma'}
          </h3>
          <p className="text-sm text-slate-500">
            Defina a série e as disciplinas que fazem parte da turma.
          </p>
        </div>

        <form className="grid gap-4 sm:grid-cols-2" onSubmit={onSubmit}>
          <div>
            <label className="label" htmlFor="classroom_name">
              Nome da turma
            </label>
            <input
              id="classroom_name"
              className="input"
              placeholder="Ex.: 3º Ano A"
              value={form.name}
              onChange={(event) => onChange({ name: event.target.value })}
              disabled={submitting}
              required
            />
          </div>
          <div>
            <label className="label" htmlFor="classroom_code">
              Código (opcional)
            </label>
            <input
              id="classroom_code"
              className="input"
              placeholder="Ex.: 3A-EM"
              value={form.code}
              onChange={(event) => onChange({ code: event.target.value })}
              disabled={submitting}
            />
          </div>
          <div>
            <label className="label" htmlFor="classroom_grade">
              Série / Etapa
            </label>
            <input
              id="classroom_grade"
              className="input"
              value={form.grade_level}
              onChange={(event) => onChange({ grade_level: event.target.value })}
              disabled={submitting}
              placeholder="Ex.: Ensino Médio"
            />
          </div>
          <div>
            <label className="label" htmlFor="classroom_school">
              Unidade escolar
            </label>
            {visibleSchools.length > 1 ? (
              <select
                id="classroom_school"
                className="input"
                value={form.school_id}
                onChange={(event) => onChange({ school_id: event.target.value, subject_ids: [] })}
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
          <div className="sm:col-span-2">
            <label className="label" htmlFor="classroom_subjects">
              Grade de matérias
            </label>
            <select
              id="classroom_subjects"
              multiple
              className="input h-32"
              value={form.subject_ids}
              onChange={(event) => {
                const selected = Array.from(event.target.selectedOptions).map(
                  (option) => option.value,
                )
                onChange({ subject_ids: selected })
              }}
              disabled={submitting || !form.school_id}
              required
            >
              {subjects
                .filter(
                  (subject) => !form.school_id || subject.school_id === Number(form.school_id),
                )
                .map((subject) => (
                  <option key={subject.id} value={String(subject.id)}>
                    {subject.name}
                  </option>
                ))}
            </select>
            <p className="text-xs text-slate-500 mt-1">
              {form.school_id
                ? 'Selecione uma ou mais matérias ofertadas nesta turma.'
                : 'Escolha a unidade escolar antes de definir as matérias.'}
            </p>
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
          Turmas ativas ({classrooms.length})
        </h3>
        {loading ? (
          <p className="text-sm text-slate-500">Carregando turmas...</p>
        ) : classrooms.length === 0 ? (
          <p className="text-sm text-slate-500 py-6 text-center border border-dashed border-slate-200 rounded-xl">
            Nenhuma turma cadastrada até o momento.
          </p>
        ) : (
          <ul className="divide-y divide-slate-100 rounded-xl border border-slate-200/80 overflow-hidden bg-white">
            {classrooms.map((classroom) => (
              <li
                key={classroom.id}
                className="p-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 hover:bg-slate-50/40"
              >
                <div className="space-y-1.5 min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-sm font-semibold text-slate-900">{classroom.name}</p>
                    {classroom.grade_level && (
                      <span className="text-[11px] font-medium px-2 py-0.5 rounded bg-brand-50 text-brand-800">
                        {classroom.grade_level}
                      </span>
                    )}
                    {classroom.code && (
                      <span className="text-[11px] font-medium px-2 py-0.5 rounded bg-slate-100 text-slate-600">
                        {classroom.code}
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-slate-500">
                    {schoolMap[classroom.school_id]?.name ?? 'Unidade escolar'}
                  </p>
                  {classroom.subject_ids?.length > 0 && (
                    <div className="flex flex-wrap gap-1 pt-0.5">
                      {classroom.subject_ids.map((subjectId) => (
                        <span
                          key={`${classroom.id}-${subjectId}`}
                          className="rounded bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600"
                        >
                          {subjectMap[subjectId]?.name ?? `Matéria #${subjectId}`}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  <button
                    className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-slate-200 text-xs font-medium text-slate-700 hover:bg-slate-50"
                    type="button"
                    onClick={() => onEdit(classroom)}
                  >
                    <Pencil className="h-3 w-3" />
                    Editar
                  </button>
                  <button
                    className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-rose-200 text-xs font-medium text-rose-700 hover:bg-rose-50"
                    type="button"
                    onClick={() => onDelete(classroom.id)}
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
