import { useEffect, useMemo, useState } from 'react'
import { CheckCircle2, EyeOff, Search, Send } from 'lucide-react'

import {
  createFeedback,
  fetchAvailableClassrooms,
  fetchAvailableSubjects,
  fetchFeedbackRecipients,
} from '../../lib/api'
import { useAuth } from '../../context/AuthContext'
import type {
  AdminRole,
  Classroom,
  FeedbackRecipient,
  FeedbackCreateInput,
  FeedbackPublic,
  FeedbackTargetType,
  Subject,
} from '../../lib/types'
import { FeedbackTermsModal } from './FeedbackTermsModal'

type FeedbackComposerProps = {
  title: string
  helperText?: string
  onSuccess?: (feedback: FeedbackPublic) => void
}

type ComposerFormState = {
  target_type: FeedbackTargetType | ''
  target_id: string
  content: string
  is_anonymous: boolean
}

const TARGET_VISIBILITY: Record<string, AdminRole[]> = {
  admin: ['admin', 'gestor', 'professor', 'aluno'],
  gestor: ['gestor', 'professor', 'aluno'],
  professor: ['gestor', 'aluno'],
  aluno: ['gestor', 'professor'],
}

const TARGET_TYPE_VISIBILITY: Record<string, FeedbackTargetType[]> = {
  admin: ['user', 'class', 'subject'],
  gestor: ['user', 'class', 'subject'],
  professor: ['user', 'class', 'subject'],
  aluno: ['user', 'subject'],
}

const TARGET_TYPE_LABELS: Record<FeedbackTargetType, string> = {
  user: 'Pessoa específica',
  class: 'Turma inteira',
  subject: 'Matéria / Disciplina',
}

const ROLE_LABELS: Record<AdminRole, string> = {
  admin: 'Administração',
  gestor: 'Coordenação / Gestão',
  professor: 'Professor(a)',
  aluno: 'Aluno(a)',
}

export function FeedbackComposer({ title, helperText, onSuccess }: FeedbackComposerProps) {
  const { session } = useAuth()
  const isStudentSender = session?.backendRole === 'aluno'

  const [form, setForm] = useState<ComposerFormState>({
    target_type: '',
    target_id: '',
    content: '',
    is_anonymous: false,
  })
  const [termsModalOpen, setTermsModalOpen] = useState(false)
  const [status, setStatus] = useState<{ type: 'success' | 'error' | 'info'; text: string } | null>(
    null,
  )
  const [submitting, setSubmitting] = useState(false)

  const [targetRole, setTargetRole] = useState<AdminRole | ''>('')
  const [studentClassroomId, setStudentClassroomId] = useState<string>('')
  const [recipientSearch, setRecipientSearch] = useState('')
  const [recipients, setRecipients] = useState<FeedbackRecipient[]>([])
  const [recipientsStatus, setRecipientsStatus] = useState<string | null>(null)
  const [recipientsLoading, setRecipientsLoading] = useState(false)

  const [subjects, setSubjects] = useState<Subject[]>([])
  const [subjectsStatus, setSubjectsStatus] = useState<string | null>(null)
  const [subjectsLoading, setSubjectsLoading] = useState(false)
  const [subjectsFetched, setSubjectsFetched] = useState(false)

  const [classrooms, setClassrooms] = useState<Classroom[]>([])
  const [classroomsStatus, setClassroomsStatus] = useState<string | null>(null)
  const [classroomsLoading, setClassroomsLoading] = useState(false)

  const allowedRecipientRoles = useMemo(() => {
    const key = session?.backendRole || ''
    return TARGET_VISIBILITY[key] ?? []
  }, [session?.backendRole])

  const allowedTargetTypes = useMemo(() => {
    const key = session?.backendRole || ''
    return TARGET_TYPE_VISIBILITY[key] ?? ['user']
  }, [session?.backendRole])

  const isUserTarget = form.target_type === 'user'
  const isStudentTarget = isUserTarget && targetRole === 'aluno'
  const needsClassrooms = form.target_type === 'class' || isStudentTarget

  // Carrega turmas quando destino for turma OU quando for selecionar um aluno por turma
  useEffect(() => {
    if (!needsClassrooms) {
      return
    }
    setClassroomsLoading(true)
    setClassroomsStatus('Carregando turmas...')
    fetchAvailableClassrooms()
      .then((data) => {
        setClassrooms(data)
        setClassroomsStatus(
          data.length === 0 ? 'Nenhuma turma disponível no seu escopo.' : null,
        )
      })
      .catch((error: any) => {
        setClassrooms([])
        setClassroomsStatus(error?.message || 'Não foi possível carregar as turmas.')
      })
      .finally(() => {
        setClassroomsLoading(false)
      })
  }, [needsClassrooms, isStudentTarget])

  // Carrega destinatários (para alunos, exige primeiro selecionar a turma!)
  useEffect(() => {
    if (!isUserTarget || !targetRole) {
      setRecipients([])
      setRecipientsStatus(null)
      if (!isUserTarget) {
        setTargetRole('')
        setStudentClassroomId('')
        setRecipientSearch('')
        setForm((prev) => ({ ...prev, target_id: '' }))
      }
      return
    }

    if (targetRole === 'aluno' && !studentClassroomId) {
      setRecipients([])
      setRecipientsStatus(null)
      return
    }

    setRecipientsLoading(true)
    setRecipientsStatus('Buscando destinatários...')

    const classroomId = targetRole === 'aluno' && studentClassroomId
      ? Number(studentClassroomId)
      : undefined

    fetchFeedbackRecipients(targetRole, classroomId)
      .then((data) => {
        const filtered = data.filter((user) => String(user.id) !== String(session?.id))
        setRecipients(filtered)
        setRecipientsStatus(
          filtered.length === 0
            ? targetRole === 'aluno'
              ? 'Nenhum aluno cadastrado nesta turma.'
              : 'Nenhuma pessoa encontrada neste perfil.'
            : null,
        )
      })
      .catch((error: any) => {
        setRecipients([])
        setRecipientsStatus(error?.message || 'Não foi possível carregar os destinatários.')
      })
      .finally(() => {
        setRecipientsLoading(false)
      })
  }, [isUserTarget, session?.id, targetRole, studentClassroomId])

  useEffect(() => {
    if (form.target_type !== 'subject' || subjectsFetched) {
      return
    }
    setSubjectsLoading(true)
    setSubjectsStatus('Carregando matérias...')
    fetchAvailableSubjects()
      .then((data) => {
        setSubjects(data)
        setSubjectsStatus(
          data.length === 0 ? 'Nenhuma matéria vinculada à sua turma no momento.' : null,
        )
        setSubjectsFetched(true)
      })
      .catch((error: any) => {
        setSubjects([])
        setSubjectsStatus(error?.message || 'Não foi possível carregar as matérias.')
      })
      .finally(() => {
        setSubjectsLoading(false)
      })
  }, [form.target_type, subjectsFetched])

  const filteredRecipients = useMemo(() => {
    const query = recipientSearch.trim().toLowerCase()
    if (!query) return recipients
    return recipients.filter(
      (recipient) =>
        recipient.full_name.toLowerCase().includes(query),
    )
  }, [recipients, recipientSearch])

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setSubmitting(true)
    setStatus({ type: 'info', text: 'Registrando mensagem...' })
    try {
      if (!form.target_type) {
        throw new Error('Escolha para quem deseja enviar.')
      }
      if (!form.target_id) {
        throw new Error('Selecione o destinatário.')
      }
      if (!form.content.trim()) {
        throw new Error('Escreva sua mensagem antes de enviar.')
      }
      const payload: FeedbackCreateInput = {
        target_type: form.target_type as FeedbackTargetType,
        target_id: form.target_id,
        content: form.content.trim(),
        is_anonymous: isStudentSender ? form.is_anonymous : false,
      }
      const feedback = await createFeedback(payload)
      setStatus({
        type: 'success',
        text:
          isStudentSender && form.is_anonymous
            ? 'Relato anônimo enviado com sucesso.'
            : 'Mensagem enviada com sucesso.',
      })
      setForm({ target_type: '', target_id: '', content: '', is_anonymous: false })
      setTargetRole('')
      setStudentClassroomId('')
      setRecipientSearch('')
      onSuccess?.(feedback)
    } catch (error: any) {
      setStatus({
        type: 'error',
        text: error?.message || 'Não foi possível enviar sua mensagem.',
      })
    } finally {
      setSubmitting(false)
    }
  }

  const canSelectRecipients = isUserTarget && allowedRecipientRoles.length > 0
  const isClassTarget = form.target_type === 'class'
  const isSubjectTarget = form.target_type === 'subject'
  const canSubmit =
    Boolean(form.target_type) && Boolean(form.target_id) && Boolean(form.content.trim())
  const showRecipientSearch =
    recipients.length > 6 || (isStudentTarget && Boolean(studentClassroomId) && recipients.length > 0)

  return (
    <>
      <div className="card p-5 sm:p-6 space-y-5">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
          {helperText && <p className="text-sm text-slate-500 mt-0.5">{helperText}</p>}
        </div>

        <form className="space-y-4" onSubmit={handleSubmit}>
          <div>
            <label className="label">Para onde vai este relato?</label>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
              {allowedTargetTypes.map((type) => {
                const selected = form.target_type === type
                return (
                  <button
                    key={type}
                    type="button"
                    disabled={submitting}
                    onClick={() => {
                      setForm((prev) => ({
                        ...prev,
                        target_type: type,
                        target_id: '',
                      }))
                      setTargetRole('')
                      setStudentClassroomId('')
                      setRecipientSearch('')
                      setStatus(null)
                    }}
                    className={`px-3.5 py-2.5 rounded-lg border text-sm font-medium text-left transition-colors ${
                      selected
                        ? 'border-brand-600 bg-brand-50/70 text-brand-900 ring-1 ring-brand-600/20'
                        : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-50'
                    }`}
                  >
                    {TARGET_TYPE_LABELS[type]}
                  </button>
                )
              })}
            </div>
          </div>

          {isUserTarget && (
            <div className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label className="label" htmlFor="composer-role">
                    Área / Função
                  </label>
                  <select
                    id="composer-role"
                    className="input"
                    value={targetRole}
                    onChange={(event) => {
                      setTargetRole(event.target.value as AdminRole)
                      setStudentClassroomId('')
                      setRecipientSearch('')
                      setForm((prev) => ({ ...prev, target_id: '' }))
                    }}
                    disabled={!canSelectRecipients || submitting}
                  >
                    <option value="">Escolha o grupo...</option>
                    {allowedRecipientRoles.map((role) => (
                      <option key={role} value={role}>
                        {ROLE_LABELS[role]}
                      </option>
                    ))}
                  </select>
                </div>

                {isStudentTarget && (
                  <div>
                    <label className="label" htmlFor="composer-student-classroom">
                      Turma do aluno
                    </label>
                    <select
                      id="composer-student-classroom"
                      className="input"
                      value={studentClassroomId}
                      onChange={(event) => {
                        setStudentClassroomId(event.target.value)
                        setRecipientSearch('')
                        setForm((prev) => ({ ...prev, target_id: '' }))
                      }}
                      disabled={classroomsLoading || submitting}
                    >
                      <option value="">Selecione a turma...</option>
                      {classrooms.map((classroom) => (
                        <option key={classroom.id} value={String(classroom.id)}>
                          {classroom.name}
                          {classroom.grade_level ? ` · ${classroom.grade_level}` : ''}
                        </option>
                      ))}
                    </select>
                    {(classroomsLoading || classroomsStatus) && (
                      <p className="text-xs text-slate-500 mt-1.5">
                        {classroomsLoading ? 'Carregando turmas...' : classroomsStatus}
                      </p>
                    )}
                  </div>
                )}

                {(!isStudentTarget || studentClassroomId) && (
                  <div className={isStudentTarget ? 'sm:col-span-2 space-y-2' : ''}>
                    <div className="flex items-center justify-between gap-2">
                      <label className="label mb-0" htmlFor="composer-recipient">
                        {isStudentTarget ? 'Estudante' : 'Nome do destinatário'}
                      </label>
                      {recipients.length > 0 && (
                        <span className="text-[11px] text-slate-400 tabular-nums">
                          {filteredRecipients.length} de {recipients.length} pessoa(s)
                        </span>
                      )}
                    </div>

                    {showRecipientSearch && (
                      <div className="relative">
                        <Search className="h-4 w-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                        <input
                          type="search"
                          className="input pl-9"
                          placeholder={
                            isStudentTarget
                              ? 'Filtrar estudante pelo nome...'
                              : 'Filtrar destinatário pelo nome...'
                          }
                          value={recipientSearch}
                          onChange={(event) => {
                            const nextSearch = event.target.value
                            setRecipientSearch(nextSearch)
                          }}
                          disabled={submitting}
                        />
                      </div>
                    )}

                    <select
                      id="composer-recipient"
                      className="input mt-1.5"
                      value={form.target_id}
                      onChange={(event) =>
                        setForm((prev) => ({ ...prev, target_id: event.target.value }))
                      }
                      disabled={
                        !canSelectRecipients ||
                        !targetRole ||
                        (isStudentTarget && !studentClassroomId) ||
                        recipientsLoading ||
                        submitting
                      }
                    >
                      <option value="">
                        {isStudentTarget ? 'Selecione o(a) aluno(a)...' : 'Selecione...'}
                      </option>
                      {filteredRecipients.map((recipient) => (
                        <option key={recipient.id} value={recipient.id}>
                          {recipient.full_name}
                        </option>
                      ))}
                    </select>

                    {(recipientsLoading || recipientsStatus) && (
                      <p className="text-xs text-slate-500 mt-1">
                        {recipientsLoading ? 'Buscando alunos da turma...' : recipientsStatus}
                      </p>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}

          {isSubjectTarget && (
            <div>
              <label className="label" htmlFor="composer-subject">
                Qual matéria?
              </label>
              <select
                id="composer-subject"
                className="input"
                value={form.target_id}
                onChange={(event) =>
                  setForm((prev) => ({ ...prev, target_id: event.target.value }))
                }
                disabled={subjectsLoading || submitting}
              >
                <option value="">Selecione a matéria...</option>
                {subjects.map((subject) => (
                  <option key={subject.id} value={subject.id}>
                    {subject.name}
                  </option>
                ))}
              </select>
              {(subjectsLoading || subjectsStatus) && (
                <p className="text-xs text-slate-500 mt-1.5">
                  {subjectsLoading ? 'Carregando matérias...' : subjectsStatus}
                </p>
              )}
            </div>
          )}

          {isClassTarget && (
            <div>
              <label className="label" htmlFor="composer-class">
                Qual turma?
              </label>
              <select
                id="composer-class"
                className="input"
                value={form.target_id}
                onChange={(event) =>
                  setForm((prev) => ({ ...prev, target_id: event.target.value }))
                }
                disabled={classroomsLoading || submitting}
              >
                <option value="">Selecione a turma...</option>
                {classrooms.map((classroom) => (
                  <option key={classroom.id} value={classroom.id}>
                    {classroom.name}
                  </option>
                ))}
              </select>
              {(classroomsLoading || classroomsStatus) && (
                <p className="text-xs text-slate-500 mt-1.5">
                  {classroomsLoading ? 'Carregando turmas...' : classroomsStatus}
                </p>
              )}
            </div>
          )}

          <div>
            <label className="label" htmlFor="composer-content">
              Mensagem
            </label>
            <textarea
              id="composer-content"
              className="input min-h-[120px] resize-y"
              placeholder="Escreva de forma clara e construtiva sobre o que aconteceu ou o que pode melhorar..."
              value={form.content}
              onChange={(event) => setForm((prev) => ({ ...prev, content: event.target.value }))}
              disabled={submitting}
              required
            />
          </div>

          {/* Toggle de Envio Anônimo exclusivo para Alunos */}
          {isStudentSender && (
            <div className="rounded-xl border border-slate-200/90 bg-slate-50/70 p-3.5 sm:p-4 flex items-start justify-between gap-4">
              <div className="flex items-start gap-3">
                <span
                  className={`mt-0.5 h-8 w-8 rounded-lg grid place-items-center shrink-0 transition-colors ${
                    form.is_anonymous
                      ? 'bg-brand-700 text-white'
                      : 'bg-white border border-slate-200 text-slate-500'
                  }`}
                >
                  <EyeOff className="h-4 w-4" strokeWidth={1.75} />
                </span>
                <div>
                  <label
                    htmlFor="composer-anonymous-toggle"
                    className="text-sm font-semibold text-slate-900 cursor-pointer select-none"
                  >
                    Enviar de forma anônima
                  </label>
                  <p className="text-xs text-slate-500 mt-0.5 leading-relaxed">
                    Seu nome não será exibido para professores nem para a coordenação.
                  </p>
                </div>
              </div>

              <button
                id="composer-anonymous-toggle"
                type="button"
                role="switch"
                aria-checked={form.is_anonymous}
                disabled={submitting}
                onClick={() =>
                  setForm((prev) => ({ ...prev, is_anonymous: !prev.is_anonymous }))
                }
                className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus:outline-none focus:ring-2 focus:ring-brand-600/30 ${
                  form.is_anonymous ? 'bg-brand-700' : 'bg-slate-300'
                }`}
              >
                <span
                  aria-hidden="true"
                  className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow-xs transition-transform ${
                    form.is_anonymous ? 'translate-x-5' : 'translate-x-0'
                  }`}
                />
              </button>
            </div>
          )}

          <div className="space-y-3 pt-1">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
              <div className="min-h-[20px]">
                {status && (
                  <p
                    className={`inline-flex items-center gap-1.5 text-sm font-medium ${
                      status.type === 'success'
                        ? 'text-emerald-700'
                        : status.type === 'error'
                          ? 'text-rose-600'
                          : 'text-slate-600'
                    }`}
                  >
                    {status.type === 'success' && <CheckCircle2 className="h-4 w-4 shrink-0" />}
                    {status.text}
                  </p>
                )}
              </div>

              <button
                type="submit"
                className="btn w-full sm:w-auto px-6"
                disabled={submitting || !canSubmit}
              >
                <Send className="h-4 w-4" strokeWidth={1.75} />
                {submitting ? 'Enviando...' : 'Enviar relato'}
              </button>
            </div>

            <div className="border-t border-slate-100 pt-3 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1 text-xs text-slate-400">
              <span>O conteúdo é criptografado em repouso (AES-256-GCM).</span>
              <span>
                Ao enviar, você concorda com os{' '}
                <button
                  type="button"
                  onClick={() => setTermsModalOpen(true)}
                  className="font-medium text-brand-700 hover:text-brand-800 underline underline-offset-2"
                >
                  termos de uso e convivência
                </button>
                .
              </span>
            </div>
          </div>
        </form>
      </div>

      <FeedbackTermsModal open={termsModalOpen} onClose={() => setTermsModalOpen(false)} />
    </>
  )
}
