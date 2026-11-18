import { useMemo, useState } from 'react'
import { Pencil, Search, Trash2 } from 'lucide-react'

import type { AdminRole, Classroom, DirectoryUser, School, Subject } from '../../lib/types'

type UsersTableCardProps = {
  users: DirectoryUser[]
  loading: boolean
  error: string | null
  roleFilter: AdminRole | 'all'
  onChangeRoleFilter: (role: AdminRole | 'all') => void
  onDeleteUser: (userId: string) => void
  onEditUser: (user: DirectoryUser) => void
  userActionStatus: string | null
  sessionUserId?: string | null
  schoolMap: Record<number, School>
  subjectMap: Record<number, Subject>
  classroomMap: Record<number, Classroom>
  tone?: 'light' | 'dark'
}

const ROLE_ORDER: AdminRole[] = ['admin', 'gestor', 'professor', 'aluno']

export function UsersTableCard({
  users,
  loading,
  error,
  roleFilter,
  onChangeRoleFilter,
  onDeleteUser,
  onEditUser,
  userActionStatus,
  sessionUserId,
  schoolMap,
  subjectMap,
  classroomMap,
}: UsersTableCardProps) {
  const [search, setSearch] = useState('')

  const filteredUsers = useMemo(() => {
    const query = search.trim().toLowerCase()
    if (!query) return users
    return users.filter(
      (user) =>
        user.full_name.toLowerCase().includes(query) ||
        user.email.toLowerCase().includes(query),
    )
  }, [search, users])

  const groupedUsers = useMemo(() => {
    const allowedRoles =
      roleFilter === 'all' ? ROLE_ORDER : ROLE_ORDER.filter((role) => role === roleFilter)
    return allowedRoles.map((role) => ({
      role,
      label: roleLabel(role),
      items: filteredUsers.filter((user) => user.role === role),
    }))
  }, [filteredUsers, roleFilter])

  const totalByRole = useMemo(() => {
    return ROLE_ORDER.reduce<Record<AdminRole, number>>((acc, role) => {
      acc[role] = users.filter((user) => user.role === role).length
      return acc
    }, {} as Record<AdminRole, number>)
  }, [users])

  return (
    <div className="card p-5 sm:p-6 space-y-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h3 className="text-base sm:text-lg font-semibold text-slate-900">
            Diretório de pessoas
          </h3>
          <p className="text-sm text-slate-500">
            Consulte e gerencie o cadastro de alunos, docentes e coordenação.
          </p>
        </div>

        <div className="relative w-full lg:w-72">
          <Search className="h-4 w-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
          <input
            className="input pl-9"
            placeholder="Buscar nome ou e-mail..."
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </div>
      </div>

      <div className="flex items-center gap-1.5 overflow-x-auto pb-1">
        {(['all', ...ROLE_ORDER] as const).map((roleKey) => {
          const active = roleFilter === roleKey
          const count = roleKey === 'all' ? users.length : totalByRole[roleKey]
          return (
            <button
              key={roleKey}
              type="button"
              onClick={() => onChangeRoleFilter(roleKey)}
              className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium whitespace-nowrap transition-colors ${
                active
                  ? 'bg-brand-700 text-white'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200/70'
              }`}
            >
              <span>{roleKey === 'all' ? 'Todos' : roleLabel(roleKey)}</span>
              <span
                className={`px-1.5 py-0.2 rounded text-[11px] tabular-nums ${
                  active ? 'bg-white/20 text-white' : 'bg-white text-slate-500'
                }`}
              >
                {count}
              </span>
            </button>
          )
        })}
      </div>

      {userActionStatus && (
        <p className="text-xs font-medium text-brand-800 bg-brand-50 border border-brand-200/70 rounded-lg px-3 py-2">
          {userActionStatus}
        </p>
      )}
      {error && <p className="text-sm text-rose-600">{error}</p>}
      {loading && <p className="text-sm text-slate-500 py-4">Carregando diretório...</p>}

      {!loading && filteredUsers.length === 0 && !error && (
        <p className="text-sm text-slate-500 py-6 text-center border border-dashed border-slate-200 rounded-xl">
          Nenhum usuário encontrado com os filtros selecionados.
        </p>
      )}

      {!loading && filteredUsers.length > 0 && (
        <div className="space-y-4">
          {groupedUsers
            .filter(({ items }) => roleFilter !== 'all' || items.length > 0)
            .map(({ role, label, items }) => (
              <section
                key={role}
                className="rounded-xl border border-slate-200/80 overflow-hidden bg-white"
              >
                <div className="px-4 py-2.5 bg-slate-50/80 border-b border-slate-200/70 flex items-center justify-between">
                  <span className="text-xs font-semibold uppercase tracking-wider text-slate-600">
                    {label}
                  </span>
                  <span className="text-xs text-slate-400 tabular-nums">
                    {items.length} registro(s)
                  </span>
                </div>

                {items.length === 0 ? (
                  <p className="p-4 text-sm text-slate-500">Nenhum cadastro neste perfil.</p>
                ) : (
                  <ul className="divide-y divide-slate-100">
                    {items.map((user) => {
                      const canEdit = user.role !== 'admin'
                      const canDelete =
                        String(sessionUserId) !== String(user.id) && user.role !== 'admin'
                      return (
                        <li
                          key={user.id}
                          className="p-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 hover:bg-slate-50/40 transition-colors"
                        >
                          <div className="min-w-0 space-y-1">
                            <div className="flex flex-wrap items-center gap-2">
                              <p className="text-sm font-semibold text-slate-900 truncate">
                                {user.full_name}
                              </p>
                              {user.school_id && (
                                <span className="text-[11px] font-medium px-2 py-0.5 rounded bg-slate-100 text-slate-600">
                                  {schoolMap[user.school_id]?.name ?? `Unidade #${user.school_id}`}
                                </span>
                              )}
                            </div>
                            <p className="text-xs text-slate-500 truncate">{user.email}</p>
                            {user.role !== 'admin' && user.role !== 'gestor' && (
                              <p className="text-xs text-slate-500">
                                <span className="font-medium text-slate-600">
                                  {user.role === 'aluno' ? 'Turma:' : 'Matérias:'}
                                </span>{' '}
                                {user.role === 'aluno'
                                  ? renderClassrooms(user, classroomMap)
                                  : renderSubjects(user, subjectMap)}
                              </p>
                            )}
                          </div>

                          {(canEdit || canDelete) && (
                            <div className="flex items-center gap-2 shrink-0 sm:self-center">
                              {canEdit && (
                                <button
                                  type="button"
                                  onClick={() => onEditUser(user)}
                                  className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-slate-200 text-xs font-medium text-slate-700 hover:bg-slate-50"
                                >
                                  <Pencil className="h-3 w-3" />
                                  Editar
                                </button>
                              )}
                              {canDelete && (
                                <button
                                  type="button"
                                  onClick={() => onDeleteUser(user.id)}
                                  className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-rose-200 text-xs font-medium text-rose-700 hover:bg-rose-50"
                                >
                                  <Trash2 className="h-3 w-3" />
                                  Excluir
                                </button>
                              )}
                            </div>
                          )}
                        </li>
                      )
                    })}
                  </ul>
                )}
              </section>
            ))}
        </div>
      )}
    </div>
  )
}

function renderClassrooms(user: DirectoryUser, classroomMap: Record<number, Classroom>) {
  if (user.classroom_id) {
    return classroomMap[user.classroom_id]?.name ?? `Turma #${user.classroom_id}`
  }
  return 'Não vinculada'
}

function renderSubjects(user: DirectoryUser, subjectMap: Record<number, Subject>) {
  const list = user.teachable_subject_ids || []
  if (!list.length) return 'Nenhuma selecionada'
  return list.map((subjectId) => subjectMap[subjectId]?.name ?? `Matéria #${subjectId}`).join(', ')
}

function roleLabel(role: AdminRole | 'all') {
  if (role === 'all') return 'Todos'
  return {
    admin: 'Administradores',
    gestor: 'Gestores',
    professor: 'Professores',
    aluno: 'Alunos',
  }[role]
}
