import { FormEvent, useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import {
  ArrowRight,
  BookOpen,
  CheckCircle2,
  ChevronDown,
  Lock,
  MessageSquare,
  Send,
  ShieldAlert,
  Sparkles,
  Users,
} from 'lucide-react'

import { Navbar } from '../components/layout/Navbar'
import { Footer } from '../components/layout/Footer'

type RoleTab = 'gestor' | 'professor' | 'aluno'

const ROLE_DETAILS: Record<
  RoleTab,
  {
    badge: string
    title: string
    description: string
    bullets: string[]
  }
> = {
  gestor: {
    badge: 'Coordenação e Direção',
    title: 'Visão clara do clima de cada turma sem planilhas soltas',
    description:
      'Acompanhe indicadores de participação, identifique disciplinas que precisam de apoio e trate relatos sensíveis com registro de encaminhamento.',
    bullets: [
      'Painel consolidado por unidade, série, turma e matéria',
      'Fila prioritária para relatos sinalizados por termos de risco',
      'Síntese executiva assistida para reuniões pedagógicas',
    ],
  },
  professor: {
    badge: 'Corpo Docente',
    title: 'Retorno contínuo das turmas com organização por disciplina',
    description:
      'Receba percepções dos estudantes vinculadas às suas matérias, envie orientações para a turma e acione a coordenação quando necessário.',
    bullets: [
      'Caixa de entrada filtrada por clima positivo, neutro ou atenção',
      'Envio rápido de comunicados para turmas ou alunos específicos',
      'Encaminhamento em um toque para apoio da equipe gestora',
    ],
  },
  aluno: {
    badge: 'Estudantes',
    title: 'Espaço direto e respeitoso para ser ouvido pela escola',
    description:
      'Pelo celular ou computador, o aluno compartilha percepções sobre aulas e convivência sabendo exatamente quem receberá a mensagem.',
    bullets: [
      'Interface leve pensada para uso rápido no celular',
      'Seleção guiada apenas das matérias e equipe da própria turma',
      'Acompanhamento das respostas enviadas pela coordenação e docentes',
    ],
  },
}

const STEPS = [
  {
    icon: MessageSquare,
    title: '1. Relato contextualizado',
    copy: 'Estudantes e educadores registram feedbacks já vinculados à turma, disciplina ou profissional responsável.',
  },
  {
    icon: Sparkles,
    title: '2. Triagem automática',
    copy: 'O classificador analisa o tom da mensagem na hora e destaca situações sensíveis que exigem olhar imediato.',
  },
  {
    icon: CheckCircle2,
    title: '3. Retorno acompanhado',
    copy: 'Professores e gestores respondem, registram desfechos e acompanham a evolução do ambiente escolar.',
  },
]

const FAQ_ITEMS = [
  {
    question: 'O Echora substitui o atendimento presencial da coordenação?',
    answer:
      'Não. Ele organiza e antecipa demandas do dia a dia para que a equipe pedagógica saiba onde agir primeiro, fortalecendo o diálogo presencial.',
  },
  {
    question: 'Os relatos ficam abertos para outros alunos verem?',
    answer:
      'Nunca. Cada mensagem é restrita ao destinatário autorizado e cifrada no banco de dados com AES-256-GCM. Outros estudantes não têm acesso aos envios dos colegas.',
  },
  {
    question: 'Funciona para mais de uma escola ou rede de ensino?',
    answer:
      'Sim. A arquitetura é multiunidade: cada escola opera com suas próprias turmas, disciplinas e gestores de forma isolada, com visão global opcional para a mantenedora.',
  },
  {
    question: 'Os alunos precisam instalar algum aplicativo pesado?',
    answer:
      'Não é necessário instalar nada. O Echora funciona direto no navegador do celular ou computador com navegação adaptada para telas pequenas.',
  },
]

export default function LandingPage() {
  const [activeRole, setActiveRole] = useState<RoleTab>('gestor')
  const [openFaqIndex, setOpenFaqIndex] = useState<number | null>(0)
  const [contactStatus, setContactStatus] = useState<string | null>(null)
  const location = useLocation()

  useEffect(() => {
    if (!location.hash) return
    const target = location.hash.replace('#', '')
    requestAnimationFrame(() => {
      document.getElementById(target)?.scrollIntoView({ behavior: 'smooth' })
    })
  }, [location.hash])

  const handleContactSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setContactStatus('Mensagem registrada. Nossa equipe entrará em contato pelo e-mail informado.')
    event.currentTarget.reset()
  }

  const currentRole = ROLE_DETAILS[activeRole]

  return (
    <div className="min-h-screen bg-[#F6F8FA] text-slate-900 flex flex-col">
      <Navbar />

      <main className="flex-1">
        {/* Hero Section */}
        <section id="inicio" className="bg-white border-b border-slate-200/80">
          <div className="max-w-6xl mx-auto px-4 sm:px-6 py-12 sm:py-16 lg:py-20 grid gap-10 lg:grid-cols-[1.08fr_0.92fr] items-center">
            <div className="space-y-6">
              <div className="inline-flex items-center gap-2 rounded-full bg-brand-50 border border-brand-200/70 px-3 py-1 text-xs font-semibold text-brand-800">
                <span className="h-1.5 w-1.5 rounded-full bg-brand-600" />
                Clima escolar e escuta estruturada
              </div>

              <h1 className="text-3xl sm:text-4xl lg:text-[44px] font-bold leading-[1.15] text-slate-900">
                Aproxime alunos, professores e coordenação no dia a dia da escola.
              </h1>

              <p className="text-base sm:text-lg text-slate-600 leading-relaxed max-w-xl">
                O Echora organiza a comunicação pedagógica por turma e disciplina, identifica
                relatos urgentes automaticamente e ajuda a gestão a agir antes que pequenos ruídos
                virem problemas maiores.
              </p>

              <div className="flex flex-col sm:flex-row gap-3 pt-1">
                <Link to="/login" className="btn group py-3 px-6 text-sm">
                  Entrar na plataforma
                  <ArrowRight className="h-4 w-4 transition-transform duration-150 group-hover:translate-x-0.5" />
                </Link>
                <a href="#como-funciona" className="btn-secondary py-3 px-6 text-sm">
                  Ver como funciona
                </a>
              </div>

              <div className="pt-2 flex flex-wrap items-center gap-x-6 gap-y-2 text-xs text-slate-500">
                <span className="inline-flex items-center gap-1.5">
                  <Lock className="h-3.5 w-3.5 text-brand-700" />
                  Relatos cifrados (AES-256)
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <Users className="h-3.5 w-3.5 text-brand-700" />
                  Acesso separado por papel
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <BookOpen className="h-3.5 w-3.5 text-brand-700" />
                  Pronto para celular e PC
                </span>
              </div>
            </div>

            {/* Realistic Product Preview Card */}
            <div className="rounded-2xl border border-slate-200 bg-[#F6F8FA] p-3 sm:p-4 shadow-elevated">
              <div className="rounded-xl bg-white border border-slate-200/80 overflow-hidden">
                <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between bg-slate-50/60">
                  <div className="flex items-center gap-2">
                    <span className="h-2.5 w-2.5 rounded-full bg-brand-600" />
                    <span className="text-xs font-semibold text-slate-700">
                      Painel da Coordenação · 3º Ano A
                    </span>
                  </div>
                  <span className="text-[11px] font-medium text-slate-400">Tempo real</span>
                </div>

                <div className="p-4 space-y-3">
                  <div className="grid grid-cols-3 gap-2">
                    <div className="rounded-lg bg-slate-50 border border-slate-200/60 p-2.5">
                      <p className="text-[11px] text-slate-500">Relatos da semana</p>
                      <p className="text-lg font-bold text-slate-900 tabular-nums">48</p>
                    </div>
                    <div className="rounded-lg bg-emerald-50/60 border border-emerald-200/60 p-2.5">
                      <p className="text-[11px] text-emerald-700">Clima positivo</p>
                      <p className="text-lg font-bold text-emerald-800 tabular-nums">84%</p>
                    </div>
                    <div className="rounded-lg bg-rose-50/60 border border-rose-200/60 p-2.5">
                      <p className="text-[11px] text-rose-700">Em atenção</p>
                      <p className="text-lg font-bold text-rose-800 tabular-nums">2</p>
                    </div>
                  </div>

                  <div className="rounded-lg border border-slate-200/80 p-3.5 space-y-2">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-semibold text-slate-800">
                        Estudante → Matemática
                      </span>
                      <span className="tag tag-pos">
                        <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                        Positivo · 98%
                      </span>
                    </div>
                    <p className="text-xs sm:text-sm text-slate-600 leading-relaxed">
                      “As listas de revisão antes da prova ajudaram muito a turma a entender o
                      conteúdo novo.”
                    </p>
                  </div>

                  <div className="rounded-lg border border-amber-200/90 bg-amber-50/40 p-3.5 space-y-1.5">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-semibold text-amber-900 inline-flex items-center gap-1.5">
                        <ShieldAlert className="h-3.5 w-3.5 text-amber-700" />
                        Sinalização preventiva · Convivência
                      </span>
                      <span className="text-[11px] font-medium text-amber-700">Em acompanhamento</span>
                    </div>
                    <p className="text-xs text-slate-600">
                      Encaminhado automaticamente à orientação educacional da unidade.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* How it works */}
        <section id="como-funciona" className="max-w-6xl mx-auto px-4 sm:px-6 py-14 sm:py-20 space-y-10">
          <div className="max-w-2xl space-y-2">
            <p className="text-xs font-semibold uppercase tracking-wider text-brand-700">
              Fluxo simples
            </p>
            <h2 className="text-2xl sm:text-3xl font-bold text-slate-900">
              Como o Echora funciona na rotina escolar
            </h2>
            <p className="text-sm sm:text-base text-slate-600">
              Sem configurações complexas: cada pessoa vê apenas o que faz sentido para a sua função.
            </p>
          </div>

          <div className="grid gap-4 md:grid-cols-3">
            {STEPS.map((step) => {
              const Icon = step.icon
              return (
                <article
                  key={step.title}
                  className="card p-6 space-y-3 hover:-translate-y-0.5 hover:shadow-elevated transition-all duration-200"
                >
                  <span className="h-10 w-10 rounded-lg bg-brand-50 text-brand-700 grid place-items-center">
                    <Icon className="h-5 w-5" strokeWidth={1.75} />
                  </span>
                  <h3 className="text-base font-semibold text-slate-900">{step.title}</h3>
                  <p className="text-sm text-slate-600 leading-relaxed">{step.copy}</p>
                </article>
              )
            })}
          </div>
        </section>

        {/* Roles Interactive Tabs */}
        <section id="perfis" className="bg-white border-y border-slate-200/80">
          <div className="max-w-6xl mx-auto px-4 sm:px-6 py-14 sm:py-20 space-y-8">
            <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
              <div className="space-y-2">
                <p className="text-xs font-semibold uppercase tracking-wider text-brand-700">
                  Experiência dedicada
                </p>
                <h2 className="text-2xl sm:text-3xl font-bold text-slate-900">
                  Pensado para quem vive a escola todos os dias
                </h2>
              </div>

              <div className="inline-flex rounded-xl bg-slate-100 p-1 self-start">
                {(
                  [
                    { id: 'gestor', label: 'Gestão' },
                    { id: 'professor', label: 'Professores' },
                    { id: 'aluno', label: 'Alunos' },
                  ] as const
                ).map((tab) => (
                  <button
                    key={tab.id}
                    type="button"
                    onClick={() => setActiveRole(tab.id)}
                    className={`px-4 py-2 rounded-lg text-xs sm:text-sm font-semibold transition-colors ${
                      activeRole === tab.id
                        ? 'bg-white text-slate-900 shadow-xs'
                        : 'text-slate-600 hover:text-slate-900'
                    }`}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>
            </div>

            <div
              key={activeRole}
              className="animate-fadeUp rounded-2xl border border-slate-200/90 bg-[#F6F8FA] p-6 sm:p-8 lg:p-10 grid gap-8 lg:grid-cols-[1.1fr_0.9fr] items-center"
            >
              <div className="space-y-4">
                <span className="inline-block text-xs font-semibold px-2.5 py-1 rounded-md bg-brand-100/80 text-brand-900">
                  {currentRole.badge}
                </span>
                <h3 className="text-xl sm:text-2xl font-bold text-slate-900">
                  {currentRole.title}
                </h3>
                <p className="text-sm sm:text-base text-slate-600 leading-relaxed">
                  {currentRole.description}
                </p>
              </div>

              <ul className="space-y-3">
                {currentRole.bullets.map((bullet, idx) => (
                  <li
                    key={bullet}
                    style={{ animationDelay: `${idx * 50}ms` }}
                    className="animate-fadeUp flex items-start gap-3 rounded-xl bg-white border border-slate-200/80 p-4 text-sm text-slate-700 shadow-soft"
                  >
                    <CheckCircle2 className="h-4 w-4 text-brand-700 shrink-0 mt-0.5" />
                    <span>{bullet}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </section>

        {/* Security & Governance */}
        <section id="seguranca" className="max-w-6xl mx-auto px-4 sm:px-6 py-14 sm:py-20">
          <div className="rounded-2xl bg-brand-900 text-white p-6 sm:p-10 lg:p-12 grid gap-8 lg:grid-cols-[1fr_1.1fr] items-center">
            <div className="space-y-4">
              <p className="text-xs font-semibold uppercase tracking-wider text-teal-300">
                Privacidade por padrão
              </p>
              <h2 className="text-2xl sm:text-3xl font-bold text-white">
                Segurança institucional para lidar com relatos sensíveis
              </h2>
              <p className="text-sm sm:text-base text-teal-100/85 leading-relaxed">
                Sabemos que feedbacks escolares exigem sigilo e responsabilidade. Cada camada da
                plataforma foi construída para proteger alunos e educadores.
              </p>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              {[
                {
                  title: 'Criptografia AES-256-GCM',
                  text: 'Conteúdo cifrado no banco de dados com chaves simétricas autenticadas.',
                },
                {
                  title: 'Segregação por turma',
                  text: 'Estudantes só interagem com disciplinas e docentes vinculados à própria matrícula.',
                },
                {
                  title: 'Detecção de gatilhos',
                  text: 'Palavras críticas geram alerta discreto para ação rápida da coordenação.',
                },
                {
                  title: 'Trilha de resolução',
                  text: 'Registro de quando e como cada ocorrência prioritária foi acompanhada.',
                },
              ].map((item) => (
                <div
                  key={item.title}
                  className="rounded-xl bg-white/10 border border-white/10 p-4 space-y-1.5"
                >
                  <p className="text-sm font-semibold text-white">{item.title}</p>
                  <p className="text-xs text-teal-100/80 leading-relaxed">{item.text}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* FAQ Accordion */}
        <section id="faq" className="max-w-3xl mx-auto px-4 sm:px-6 pb-14 sm:pb-20 space-y-6">
          <div className="text-center space-y-2">
            <h2 className="text-2xl sm:text-3xl font-bold text-slate-900">Perguntas frequentes</h2>
            <p className="text-sm text-slate-500">
              Tire dúvidas comuns sobre implantação e rotina de uso nas escolas.
            </p>
          </div>

          <div className="space-y-2.5">
            {FAQ_ITEMS.map((item, idx) => {
              const isOpen = openFaqIndex === idx
              return (
                <div key={item.question} className="card overflow-hidden">
                  <button
                    type="button"
                    aria-expanded={isOpen}
                    onClick={() => setOpenFaqIndex(isOpen ? null : idx)}
                    className="w-full px-5 py-4 text-left flex items-center justify-between gap-4 hover:bg-slate-50/60 transition-colors"
                  >
                    <span className="text-sm sm:text-base font-semibold text-slate-900">
                      {item.question}
                    </span>
                    <ChevronDown
                      className={`h-4 w-4 text-slate-400 shrink-0 transition-transform duration-200 ${
                        isOpen ? 'rotate-180 text-brand-700' : ''
                      }`}
                    />
                  </button>
                  <div
                    className={`grid transition-all duration-200 ease-out ${
                      isOpen ? 'grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0'
                    }`}
                  >
                    <div className="overflow-hidden">
                      <div className="px-5 pb-4 text-sm text-slate-600 dark:text-slate-300 leading-relaxed border-t border-slate-100 dark:border-slate-800 pt-3">
                        {item.answer}
                      </div>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </section>

        {/* Contact Section */}
        <section id="contato" className="bg-white border-t border-slate-200/80">
          <div className="max-w-5xl mx-auto px-4 sm:px-6 py-14 sm:py-20 grid gap-10 lg:grid-cols-[0.95fr_1.05fr] items-start">
            <div className="space-y-4">
              <p className="text-xs font-semibold uppercase tracking-wider text-brand-700">
                Implantação
              </p>
              <h2 className="text-2xl sm:text-3xl font-bold text-slate-900">
                Leve o Echora para a sua instituição
              </h2>
              <p className="text-sm sm:text-base text-slate-600 leading-relaxed">
                Converse com a nossa equipe para configurar sua unidade escolar, importar turmas e
                liberar o acesso para coordenadores e docentes.
              </p>
              <p className="text-sm text-slate-500 pt-1">
                Contato direto:{' '}
                <a
                  href="mailto:contato@echora.dev"
                  className="font-semibold text-brand-700 hover:underline"
                >
                  contato@echora.dev
                </a>
              </p>
            </div>

            <form className="card p-5 sm:p-6 space-y-4 bg-[#F6F8FA]/50" onSubmit={handleContactSubmit}>
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label htmlFor="contact-name" className="label">
                    Nome
                  </label>
                  <input id="contact-name" name="name" className="input" required />
                </div>
                <div>
                  <label htmlFor="contact-school" className="label">
                    Escola ou Rede
                  </label>
                  <input id="contact-school" name="school" className="input" required />
                </div>
              </div>
              <div>
                <label htmlFor="contact-email" className="label">
                  E-mail institucional
                </label>
                <input id="contact-email" name="email" type="email" className="input" required />
              </div>
              <div>
                <label htmlFor="contact-message" className="label">
                  Como podemos ajudar?
                </label>
                <textarea
                  id="contact-message"
                  name="message"
                  className="input min-h-[96px]"
                  placeholder="Conte brevemente o número aproximado de turmas ou sua necessidade..."
                  required
                />
              </div>
              {contactStatus && (
                <p className="text-xs font-medium text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-lg px-3 py-2">
                  {contactStatus}
                </p>
              )}
              <button type="submit" className="btn w-full sm:w-auto px-6">
                <Send className="h-4 w-4" />
                Enviar mensagem
              </button>
            </form>
          </div>
        </section>
      </main>

      <Footer />
    </div>
  )
}
