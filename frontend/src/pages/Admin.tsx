import { useCallback, useEffect, useMemo, useState } from 'react'
import { Activity, BarChart3, Building2, MessageSquare, Users } from 'lucide-react'

import { useAuth } from '../context/AuthContext'
import { ActionModal } from '../components/layout/ActionModal'
import { AppShell, type NavItem } from '../components/layout/AppShell'
import { useAdminMetrics } from '../hooks/useAdminMetrics'
import { AdminMetricsGrid } from '../components/admin/AdminMetricsGrid'
import { AdminHealthPanel } from '../components/admin/AdminHealthPanel'
import { AdminSchoolManager } from '../components/admin/AdminSchoolManager'
import { useGestorDirectory, type UserFormState } from '../hooks/useGestorDirectory'
import { UserRegistrationCard } from '../components/gestor/UserRegistrationCard'
import { UsersTableCard } from '../components/gestor/UsersTableCard'
import { useGestorOverview } from '../hooks/useGestorOverview'
import { RecentFeedbackTable } from '../components/gestor/RecentFeedbackTable'
import { deleteFeedback } from '../lib/api'

type AdminSection = 'overview' | 'schools' | 'users' | 'feedbacks' | 'health'

const NAV_ITEMS: Array<NavItem<AdminSection>> = [
  { id: 'overview', label: 'Visão geral', shortLabel: 'Painel', icon: BarChart3, group: 'Rede' },
  { id: 'schools', label: 'Escolas', icon: Building2, group: 'Rede' },
  { id: 'users', label: 'Usuários', icon: Users, group: 'Rede' },
  { id: 'feedbacks', label: 'Relatos', icon: MessageSquare, group: 'Auditoria' },
  { id: 'health', label: 'Diagnóstico', shortLabel: 'Status', icon: Activity, group: 'Sistema' },
]

const SECTION_META: Record<AdminSection, { title: string; subtitle: string }> = {
  overview: {
    title: 'Administração da Rede',
    subtitle: 'Indicadores globais das unidades, cadastros e relatos ativos.',
  },
  schools: {
    title: 'Unidades Escolares',
    subtitle: 'Gerencie as escolas e instituições habilitadas no Echora.',
  },
  users: {
    title: 'Usuários e Permissões',
    subtitle: 'Administração de gestores, docentes e estudantes por unidade.',
  },
  feedbacks: {
    title: 'Auditoria de Relatos',
    subtitle: 'Consulta global de feedbacks com filtro por instituição.',
  },
  health: {
    title: 'Status Operacional',
    subtitle: 'Monitoramento de disponibilidade do banco de dados e serviços de IA.',
  },
}

export default function Admin() {
  const { session, logout } = useAuth()
  const [activeSection, setActiveSection] = useState<AdminSection>('overview')
  const [directoryInitialized, setDirectoryInitialized] = useState(false)
  const [feedbackActionStatus, setFeedbackActionStatus] = useState<string | null>(null)
  const [pendingDeleteFeedbackId, setPendingDeleteFeedbackId] = useState<number | null>(null)
  const [deleteBusy, setDeleteBusy] = useState(false)
  const [userSchoolFilter, setUserSchoolFilter] = useState<string>('all')
  const [feedbackSchoolFilter, setFeedbackSchoolFilter] = useState<string>('all')
  const selectedFeedbackSchoolId =
    feedbackSchoolFilter === 'all' ? null : Number(feedbackSchoolFilter)

  const adminMetrics = useAdminMetrics()
  const overview = useGestorOverview({
    isAdmin: true,
    managerSchoolId: null,
    adminSchoolFilterId: selectedFeedbackSchoolId,
  })
  const directory = useGestorDirectory({ isAdmin: true, isManager: false, managerSchoolId: null })

  const {
    initializeDirectory,
    usersState,
    subjectsState,
    classroomsState,
    referenceData,
  } = directory
  const availableSchools = referenceData?.visibleSchools ?? []

  useEffect(() => {
    void overview.loadFeedbacks()
  }, [overview.loadFeedbacks])

  useEffect(() => {
    if (!directoryInitialized) {
      setDirectoryInitialized(true)
      void initializeDirectory()
    }
  }, [directoryInitialized, initializeDirectory])

  const filteredUsers = useMemo(() => {
    if (userSchoolFilter === 'all') return usersState.filteredUsers
    const schoolId = Number(userSchoolFilter)
    return usersState.filteredUsers.filter((user) => (user.school_id ?? null) === schoolId)
  }, [usersState.filteredUsers, userSchoolFilter])

  const handleDeleteSingleFeedback = useCallback((feedbackId: number) => {
    setPendingDeleteFeedbackId(feedbackId)
  }, [])

  const handleConfirmDeleteFeedback = useCallback(async () => {
    if (pendingDeleteFeedbackId === null) return
    setDeleteBusy(true)
    setFeedbackActionStatus('Removendo relato...')
    try {
      await deleteFeedback(pendingDeleteFeedbackId)
      setFeedbackActionStatus('Relato removido.')
      setPendingDeleteFeedbackId(null)
      await overview.loadFeedbacks()
    } catch (error: any) {
      setFeedbackActionStatus(error?.message || 'Não foi possível remover o relato.')
    } finally {
      setDeleteBusy(false)
    }
  }, [pendingDeleteFeedbackId, overview])

  const renderSection = () => {
    switch (activeSection) {
      case 'overview':
        return (
          <AdminMetricsGrid
            metrics={adminMetrics.overview}
            loading={adminMetrics.overviewLoading}
            onRefresh={adminMetrics.loadOverview}
          />
        )
      case 'health':
        return (
          <AdminHealthPanel
            health={adminMetrics.health}
            loading={adminMetrics.healthLoading}
            onRefresh={adminMetrics.loadHealth}
          />
        )
      case 'schools':
        return <AdminSchoolManager />
      case 'users':
        return (
          <div className="space-y-6">
            <div className="card p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-slate-900">Filtrar por unidade escolar</p>
                <p className="text-xs text-slate-500">
                  Restrinja a listagem abaixo a uma instituição específica.
                </p>
              </div>
              <select
                className="input sm:w-72"
                value={userSchoolFilter}
                onChange={(event) => setUserSchoolFilter(event.target.value)}
              >
                <option value="all">Todas as unidades</option>
                {availableSchools.map((school) => (
                  <option key={school.id} value={school.id}>
                    {school.name}
                  </option>
                ))}
              </select>
            </div>

            <UserRegistrationCard
              form={usersState.userForm}
              onChange={(updates) =>
                usersState.setUserForm((prev: UserFormState) => ({ ...prev, ...updates }))
              }
              onSubmit={usersState.handleUserSubmit}
              submitting={usersState.userFormSubmitting}
              statusMessage={usersState.userFormStatus}
              isAdmin
              isManager={false}
              visibleSchools={referenceData.visibleSchools}
              subjects={subjectsState.subjects}
              classrooms={classroomsState.classrooms}
              mode={usersState.userFormMode}
              onCancelEdit={usersState.resetUserForm}
            />

            <UsersTableCard
              users={filteredUsers}
              loading={usersState.usersLoading}
              error={usersState.usersError}
              roleFilter={usersState.roleFilter}
              onChangeRoleFilter={usersState.setRoleFilter}
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
      case 'feedbacks':
        return (
          <div className="space-y-5">
            <div className="card p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-slate-900">Unidade monitorada</p>
                <p className="text-xs text-slate-500">
                  Visualize todos os registros da rede ou filtre por escola.
                </p>
              </div>
              <select
                className="input sm:w-72"
                value={feedbackSchoolFilter}
                onChange={(event) => setFeedbackSchoolFilter(event.target.value)}
              >
                <option value="all">Todas as unidades</option>
                {availableSchools.map((school) => (
                  <option key={school.id} value={school.id}>
                    {school.name}
                  </option>
                ))}
              </select>
            </div>

            <RecentFeedbackTable
              feedbacks={overview.feedbacks}
              loading={overview.feedbacksLoading}
              message={overview.feedbacksNotice}
              onRefresh={overview.loadFeedbacks}
              canPurge
              onDeleteAll={overview.handleDeleteAllFeedbacks}
              purgeStatus={overview.feedbackPurgeStatus}
              purgeLoading={overview.feedbackPurgeLoading}
              onDeleteFeedback={handleDeleteSingleFeedback}
              statusMessage={feedbackActionStatus}
            />
          </div>
        )
      default:
        return null
    }
  }

  const currentMeta = SECTION_META[activeSection]

  return (
    <>
      <AppShell
        userName={session?.fullName || 'Administrador'}
        userEmail={session?.email}
        roleLabel="Admin"
        pageTitle={currentMeta.title}
        pageSubtitle={currentMeta.subtitle}
        items={NAV_ITEMS}
        bottomNavIds={['overview', 'schools', 'users', 'feedbacks', 'health']}
        activeId={activeSection}
        onSelect={setActiveSection}
        onLogout={logout}
        onRefresh={adminMetrics.loadOverview}
        refreshLoading={adminMetrics.overviewLoading}
        refreshLabel="Atualizar painel"
      >
        {adminMetrics.error && (
          <div className="rounded-lg bg-rose-50 border border-rose-200 px-4 py-3 text-sm text-rose-700">
            {adminMetrics.error}
          </div>
        )}
        {renderSection()}
      </AppShell>

      <ActionModal
        open={pendingDeleteFeedbackId !== null}
        mode="confirm"
        tone="danger"
        title="Excluir relato"
        description="Deseja excluir permanentemente este relato? Esta ação não pode ser desfeita."
        confirmLabel="Excluir relato"
        loading={deleteBusy}
        onConfirm={handleConfirmDeleteFeedback}
        onClose={() => setPendingDeleteFeedbackId(null)}
      />
    </>
  )
}
