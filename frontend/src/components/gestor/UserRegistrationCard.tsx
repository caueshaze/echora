import type { ChangeEvent } from 'react'
import { UserPlus } from 'lucide-react'

import type { AdminRole, Classroom, School, Subject } from '../../lib/types'
import type { UserFormState } from '../../hooks/useGestorDirectory'

type UserRegistrationCardProps = {
  form: UserFormState
  onChange: (updates: Partial<UserFormState>) => void
  onSubmit: (event: React.FormEvent<HTMLFormElement>) => void
  submitting: boolean
  statusMessage: string | null
  isAdmin: boolean
  isManager: boolean
  visibleSchools: School[]
  subjects: Subject[]
  classrooms: Classroom[]
  mode: 'create' | 'edit'
  onCancelEdit: () => void
  tone?: 'light' | 'dark'
  className?: string
  allowedRoles?: AdminRole[]
  disabled?: boolean
  disabledReason?: string | null
}

export function UserRegistrationCard({
  form,
  onChange,
  onSubmit,
  submitting,
  statusMessage,
  isAdmin,
  isManager,
  visibleSchools,
  subjects,
  classrooms,
  mode,
  onCancelEdit,
  className,
  allowedRoles,
  disabled = false,
  disabledReason = null,
}: UserRegistrationCardProps) {
  const handleInputChange = (event: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { id, value } = event.target
    onChange({ [id as keyof UserFormState]: value } as Partial<UserFormState>)
  }

  const roleOptions: AdminRole[] =
    allowedRoles ||
    (isManager
      ? (['professor', 'aluno'] as AdminRole[])
      : (['admin', 'gestor', 'professor', 'aluno'] as AdminRole[]))
  const formDisabled = submitting || disabled

  const filteredSubjects = subjects.filter(
    (subject) => !form.school_id || subject.school_id === Number(form.school_id),
  )
  const filteredClassrooms = classrooms.filter(
    (classroom) => !form.school_id || classroom.school_id === Number(form.school_id),
  )

  return (
    <div className={className ?? 'card p-5 sm:p-6 space-y-5'}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-base sm:text-lg font-semibold text-slate-900">
            {mode === 'edit' ? 'Editar cadastro' : 'Novo usuário'}
          </h3>
          <p className="text-sm text-slate-500">
            {mode === 'edit'
              ? 'Altere os dados ou vínculos escolares e salve.'
              : 'Preencha as informações institucionais para liberar o acesso.'}
          </p>
        </div>
        {mode === 'edit' && (
          <button
            type="button"
            className="btn-secondary text-xs py-1.5 px-3 min-h-[34px]"
            onClick={onCancelEdit}
          >
            Cancelar
          </button>
        )}
      </div>

      {disabledReason && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-3.5 py-2.5 text-sm text-amber-800">
          {disabledReason}
        </div>
      )}

      <form className="space-y-5" onSubmit={onSubmit}>
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="label" htmlFor="full_name">
              Nome completo
            </label>
            <input
              id="full_name"
              className="input"
              placeholder="Ex.: Mariana Souza"
              value={form.full_name}
              onChange={handleInputChange}
              disabled={formDisabled}
              required
            />
          </div>

          <div>
            <label className="label" htmlFor="email">
              E-mail institucional
            </label>
            <input
              id="email"
              type="email"
              className="input"
              placeholder="nome@escola.edu.br"
              value={form.email}
              onChange={handleInputChange}
              disabled={formDisabled}
              required
            />
          </div>

          <div>
            <label className="label" htmlFor="password">
              {mode === 'edit' ? 'Nova senha (opcional)' : 'Senha inicial'}
            </label>
            <input
              id="password"
              type="password"
              className="input"
              placeholder={mode === 'edit' ? 'Manter senha atual' : 'Mínimo de 10 caracteres (12 para gestão)'}
              value={form.password}
              onChange={handleInputChange}
              disabled={formDisabled}
              required={mode === 'create'}
            />
          </div>

          <div>
            <label className="label" htmlFor="role">
              Função na escola
            </label>
            <select
              id="role"
              className="input"
              value={form.role}
              onChange={(event) =>
                onChange({
                  role: event.target.value as UserFormState['role'],
                  classroom_id: '',
                  teachable_subject_ids: [],
                })
              }
              disabled={formDisabled}
            >
              <option value="">Selecione...</option>
              {roleOptions.map((role) => (
                <option key={role} value={role}>
                  {labelForRole(role)}
                </option>
              ))}
            </select>
          </div>

          {form.role !== 'admin' && (
            <div className="sm:col-span-2">
              <label className="label" htmlFor="school_id">
                Unidade escolar
              </label>
              {isAdmin ? (
                <select
                  id="school_id"
                  className="input"
                  value={form.school_id}
                  onChange={(event) =>
                    onChange({
                      school_id: event.target.value,
                      classroom_id: '',
                      teachable_subject_ids: [],
                    })
                  }
                  disabled={formDisabled}
                  required
                >
                  <option value="">Selecione a unidade...</option>
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
          )}

          {form.role === 'professor' && (
            <div className="sm:col-span-2">
              <label className="label" htmlFor="teachable_subject_ids">
                Matérias lecionadas
              </label>
              <select
                id="teachable_subject_ids"
                multiple
                className="input h-32"
                value={form.teachable_subject_ids}
                onChange={(event) =>
                  onChange({
                    teachable_subject_ids: Array.from(event.target.selectedOptions).map(
                      (option) => option.value,
                    ),
                  })
                }
                disabled={formDisabled || !form.school_id}
                required
              >
                {filteredSubjects.map((subject) => (
                  <option key={subject.id} value={String(subject.id)}>
                    {subject.name}
                  </option>
                ))}
              </select>
              <p className="text-xs text-slate-500 mt-1">
                {form.school_id
                  ? filteredSubjects.length
                    ? 'No computador, segure Ctrl (ou Cmd) para marcar mais de uma matéria.'
                    : 'Cadastre matérias antes de vincular professores.'
                  : 'Selecione primeiro a unidade escolar.'}
              </p>
            </div>
          )}

          {form.role === 'aluno' && (
            <div className="sm:col-span-2">
              <label className="label" htmlFor="classroom_id">
                Turma
              </label>
              <select
                id="classroom_id"
                className="input"
                value={form.classroom_id}
                onChange={(event) => onChange({ classroom_id: event.target.value })}
                disabled={formDisabled || !form.school_id}
                required
              >
                <option value="">Selecione a turma...</option>
                {filteredClassrooms.map((classroom) => (
                  <option key={classroom.id} value={String(classroom.id)}>
                    {classroom.name}
                  </option>
                ))}
              </select>
              {!form.school_id && (
                <p className="text-xs text-slate-500 mt-1">
                  Selecione primeiro a unidade escolar para listar as turmas.
                </p>
              )}
            </div>
          )}
        </div>

        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pt-1">
          <p className="text-sm text-slate-600">{statusMessage}</p>
          <div className="flex gap-2">
            {mode === 'edit' && (
              <button
                type="button"
                className="btn-secondary"
                onClick={onCancelEdit}
                disabled={submitting}
              >
                Cancelar
              </button>
            )}
            <button className="btn w-full sm:w-auto" type="submit" disabled={formDisabled}>
              <UserPlus className="h-4 w-4" strokeWidth={1.75} />
              {submitting ? 'Salvando...' : mode === 'edit' ? 'Salvar alterações' : 'Cadastrar'}
            </button>
          </div>
        </div>
      </form>
    </div>
  )
}

function labelForRole(role: AdminRole) {
  return {
    admin: 'Administrador',
    gestor: 'Gestor(a) / Coordenação',
    professor: 'Professor(a)',
    aluno: 'Aluno(a)',
  }[role]
}
