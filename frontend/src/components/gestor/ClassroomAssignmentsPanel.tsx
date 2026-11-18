import { useEffect, useMemo, useState } from 'react'
import { Check } from 'lucide-react'

import { fetchClassroomAssignments, updateClassroomAssignments } from '../../lib/api'
import type {
  Classroom,
  ClassroomAssignments,
  DirectoryUser,
  Subject,
} from '../../lib/types'

type ClassroomAssignmentsPanelProps = {
  classrooms: Classroom[]
  subjects: Subject[]
  teachers: DirectoryUser[]
  subjectMap: Record<number, Subject>
}

export function ClassroomAssignmentsPanel({
  classrooms,
  subjects,
  teachers,
  subjectMap,
}: ClassroomAssignmentsPanelProps) {
  const [selectedClassroomId, setSelectedClassroomId] = useState<number | null>(null)
  const [assignments, setAssignments] = useState<ClassroomAssignments | null>(null)
  const [status, setStatus] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)

  const selectedClassroom = useMemo(
    () => classrooms.find((classroom) => classroom.id === selectedClassroomId) ?? null,
    [classrooms, selectedClassroomId],
  )

  const eligibleTeachersBySubject = useMemo(() => {
    const map: Record<number, DirectoryUser[]> = {}
    subjects.forEach((subject) => {
      map[subject.id] = teachers.filter((teacher) =>
        (teacher.teachable_subject_ids || []).includes(subject.id),
      )
    })
    return map
  }, [teachers, subjects])

  useEffect(() => {
    if (!selectedClassroomId) {
      setAssignments(null)
      return
    }
    setLoading(true)
    setStatus(null)
    fetchClassroomAssignments(selectedClassroomId)
      .then((data) => {
        setAssignments(data)
      })
      .catch((error: any) => {
        setStatus(error?.message || 'Não foi possível carregar as atribuições desta turma.')
        setAssignments(null)
      })
      .finally(() => {
        setLoading(false)
      })
  }, [selectedClassroomId])

  const handleTeacherChange = (subjectId: number, teacherId: string | '') => {
    if (!assignments) return
    setAssignments({
      ...assignments,
      assignments: assignments.assignments.map((entry) =>
        entry.subject_id === subjectId
          ? { subject_id: subjectId, teacher_id: teacherId || null }
          : entry,
      ),
    })
  }

  const handleSave = async () => {
    if (!assignments || !selectedClassroomId) return
    setSaving(true)
    setStatus('Salvando atribuições...')
    try {
      await updateClassroomAssignments(selectedClassroomId, assignments)
      setStatus('Atribuições salvas com sucesso.')
    } catch (error: any) {
      setStatus(error?.message || 'Não foi possível salvar as atribuições.')
    } finally {
      setSaving(false)
    }
  }

  const classroomSubjects = selectedClassroom ? selectedClassroom.subject_ids : []

  return (
    <div className="card space-y-5 p-5 sm:p-6">
      <div>
        <h3 className="text-base sm:text-lg font-semibold text-slate-900">
          Docentes por turma e matéria
        </h3>
        <p className="text-sm text-slate-500">
          Selecione a turma para definir qual professor responde por cada disciplina.
        </p>
      </div>

      <div className="max-w-md">
        <label className="label" htmlFor="assignment_classroom">
          Turma
        </label>
        <select
          id="assignment_classroom"
          className="input"
          value={selectedClassroomId ?? ''}
          onChange={(event) =>
            setSelectedClassroomId(event.target.value ? Number(event.target.value) : null)
          }
        >
          <option value="">Selecione uma turma...</option>
          {classrooms.map((classroom) => (
            <option key={classroom.id} value={classroom.id}>
              {classroom.name}
            </option>
          ))}
        </select>
        {!classrooms.length && (
          <p className="text-xs text-slate-500 mt-1.5">
            Cadastre turmas antes de configurar atribuições.
          </p>
        )}
      </div>

      {status && (
        <p className="text-xs font-medium text-brand-800 bg-brand-50 border border-brand-200/70 rounded-lg px-3 py-2">
          {status}
        </p>
      )}
      {loading && <p className="text-sm text-slate-500">Carregando grade da turma...</p>}

      {selectedClassroom && classroomSubjects.length === 0 && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-3.5 text-sm text-amber-800">
          Esta turma ainda não possui disciplinas associadas. Vincule matérias no cadastro de turmas.
        </div>
      )}

      {assignments && selectedClassroom && classroomSubjects.length > 0 && (
        <div className="space-y-4">
          <ul className="divide-y divide-slate-100 rounded-xl border border-slate-200/80 overflow-hidden bg-white">
            {classroomSubjects.map((subjectId) => {
              const subject = subjectMap[subjectId]
              const entry = assignments.assignments.find((item) => item.subject_id === subjectId)
              const teacherList = (eligibleTeachersBySubject[subjectId] || []).filter(
                (teacher) => teacher.school_id === selectedClassroom.school_id,
              )
              return (
                <li
                  key={subjectId}
                  className="p-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3"
                >
                  <div className="flex items-center gap-2.5">
                    {subject?.color && (
                      <span
                        className="h-3 w-3 rounded-full shrink-0"
                        style={{ backgroundColor: subject.color }}
                      />
                    )}
                    <span className="text-sm font-semibold text-slate-900">
                      {subject?.name ?? `Matéria #${subjectId}`}
                    </span>
                  </div>

                  <div className="w-full sm:w-72">
                    {teacherList.length === 0 ? (
                      <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200/70 rounded-lg px-3 py-2">
                        Nenhum professor habilitado nesta matéria.
                      </p>
                    ) : (
                      <select
                        className="input"
                        value={entry?.teacher_id ?? ''}
                        onChange={(event) => handleTeacherChange(subjectId, event.target.value)}
                        disabled={saving}
                      >
                        <option value="">Sem professor definido</option>
                        {teacherList.map((teacher) => (
                          <option key={teacher.id} value={teacher.id}>
                            {teacher.full_name}
                          </option>
                        ))}
                      </select>
                    )}
                  </div>
                </li>
              )
            })}
          </ul>

          <div className="flex justify-end">
            <button
              className="btn w-full sm:w-auto"
              type="button"
              onClick={handleSave}
              disabled={saving || classroomSubjects.length === 0}
            >
              <Check className="h-4 w-4" />
              {saving ? 'Salvando...' : 'Salvar atribuições'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
