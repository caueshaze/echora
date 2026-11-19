import { MayaHistory } from '../components/maya/MayaHistory'
import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  BarChart3,
  BookOpen,
  Building2,
  GitBranch,
  GraduationCap,
  MessageSquare,
  PenSquare,
  ShieldAlert,
  Sparkles,
  UserCheck,
  UserCog,
  Users,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

import { useAuth } from '../context/AuthContext'
import { useGestorOverview } from '../hooks/useGestorOverview'
import {
  useGestorDirectory,
  type ClassroomFormState,
  type SubjectFormState,
  type UserFormState,
} from '../hooks/useGestorDirectory'
import { AppShell, type NavItem } from '../components/layout/AppShell'
import { GestorOverviewSection } from '../components/gestor/GestorOverviewSection'
import { FeedbackComposer } from '../components/feedback/FeedbackComposer'
import { InsightSummaryCard } from '../components/gestor/InsightSummaryCard'
import { RecentFeedbackTable } from '../components/gestor/RecentFeedbackTable'
import { UserRegistrationCard } from '../components/gestor/UserRegistrationCard'
import { UsersTableCard } from '../components/gestor/UsersTableCard'
import { SchoolsCatalogCard } from '../components/gestor/SchoolsCatalogCard'
import { SubjectsCatalogCard } from '../components/gestor/SubjectsCatalogCard'
import { ClassroomsCatalogCard } from '../components/gestor/ClassroomsCatalogCard'
import { ClassroomAssignmentsPanel } from '../components/gestor/ClassroomAssignmentsPanel'
import { deleteFeedback } from '../lib/api'
import { useTriggerAlerts } from '../hooks/useTriggerAlerts'
import { useTriggerKeywords } from '../hooks/useTriggerKeywords'
import { TriggerKeywordsCard } from '../components/alerts/TriggerKeywordsCard'
import { TriggerAlertFeed } from '../components/alerts/TriggerAlertFeed'
import { GestorAnalyticsPanel } from '../components/gestor/GestorAnalyticsPanel'
import { UserProfileDrawer } from '../components/gestor/UserProfileDrawer'
import type { FeedbackPublic } from '../lib/types'

type ManagementSection =
  | 'overview'
  | 'compose'
  | 'insights'
  | 'feedbacks'
  | 'alerts'
  | 'directory'
  | 'schools'
  | 'subjects'
  | 'classrooms'
  | 'teachers'
  | 'students'
  | 'managers'
  | 'assignments'

const NAV_GROUPS: Array<{
  label: string
  items: Array<{ id: ManagementSection; label: string; shortLabel?: string; icon: LucideIcon; adminOnly?: boolean }>
}> = [
  {
    label: 'Acompanhamento',
    items: [
      { id: 'overview', label: 'Painel geral', shortLabel: 'Painel', icon: BarChart3 },
      { id: 'feedbacks', label: 'Relatos', icon: MessageSquare },
      { id: 'alerts', label: 'Atenção & Segurança', shortLabel: 'Alertas', icon: ShieldAlert },
      { id: 'insights', label: 'Relatório IA', shortLabel: 'IA', icon: Sparkles },
      { id: 'compose', label: 'Novo comunicado', shortLabel: 'Enviar', icon: PenSquare },
    ],
  },
  {
    label: ' Organização Escolar',
    items: [
      { id: 'classrooms', label: 'Turmas', icon: GraduationCap },
      { id: 'subjects', label: 'Matérias', icon: BookOpen },
      { id: 'assignments', label: 'Atribuição docente', icon: GitBranch },
      { id: 'schools', label: 'Unidades', icon: Building2, adminOnly: true },
    ],
  },
  {
    label: 'Comunidade',
    items: [
      { id: 'teachers', label: 'Professores', icon: UserCheck },
      { id: 'students', label: 'Alunos', icon: Users },
      { id: 'managers', label: 'Gestores', icon: UserCog, adminOnly: true },
      { id: 'directory', label: 'Diretório completo', icon: Users },
    ],
  },
]

const SECTION_META: Record<ManagementSection, { title: string; subtitle: string }> = {
  overview: {
    title: 'Visão da Unidade',
    subtitle: 'Acompanhamento em tempo real do clima escolar e participação.',
  },
  compose: {
    title: 'Enviar comunicado',
    subtitle: 'Encaminhe mensagens institucionais para turmas, docentes ou estudantes.',
  },
  insights: {
    title: 'Relatório Executivo',
    subtitle: 'Síntese qualitativa gerada a partir dos relatos da unidade.',
  },
  feedbacks: {
    title: 'Relatos registrados',
    subtitle: 'Histórico consolidado de feedbacks recebidos na unidade.',
  },
  alerts: {
    title: 'Centro de Atenção',
    subtitle: 'Acompanhamento prioritário de relatos sensíveis e termos monitorados.',
  },
  directory: {
    title: 'Diretório da Comunidade',
    subtitle: 'Gestão centralizada de contas e vínculos institucionais.',
  },
  schools: {
    title: 'Unidades Escolares',
    subtitle: 'Administração das unidades cadastradas na rede.',
  },
  subjects: {
    title: 'Grade de Matérias',
    subtitle: 'Disciplinas ofertadas pela instituição.',
  },
  classrooms: {
    title: 'Turmas',
    subtitle: 'Organização de turmas, séries e respectivas disciplinas.',
  },
  teachers: {
    title: 'Corpo Docente',
    subtitle: 'Cadastro de professores e habilitação por disciplina.',
  },
  students: {
    title: 'Estudantes',
    subtitle: 'Cadastro de alunos e enturmação.',
  },
  managers: {
    title: 'Equipe Gestora',
    subtitle: 'Coordenadores e diretores vinculados às unidades.',
  },
  assignments: {
    title: 'Atribuição Docente',
    subtitle: 'Definição do professor titular por matéria em cada turma.',
  },
}

export default function Gestor() {
  const { session, logout } = useAuth()
  const backendRole = session?.backendRole ?? null
  const managerSchoolId = session?.schoolId ?? null
  const isAdmin = backendRole === 'admin'
  const isManager = backendRole === 'gestor'

  const [activeSection, setActiveSection] = useState<ManagementSection>('overview')
  const [directoryInitialized, setDirectoryInitialized] = useState(false)
  const [feedbackActionStatus, setFeedbackActionStatus] = useState<string | null>(null)
  const [selectedUserId, setSelectedUserId] = useState<string | null>(null)

  const triggerAlerts = useTriggerAlerts(
    isAdmin ? {} : { schoolId: managerSchoolId ?? undefined },
  )
  const resolvedAlerts = useTriggerAlerts({
    ...(isAdmin ? {} : { schoolId: managerSchoolId ?? undefined }),
    includeResolved: true,
    onlyResolved: true,
    emptyMessage: 'Nenhum atendimento concluído registrado ainda.',
  })
  const triggerKeywords = useTriggerKeywords({
    isAdmin,
    schoolId: managerSchoolId,
    enabled: activeSection === 'alerts',
  })

  const overview = useGestorOverview({ isAdmin, managerSchoolId })
  const directory = useGestorDirectory({ isAdmin, isManager, managerSchoolId })

  const {
    feedbacks,
    feedbacksLoading,
    feedbacksNotice,
    summary,
    summaryLoading,
    summaryStatus,
    feedbackPurgeStatus,
    feedbackPurgeLoading,
    stats,
    analytics,
    userIndex,
    loadFeedbacks,
    loadSummary,
    handleDeleteAllFeedbacks,
  } = overview

  const {
    initializeDirectory,
    usersState,
    schoolsState,
    subjectsState,
    classroomsState,
    referenceData,
  } = directory
  const roleFilterSetter = usersState.setRoleFilter

  const navItems: Array<NavItem<ManagementSection>> = useMemo(
    () =>
      NAV_GROUPS.flatMap((group) =>
        group.items
          .filter((item) => (isAdmin ? true : !item.adminOnly))
          .map((item) => ({
            ...item,
            group: group.label.trim(),
            badge:
              item.id === 'alerts' && triggerAlerts.alerts.length > 0
                ? triggerAlerts.alerts.length
                : undefined,
          })),
      ),
    [isAdmin, triggerAlerts.alerts.length],
  )

  useEffect(() => {
    void loadFeedbacks()
  }, [loadFeedbacks])

  useEffect(() => {
    const needsDirectory = [
      'directory',
      'schools',
      'subjects',
      'classrooms',
      'teachers',
      'students',
      'managers',
      'assignments',
    ].includes(activeSection)
    if (needsDirectory && !directoryInitialized) {
      setDirectoryInitialized(true)
      void initializeDirectory()
    }
  }, [activeSection, directoryInitialized, initializeDirectory])

  useEffect(() => {
    if (activeSection === 'teachers') {
      roleFilterSetter('professor')
    } else if (activeSection === 'students') {
      roleFilterSetter('aluno')
    } else if (activeSection === 'managers') {
      roleFilterSetter('gestor')
    } else if (activeSection === 'directory') {
      roleFilterSetter('all')
    }
  }, [activeSection, roleFilterSetter])

  const selectedProfile = selectedUserId ? userIndex[selectedUserId] ?? null : null

  const sortByDateDesc = useCallback((list: FeedbackPublic[]) => {
    return [...list].sort(
      (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
    )
  }, [])

  const selectedProfileSent = useMemo(() => {
    if (!selectedUserId) return []
    return sortByDateDesc(feedbacks.filter((feedback) => feedback.sender_id === selectedUserId))
  }, [selectedUserId, feedbacks, sortByDateDesc])

  const selectedProfileReceived = useMemo(() => {
    if (!selectedUserId) return []
    return sortByDateDesc(
      feedbacks.filter(
        (feedback) => feedback.target_type === 'user' && feedback.target_id === selectedUserId,
      ),
    )
  }, [selectedUserId, feedbacks, sortByDateDesc])

  const professorDirectory = useMemo(
    () => usersState.users.filter((user) => user.role === 'professor'),
    [usersState.users],
  )

  const handleRoleFilterChange = useCallback(
    (value: 'all' | 'admin' | 'gestor' | 'professor' | 'aluno') => {
      if (['teachers', 'students', 'managers'].includes(activeSection)) {
        return
      }
      roleFilterSetter(value)
    },
    [activeSection, roleFilterSetter],
  )

  const handleDeleteSingleFeedback = useCallback(
    async (feedbackId: number) => {
      if (!window.confirm('Deseja excluir permanentemente este registro?')) return
      setFeedbackActionStatus('Removendo registro...')
      try {
        await deleteFeedback(feedbackId)
        setFeedbackActionStatus('Registro removido com sucesso.')
        await loadFeedbacks()
        await triggerAlerts.loadAlerts()
        await resolvedAlerts.loadAlerts()
      } catch (error: any) {
        setFeedbackActionStatus(error?.message || 'Não foi possível remover o registro.')
      }
    },
    [loadFeedbacks, triggerAlerts, resolvedAlerts],
  )

  const handleOpenProfile = useCallback((userId: string) => {
    setSelectedUserId(userId)
  }, [])

  const handleCloseProfile = useCallback(() => {
    setSelectedUserId(null)
  }, [])

  const handleResolveAlert = useCallback(
    (feedback: FeedbackPublic) => {
      const note = window.prompt('Registrar observação de encaminhamento (opcional):')
      if (note === null) return
      void (async () => {
        await triggerAlerts.resolveAlert(feedback.id, note || undefined)
        await resolvedAlerts.loadAlerts()
      })()
    },
    [triggerAlerts, resolvedAlerts],
  )

  const renderSection = () => {
    switch (activeSection) {
      case 'overview':
        return (
          <div className="space-y-6">
            <GestorOverviewSection
              stats={stats}
              loading={feedbacksLoading}
              notice={feedbacksNotice}
              onRefresh={loadFeedbacks}
            />
            <GestorAnalyticsPanel
              loading={feedbacksLoading}
              analytics={analytics}
              onSelectUser={handleOpenProfile}
            />
          </div>
        )
      case 'compose':
        return (
          <FeedbackComposer
            title="Novo comunicado da coordenação"
            helperText="Envie orientações institucionais para docentes, estudantes ou turmas."
            onSuccess={() => {
              void loadFeedbacks()
            }}
          />
        )
      case 'insights':
        return (
          <div className="space-y-5">
          <InsightSummaryCard
            summary={summary}
            summaryLoading={summaryLoading}
            summaryStatus={summaryStatus}
            onGenerate={loadSummary}
          />
            <MayaHistory role="gestor" summary={summary} />
          </div>
        )
      case 'feedbacks':
        return (
          <RecentFeedbackTable
            feedbacks={feedbacks}
            loading={feedbacksLoading}
            message={feedbacksNotice}
            onRefresh={loadFeedbacks}
            canPurge={isAdmin}
            onDeleteAll={isAdmin ? handleDeleteAllFeedbacks : undefined}
            purgeStatus={feedbackPurgeStatus}
            purgeLoading={feedbackPurgeLoading}
            onDeleteFeedback={handleDeleteSingleFeedback}
            statusMessage={feedbackActionStatus}
          />
        )
      case 'alerts':
        return (
          <div className="space-y-6">
            <div className="grid grid-cols-2 gap-3 sm:max-w-md">
              <div className="card p-4 border-l-4 border-l-rose-600">
                <p className="text-xs font-medium text-slate-500">Pendentes de análise</p>
                <p className="text-2xl font-bold text-rose-700 mt-1 tabular-nums">
                  {triggerAlerts.alerts.length}
                </p>
              </div>
              <div className="card p-4 border-l-4 border-l-emerald-500">
                <p className="text-xs font-medium text-slate-500">Concluídos</p>
                <p className="text-2xl font-bold text-emerald-700 mt-1 tabular-nums">
                  {resolvedAlerts.alerts.length}
                </p>
              </div>
            </div>

            <div className="grid gap-6 lg:grid-cols-2">
              <TriggerAlertFeed
                title="Ocorrências em aberto"
                subtitle="Relatos sinalizados por termos sensíveis ou docentes"
                alerts={triggerAlerts.alerts}
                loading={triggerAlerts.loading}
                infoMessage={triggerAlerts.notice}
                statusMessage={feedbackActionStatus}
                onRefresh={triggerAlerts.loadAlerts}
                onDeleteFeedback={isAdmin ? handleDeleteSingleFeedback : undefined}
                onResolveAlert={handleResolveAlert}
                resolvingId={triggerAlerts.resolvingId}
                badgeLabel="Em aberto"
              />
              <TriggerKeywordsCard
                keywords={triggerKeywords.keywords}
                loading={triggerKeywords.loading}
                error={triggerKeywords.error}
                status={triggerKeywords.status}
                submitting={triggerKeywords.submitting}
                scopeLabel={isAdmin ? 'toda a rede' : 'a sua unidade'}
                onAdd={triggerKeywords.handleCreate}
                onDelete={triggerKeywords.handleDelete}
              />
            </div>

            <TriggerAlertFeed
              title="Histórico de casos acompanhados"
              subtitle="Ocorrências já tratadas pela coordenação"
              alerts={resolvedAlerts.alerts}
              loading={resolvedAlerts.loading}
              infoMessage={resolvedAlerts.notice}
              onRefresh={resolvedAlerts.loadAlerts}
              badgeLabel="Concluído"
            />
          </div>
        )
      case 'directory':
        return (
          <div className="space-y-6">
            <UserRegistrationCard
              form={usersState.userForm}
              onChange={(updates) =>
                usersState.setUserForm((prev: UserFormState) => ({ ...prev, ...updates }))
              }
              onSubmit={usersState.handleUserSubmit}
              submitting={usersState.userFormSubmitting}
              statusMessage={usersState.userFormStatus}
              isAdmin={isAdmin}
              isManager={isManager}
              visibleSchools={referenceData.visibleSchools}
              subjects={subjectsState.subjects}
              classrooms={classroomsState.classrooms}
              mode={usersState.userFormMode}
              onCancelEdit={usersState.resetUserForm}
            />
            <UsersTableCard
              users={usersState.filteredUsers}
              loading={usersState.usersLoading}
              error={usersState.usersError}
              roleFilter={usersState.roleFilter}
              onChangeRoleFilter={handleRoleFilterChange}
              onDeleteUser={usersState.handleDeleteUser}
              onEditUser={usersState.startEditUser}
              userActionStatus={usersState.userActionStatus}
              sessionUserId={session?.id}
              schoolMap={referenceData.schoolMap}
              subjectMap={referenceData.subjectMap}
              classroomMap={referenceData.classroomMap}
            />
          </div>
        )
      case 'teachers': {
        const hasSubjects = subjectsState.subjects.length > 0
        return (
          <div className="space-y-6">
            <UserRegistrationCard
              form={usersState.userForm}
              onChange={(updates) =>
                usersState.setUserForm((prev: UserFormState) => ({ ...prev, ...updates }))
              }
              onSubmit={usersState.handleUserSubmit}
              submitting={usersState.userFormSubmitting}
              statusMessage={usersState.userFormStatus}
              isAdmin={isAdmin}
              isManager={isManager}
              visibleSchools={referenceData.visibleSchools}
              subjects={subjectsState.subjects}
              classrooms={classroomsState.classrooms}
              mode={usersState.userFormMode}
              onCancelEdit={usersState.resetUserForm}
              allowedRoles={['professor']}
              disabled={!hasSubjects}
              disabledReason={
                hasSubjects
                  ? null
                  : 'Cadastre ao menos uma matéria antes de registrar professores.'
              }
            />
            <UsersTableCard
              users={usersState.filteredUsers}
              loading={usersState.usersLoading}
              error={usersState.usersError}
              roleFilter={usersState.roleFilter}
              onChangeRoleFilter={handleRoleFilterChange}
              onDeleteUser={usersState.handleDeleteUser}
              onEditUser={usersState.startEditUser}
              userActionStatus={usersState.userActionStatus}
              sessionUserId={session?.id}
              schoolMap={referenceData.schoolMap}
              subjectMap={referenceData.subjectMap}
              classroomMap={referenceData.classroomMap}
            />
          </div>
        )
      }
      case 'students': {
        const hasClassrooms = classroomsState.classrooms.length > 0
        return (
          <div className="space-y-6">
            <UserRegistrationCard
              form={usersState.userForm}
              onChange={(updates) =>
                usersState.setUserForm((prev: UserFormState) => ({ ...prev, ...updates }))
              }
              onSubmit={usersState.handleUserSubmit}
              submitting={usersState.userFormSubmitting}
              statusMessage={usersState.userFormStatus}
              isAdmin={isAdmin}
              isManager={isManager}
              visibleSchools={referenceData.visibleSchools}
              subjects={subjectsState.subjects}
              classrooms={classroomsState.classrooms}
              mode={usersState.userFormMode}
              onCancelEdit={usersState.resetUserForm}
              allowedRoles={['aluno']}
              disabled={!hasClassrooms}
              disabledReason={
                hasClassrooms ? null : 'Crie uma turma antes de cadastrar estudantes.'
              }
            />
            <UsersTableCard
              users={usersState.filteredUsers}
              loading={usersState.usersLoading}
              error={usersState.usersError}
              roleFilter={usersState.roleFilter}
              onChangeRoleFilter={handleRoleFilterChange}
              onDeleteUser={usersState.handleDeleteUser}
              onEditUser={usersState.startEditUser}
              userActionStatus={usersState.userActionStatus}
              sessionUserId={session?.id}
              schoolMap={referenceData.schoolMap}
              subjectMap={referenceData.subjectMap}
              classroomMap={referenceData.classroomMap}
            />
          </div>
        )
      }
      case 'managers': {
        if (!isAdmin) return null
        return (
          <div className="space-y-6">
            <UserRegistrationCard
              form={usersState.userForm}
              onChange={(updates) =>
                usersState.setUserForm((prev: UserFormState) => ({ ...prev, ...updates }))
              }
              onSubmit={usersState.handleUserSubmit}
              submitting={usersState.userFormSubmitting}
              statusMessage={usersState.userFormStatus}
              isAdmin={isAdmin}
              isManager={isManager}
              visibleSchools={referenceData.visibleSchools}
              subjects={subjectsState.subjects}
              classrooms={classroomsState.classrooms}
              mode={usersState.userFormMode}
              onCancelEdit={usersState.resetUserForm}
              allowedRoles={['gestor']}
            />
            <UsersTableCard
              users={usersState.filteredUsers}
              loading={usersState.usersLoading}
              error={usersState.usersError}
              roleFilter={usersState.roleFilter}
              onChangeRoleFilter={handleRoleFilterChange}
              onDeleteUser={usersState.handleDeleteUser}
              onEditUser={usersState.startEditUser}
              userActionStatus={usersState.userActionStatus}
              sessionUserId={session?.id}
              schoolMap={referenceData.schoolMap}
              subjectMap={referenceData.subjectMap}
              classroomMap={referenceData.classroomMap}
            />
          </div>
        )
      }
      case 'schools':
        return (
          <SchoolsCatalogCard
            schools={schoolsState.schools}
            loading={schoolsState.schoolsLoading}
            error={schoolsState.schoolsError}
            form={schoolsState.schoolForm}
            onChange={(updates) =>
              schoolsState.setSchoolForm((prev) => ({ ...prev, ...updates }))
            }
            formMode={schoolsState.schoolFormMode}
            submitting={schoolsState.schoolFormSubmitting}
            statusMessage={schoolsState.schoolFormStatus}
            onSubmit={schoolsState.handleSchoolSubmit}
            onEdit={schoolsState.startEditSchool}
            onDelete={schoolsState.handleDeleteSchool}
            onReset={schoolsState.resetSchoolForm}
          />
        )
      case 'subjects':
        return (
          <SubjectsCatalogCard
            subjects={subjectsState.subjects}
            loading={subjectsState.subjectsLoading}
            error={subjectsState.subjectsError}
            form={subjectsState.subjectForm}
            onChange={(updates) =>
              subjectsState.setSubjectForm((prev: SubjectFormState) => ({
                ...prev,
                ...updates,
              }))
            }
            formMode={subjectsState.subjectFormMode}
            submitting={subjectsState.subjectFormSubmitting}
            statusMessage={subjectsState.subjectFormStatus}
            onSubmit={subjectsState.handleSubjectSubmit}
            onEdit={subjectsState.startEditSubject}
            onDelete={subjectsState.handleDeleteSubject}
            onReset={subjectsState.resetSubjectForm}
            visibleSchools={referenceData.visibleSchools}
            schoolMap={referenceData.schoolMap}
          />
        )
      case 'classrooms':
        return (
          <ClassroomsCatalogCard
            classrooms={classroomsState.classrooms}
            loading={classroomsState.classroomsLoading}
            error={classroomsState.classroomsError}
            form={classroomsState.classroomForm}
            onChange={(updates) =>
              classroomsState.setClassroomForm((prev: ClassroomFormState) => ({
                ...prev,
                ...updates,
              }))
            }
            formMode={classroomsState.classroomFormMode}
            submitting={classroomsState.classroomFormSubmitting}
            statusMessage={classroomsState.classroomFormStatus}
            onSubmit={classroomsState.handleClassroomSubmit}
            onEdit={classroomsState.startEditClassroom}
            onDelete={classroomsState.handleDeleteClassroom}
            onReset={classroomsState.resetClassroomForm}
            visibleSchools={referenceData.visibleSchools}
            subjects={subjectsState.subjects}
            subjectMap={referenceData.subjectMap}
            schoolMap={referenceData.schoolMap}
          />
        )
      case 'assignments':
        return (
          <ClassroomAssignmentsPanel
            classrooms={classroomsState.classrooms}
            subjects={subjectsState.subjects}
            teachers={professorDirectory}
            subjectMap={referenceData.subjectMap}
          />
        )
      default:
        return null
    }
  }

  const currentMeta = SECTION_META[activeSection]

  return (
    <>
      <AppShell
        userName={session?.fullName ?? (isAdmin ? 'Administrador' : 'Coordenação')}
        userEmail={session?.email}
        roleLabel={isAdmin ? 'Admin' : 'Gestão'}
        pageTitle={currentMeta.title}
        pageSubtitle={currentMeta.subtitle}
        items={navItems}
        bottomNavIds={['overview', 'feedbacks', 'alerts', 'insights', 'compose']}
        activeId={activeSection}
        onSelect={setActiveSection}
        onLogout={logout}
        onRefresh={loadFeedbacks}
        refreshLoading={feedbacksLoading}
        refreshLabel="Sincronizar"
      >
        {renderSection()}
      </AppShell>

      {selectedProfile && (
        <UserProfileDrawer
          profile={selectedProfile}
          onClose={handleCloseProfile}
          sentFeedbacks={selectedProfileSent}
          receivedFeedbacks={selectedProfileReceived}
        />
      )}
    </>
  )
}
