import { MayaHistory } from '../components/maya/MayaHistory'
import { useEffect, useMemo, useState } from 'react'
import { Home, Inbox, PenSquare, Send, Sparkles } from 'lucide-react'

import { FeedbackComposer } from '../components/feedback/FeedbackComposer'
import { AppShell, type NavItem } from '../components/layout/AppShell'
import { FeedbackListSection } from '../components/personal/FeedbackListSection'
import { PersonalOverview } from '../components/personal/PersonalOverview'
import { PersonalSummaryCard } from '../components/personal/PersonalSummaryCard'
import { PersonalWelcome } from '../components/personal/PersonalWelcome'
import { useAuth } from '../context/AuthContext'
import { usePersonalFeedbacks } from '../hooks/usePersonalFeedbacks'

type Section = 'welcome' | 'compose' | 'received' | 'sent' | 'insights'

const SECTION_META: Record<Section, { title: string; subtitle: string }> = {
  welcome: {
    title: 'Início',
    subtitle: 'Acompanhe seus retornos e compartilhe percepções sobre suas aulas.',
  },
  compose: {
    title: 'Novo relato',
    subtitle: 'Envie uma mensagem para suas matérias, docentes ou coordenação.',
  },
  received: {
    title: 'Caixa de entrada',
    subtitle: 'Mensagens e orientações enviadas pela equipe escolar para você.',
  },
  sent: {
    title: 'Enviados',
    subtitle: 'Histórico de relatos registrados pela sua conta.',
  },
  insights: {
    title: 'Síntese com IA',
    subtitle: 'Resumo consolidado dos retornos que você recebeu.',
  },
}

export default function Aluno() {
  const { session, logout } = useAuth()
  const [activeSection, setActiveSection] = useState<Section>('welcome')
  const {
    feedbacks,
    visibleSent,
    filteredReceived,
    loading,
    notice,
    actionStatus,
    stats,
    filter,
    setFilter,
    summary,
    summaryStatus,
    summaryLoading,
    loadFeedbacks,
    handleSummary,
    hideSentFeedback,
  } = usePersonalFeedbacks()

  useEffect(() => {
    void loadFeedbacks()
  }, [loadFeedbacks])

  const navItems: Array<NavItem<Section>> = useMemo(
    () => [
      { id: 'welcome', label: 'Início', icon: Home },
      { id: 'compose', label: 'Enviar relato', shortLabel: 'Enviar', icon: PenSquare },
      {
        id: 'received',
        label: 'Recebidos',
        icon: Inbox,
        badge: feedbacks.received.length || undefined,
      },
      { id: 'sent', label: 'Enviados', icon: Send },
      { id: 'insights', label: 'Síntese IA', shortLabel: 'Síntese', icon: Sparkles },
    ],
    [feedbacks.received.length],
  )

  const renderSection = () => {
    switch (activeSection) {
      case 'welcome':
        return (
          <div className="space-y-5">
            <PersonalWelcome
              roleLabel={session?.fullName || 'Estudante'}
              tips={[
                'Seja específico ao comentar sobre aulas ou atividades.',
                'Acompanhe respostas da coordenação e professores em Recebidos.',
                'Seus relatos são protegidos por criptografia em trânsito e em repouso.',
              ]}
              actions={[
                {
                  label: 'Escrever novo relato',
                  target: 'compose',
                  description: 'Envie percepções sobre uma matéria, professor ou coordenação.',
                },
                {
                  label: 'Consultar retornos recebidos',
                  target: 'received',
                  description: 'Veja orientações encaminhadas diretamente para você.',
                },
              ]}
              onNavigate={setActiveSection}
            />
            <PersonalOverview stats={stats} notice={notice} loading={loading} />
          </div>
        )
      case 'compose':
        return (
          <FeedbackComposer
            title="Compartilhar percepção"
            helperText="Escolha a matéria ou profissional correspondente e descreva sua observação."
            onSuccess={() => {
              void loadFeedbacks()
            }}
          />
        )
      case 'received':
        return (
          <FeedbackListSection
            title="Mensagens recebidas"
            items={filteredReceived}
            loading={loading}
            infoMessage={notice}
            emptyMessage="Você ainda não recebeu retornos da equipe escolar."
            badgeLabel="Recebido"
            allowFilter
            filter={filter}
            onFilterChange={setFilter}
            onRefresh={loadFeedbacks}
            showTriggerBadge={false}
          />
        )
      case 'sent':
        return (
          <FeedbackListSection
            title="Relatos enviados"
            items={visibleSent}
            loading={loading}
            infoMessage={notice}
            emptyMessage="Você ainda não enviou nenhum relato."
            badgeLabel="Enviado"
            hideClassification
            onRefresh={loadFeedbacks}
            onDeleteItem={hideSentFeedback}
            deleteLabel="Ocultar da lista"
            actionStatus={actionStatus}
            showTriggerBadge={false}
          />
        )
      case 'insights':
        return (
          <div className="space-y-5">
          <PersonalSummaryCard
            summary={summary}
            summaryLoading={summaryLoading}
            summaryStatus={summaryStatus}
            onGenerate={handleSummary}
          />
            <MayaHistory role="aluno" summary={summary} />
          </div>
        )
      default:
        return null
    }
  }

  const currentMeta = SECTION_META[activeSection]

  return (
    <AppShell
      userName={session?.fullName || 'Estudante'}
      userEmail={session?.email}
      roleLabel="Aluno"
      pageTitle={currentMeta.title}
      pageSubtitle={currentMeta.subtitle}
      items={navItems}
      bottomNavIds={['welcome', 'compose', 'received', 'sent', 'insights']}
      activeId={activeSection}
      onSelect={setActiveSection}
      onLogout={logout}
      onRefresh={loadFeedbacks}
      refreshLoading={loading}
    >
      {renderSection()}
    </AppShell>
  )
}
