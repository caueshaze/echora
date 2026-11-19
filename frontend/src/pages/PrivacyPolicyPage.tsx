import { Navbar } from '../components/layout/Navbar'
import { Footer } from '../components/layout/Footer'

const dataInventory = [
  {
    title: 'Identidade e vínculo escolar',
    items: [
      'Nome completo, e-mail institucional e perfil atribuído pela escola.',
      'Vínculos internos de unidade, turma e disciplina para controle de acesso.',
      'Registros técnicos essenciais de sessão e autenticação segura.',
    ],
  },
  {
    title: 'Relatos pedagógicos',
    items: [
      'Mensagens enviadas e recebidas armazenadas sob criptografia AES-256-GCM.',
      'Indicadores automáticos de sentimento e sinalização preventiva de risco.',
      'Registro de encaminhamento e conclusão de alertas pela coordenação.',
      'Em relatos anônimos, a identidade não aparece nas consultas comuns. Em situações excepcionais de ameaça concreta à segurança, a identidade poderá ser consultada após justificativa, aprovação de outro administrador autorizado e registro de auditoria.',
      'O anonimato nas telas não impede que o próprio conteúdo ou as circunstâncias de um relato permitam identificar alguém.',
      'Quando a síntese por IA é solicitada, trechos dos relatos são enviados ao provedor de IA configurado, que pode processá-los fora do Brasil.',
    ],
  },
  {
    title: 'Operação e confiabilidade',
    items: [
      'Métricas técnicas agregadas de disponibilidade e tempo de resposta.',
      'Proteção de limite de requisições contra acessos automatizados indevidos.',
    ],
  },
]

const securityPractices = [
  'Criptografia simétrica autenticada em repouso (AES-256-GCM) e TLS em trânsito.',
  'Senhas protegidas com hashing Bcrypt e sessões JWT com tempo de expiração.',
  'Isolamento estrito de dados por unidade escolar, turma e papel institucional.',
  'Não comercialização de dados pessoais ou estudantis sob nenhuma hipótese.',
]

const rights = [
  'Confirmação de tratamento e consulta aos dados vinculados à conta.',
  'Correção de informações cadastrais junto à secretaria/coordenação da unidade.',
  'Exclusão ou anonimização conforme diretrizes contratuais da instituição de ensino e legislação aplicável (LGPD).',
]

export default function PrivacyPolicyPage() {
  return (
    <div className="min-h-screen bg-[#F6F8FA] text-slate-900 flex flex-col">
      <Navbar />
      <main className="flex-1 max-w-4xl mx-auto w-full px-4 sm:px-6 py-12 sm:py-16 space-y-8">
        <header className="space-y-2 border-b border-slate-200 pb-6">
          <p className="text-xs font-semibold uppercase tracking-wider text-brand-700">
            Documentação Institucional
          </p>
          <h1 className="text-3xl sm:text-4xl font-bold text-slate-900">Política de Privacidade</h1>
          <p className="text-sm sm:text-base text-slate-600 max-w-2xl leading-relaxed">
            Como o Echora coleta, protege e trata informações no contexto das instituições de ensino
            parceiras.
          </p>
        </header>

        <section className="grid gap-4 md:grid-cols-3">
          {dataInventory.map((section) => (
            <article key={section.title} className="card p-5 space-y-3">
              <h2 className="text-base font-semibold text-slate-900">{section.title}</h2>
              <ul className="text-sm text-slate-600 space-y-2 list-disc pl-4 leading-relaxed">
                {section.items.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </article>
          ))}
        </section>

        <section className="grid gap-4 md:grid-cols-2">
          <article className="card p-6 space-y-3">
            <h2 className="text-lg font-semibold text-slate-900">Práticas de segurança</h2>
            <ul className="text-sm text-slate-600 space-y-2 list-disc pl-4 leading-relaxed">
              {securityPractices.map((practice) => (
                <li key={practice}>{practice}</li>
              ))}
            </ul>
          </article>

          <article className="card p-6 space-y-3">
            <h2 className="text-lg font-semibold text-slate-900">Direitos dos titulares (LGPD)</h2>
            <ul className="text-sm text-slate-600 space-y-2 list-disc pl-4 leading-relaxed">
              {rights.map((right) => (
                <li key={right}>{right}</li>
              ))}
            </ul>
          </article>
        </section>

        <section className="card p-6 space-y-2">
          <h2 className="text-lg font-semibold text-slate-900">Canal de Privacidade</h2>
          <p className="text-sm text-slate-600 leading-relaxed">
            Solicitações relacionadas à proteção de dados devem ser encaminhadas pela instituição ou
            titular para{' '}
            <a
              className="font-semibold text-brand-700 hover:underline"
              href="mailto:privacidade@echora.dev"
            >
              privacidade@echora.dev
            </a>
            .
          </p>
        </section>
      </main>
      <Footer />
    </div>
  )
}
