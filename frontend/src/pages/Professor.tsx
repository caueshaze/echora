import { MayaHistory } from '../components/maya/MayaHistory'
import { useEffect, useMemo, useState } from 'react'
import {
  BarChart3,
  Home,
  Inbox,
  PenSquare,
  Send,
  ShieldAlert,
  Sparkles,
} from 'lucide-react'

import { FeedbackComposer } from '../components/feedback/FeedbackComposer'
import { AppShell, type NavItem } from '../components/layout/AppShell'
import { FeedbackListSection } from '../components/personal/FeedbackListSection'
import { PersonalOverview } from '../components/personal/PersonalOverview'
import { PersonalSummaryCard } from '../components/personal/PersonalSummaryCard'
import { PersonalWelcome } from '../components/personal/PersonalWelcome'
import { useAuth } from '../context/AuthContext'
import { usePersonalFeedbacks } from '../hooks/usePersonalFeedbacks'
import { useTriggerAlerts } from '../hooks/useTriggerAlerts'
import { reportFeedback } from '../lib/api'
import type { FeedbackPublic } from '../lib/types'

type Section = 'welcome' | 'received' | 'compose' | 'sent' | 'alerts' | 'insights' | 'overview'

const SECTION_META: Record<Section, { title: string; subtitle: string }> = {
  welcome: {
    title: 'Área Docente',
    subtitle: 'Acompanhe a escuta das suas turmas e envie orientações.',
  },
  overview: {
    title: 'Indicadores',
    subtitle: 'Distribuição dos retornos recebidos nas suas disciplinas.',
  },
  compose: {
    title: 'Enviar orientação',
    subtitle: 'Encaminhe comunicados ou feedbacks para alunos, turmas ou gestão.',
  },
  received: {
    title: 'Retornos das turmas',
    subtitle: 'Percepções enviadas pelos estudantes nas suas matérias.',
  },
  sent: {
    title: 'Enviados',
    subtitle: 'Histórico de mensagens encaminhadas por você.',
  },
  alerts: {
    title: 'Pontos de atenção',
    subtitle: 'Relatos sinalizados preventivamente para acompanhamento.',
  },
  insights: {
    title: 'Síntese com IA',
    subtitle: 'Leitura consolidada dos principais pontos citados pelas turmas.',
  },
}

export default function Professor() {
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
  const triggerAlerts = useTriggerAlerts()
  const [reportStatus, setReportStatus] = useState<string | null>(null)

  useEffect(() => {
    void loadFeedbacks()
  }, [loadFeedbacks])

  const navItems: Array<NavItem<Section>> = useMemo(
    () => [
      { id: 'welcome', label: 'Início', icon: Home, group: 'Acompanhamento' },
      {
        id: 'received',
        label: 'Recebidos',
        icon: Inbox,
        group: 'Acompanhamento',
        badge: feedbacks.received.length || undefined,
      },
      { id: 'compose', label: 'Comunicar', icon: PenSquare, group: 'Acompanhamento' },
      { id: 'sent', label: 'Enviados', icon: Send, group: 'Acompanhamento' },
      { id: 'overview', label: 'Indicadores', icon: BarChart3, group: 'Análise' },
      {
        id: 'alerts',
        label: 'Atenção',
        icon: ShieldAlert,
        group: 'Análise',
        badge: triggerAlerts.alerts.length || undefined,
      },
      { id: 'insights', label: 'Síntese IA', shortLabel: 'Síntese', icon: Sparkles, group: 'Análise' },
    ],
    [feedbacks.received.length, triggerAlerts.alerts.length],
  )

  const handleReportFeedback = async (feedback: FeedbackPublic) => {
    if (feedback.has_trigger) {
      setReportStatus('Este relato já está sinalizado para análise da gestão.')
      return
    }
    const reason = window.prompt('Informe brevemente o motivo para encaminhar à coordenação:')
    if (reason === null) {
      return
    }
    const trimmed = reason.trim()
    if (trimmed.length < 5) {
      setReportStatus('Descreva o motivo com pelo menos 5 caracteres.')
      return
    }
    setReportStatus('Encaminhando para a coordenação...')
    try {
      await reportFeedback(feedback.id, { reason: trimmed })
      setReportStatus('Relato encaminhado para acompanhamento da gestão.')
      await Promise.all([loadFeedbacks(), triggerAlerts.loadAlerts()])
    } catch (error: any) {
      setReportStatus(error?.message || 'Não foi possível sinalizar este relato.')
    }
  }

  const renderSection = () => {
    switch (activeSection) {
      case 'welcome':
        return (
          <div className="space-y-5">
            <PersonalWelcome
              roleLabel={session?.fullName || 'Professor(a)'}
              tips={[
                'Consulte os retornos filtrando por clima positivo, neutro ou atenção.',
                'Caso identifique um relato sensível, encaminhe à coordenação em um clique.',
                'Use a Síntese com IA para identificar padrões das turmas rapidamente.',
              ]}
              actions={[
                {
                  label: 'Ler retornos das turmas',
                  target: 'received',
                  description: 'Veja as percepções mais recentes sobre suas aulas e disciplinas.',
                },
                {
                  label: 'Enviar orientação ou retorno',
                  target: 'compose',
                  description: 'Comunique-se diretamente com estudantes, turmas ou gestão.',
                },
              ]}
              onNavigate={setActiveSection}
            />
            <PersonalOverview stats={stats} notice={notice} loading={loading} />
          </div>
        )
      case 'overview':
        return <PersonalOverview stats={stats} notice={notice} loading={loading} />
      case 'compose':
        return (
          <FeedbackComposer
            title="Nova comunicação"
            helperText="Envie orientações pedagógicas para alunos, turmas ou equipe gestora."
            onSuccess={() => {
              void loadFeedbacks()
            }}
          />
        )
      case 'received':
        return (
          <FeedbackListSection
            title="Retornos recebidos"
            items={filteredReceived}
            loading={loading}
            infoMessage={notice}
            emptyMessage="Nenhum relato recebido nas suas turmas até o momento."
            badgeLabel="Turma"
            allowFilter
            filter={filter}
            onFilterChange={setFilter}
            onRefresh={loadFeedbacks}
            onSecondaryAction={handleReportFeedback}
            secondaryActionLabel="Encaminhar à gestão"
            actionStatus={reportStatus}
          />
        )
      case 'sent':
        return (
          <FeedbackListSection
            title="Comunicações enviadas"
            items={visibleSent}
            loading={loading}
            infoMessage={notice}
            emptyMessage="Você ainda não enviou comunicações."
            badgeLabel="Enviado"
            hideClassification
            onRefresh={loadFeedbacks}
            onDeleteItem={hideSentFeedback}
            deleteLabel="Ocultar"
            actionStatus={actionStatus}
          />
        )
      case 'alerts':
        return (
          <FeedbackListSection
            title="Relatos em atenção"
            items={triggerAlerts.alerts}
            loading={triggerAlerts.loading}
            infoMessage={triggerAlerts.notice}
            emptyMessage="Nenhum alerta ativo vinculado às suas turmas."
            badgeLabel="Atenção"
            onRefresh={triggerAlerts.loadAlerts}
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
            <MayaHistory role="professor" summary={summary} />
          </div>
        )
      default:
        return null
    }
  }

  const currentMeta = SECTION_META[activeSection]

  return (
    <AppShell
      userName={session?.fullName || 'Professor(a)'}
      userEmail={session?.email}
      roleLabel="Docente"
      pageTitle={currentMeta.title}
      pageSubtitle={currentMeta.subtitle}
      items={navItems}
      bottomNavIds={['welcome', 'received', 'compose', 'alerts', 'insights']}
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
