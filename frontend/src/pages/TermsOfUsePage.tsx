import { Navbar } from '../components/layout/Navbar'
import { Footer } from '../components/layout/Footer'

const obligations = [
  {
    title: 'Responsabilidades da instituição',
    items: [
      'Gerenciar o cadastro oficial de coordenadores, professores, turmas e estudantes.',
      'Orientar a comunidade escolar sobre o uso construtivo e pedagógico da plataforma.',
      'Acompanhar prontamente os alertas preventivos sinalizados no painel de gestão.',
    ],
  },
  {
    title: 'Responsabilidades dos usuários',
    items: [
      'Manter suas credenciais de acesso em sigilo e uso estritamente pessoal.',
      'Utilizar linguagem ética, sem exposição indevida de dados sensíveis de terceiros.',
      'Comunicar imediatamente a coordenação em situações emergenciais presenciais.',
    ],
  },
]

const acceptableUse = [
  'É vedado o envio de ameaças, assédio, intimidação (bullying), discriminação, calúnia ou qualquer conteúdo ilícito.',
  'Relatos enviados no modo anônimo ocultam o nome do estudante para professores e coordenação, mas registros técnicos restritos à administração geral poderão ser auditados e acionados em casos graves de assédio, ameaça ou risco à integridade de pessoas.',
  'Não é permitido tentar acessar contas de terceiros ou contornar mecanismos de segurança da API.',
  'O Echora é uma ferramenta de acompanhamento pedagógico e não substitui canais emergenciais imediatos.',
]

export default function TermsOfUsePage() {
  return (
    <div className="min-h-screen bg-[#F6F8FA] text-slate-900 flex flex-col">
      <Navbar />
      <main className="flex-1 max-w-4xl mx-auto w-full px-4 sm:px-6 py-12 sm:py-16 space-y-8">
        <header className="space-y-2 border-b border-slate-200 pb-6">
          <p className="text-xs font-semibold uppercase tracking-wider text-brand-700">
            Documentação Institucional
          </p>
          <h1 className="text-3xl sm:text-4xl font-bold text-slate-900">Termos de Uso</h1>
          <p className="text-sm sm:text-base text-slate-600 max-w-2xl leading-relaxed">
            Diretrizes para utilização do Echora por gestores escolares, docentes e estudantes.
          </p>
        </header>

        <section className="grid gap-4 md:grid-cols-2">
          {obligations.map((block) => (
            <article key={block.title} className="card p-6 space-y-3">
              <h2 className="text-lg font-semibold text-slate-900">{block.title}</h2>
              <ul className="text-sm text-slate-600 space-y-2 list-disc pl-4 leading-relaxed">
                {block.items.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </article>
          ))}
        </section>

        <section className="card p-6 space-y-3">
          <h2 className="text-lg font-semibold text-slate-900">Conduta e uso adequado</h2>
          <ul className="text-sm text-slate-600 space-y-2 list-disc pl-4 leading-relaxed">
            {acceptableUse.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>

        <section className="card p-6 space-y-2">
          <h2 className="text-lg font-semibold text-slate-900">Suporte Institucional</h2>
          <p className="text-sm text-slate-600 leading-relaxed">
            Dúvidas operacionais ou técnicas podem ser encaminhadas para{' '}
            <a
              href="mailto:suporte@echora.dev"
              className="font-semibold text-brand-700 hover:underline"
            >
              suporte@echora.dev
            </a>
            .
          </p>
        </section>
      </main>
      <Footer />
    </div>
  )
}
