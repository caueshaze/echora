import { useEffect } from 'react'
import { EyeOff, Scale, ShieldAlert, X } from 'lucide-react'

interface FeedbackTermsModalProps {
  open: boolean
  onClose: () => void
}

export function FeedbackTermsModal({ open, onClose }: FeedbackTermsModalProps) {
  useEffect(() => {
    if (!open) return
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => {
      document.body.style.overflow = previousOverflow
      window.removeEventListener('keydown', handleKeyDown)
    }
  }, [open, onClose])

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="terms-modal-title"
    >
      <button
        type="button"
        className="fixed inset-0 bg-slate-900/45 dark:bg-slate-950/70 backdrop-blur-[1px] animate-fadeIn"
        onClick={onClose}
        aria-label="Fechar termos de uso"
      />

      <div className="relative z-10 w-full sm:max-w-lg bg-white dark:bg-slate-900 rounded-t-2xl sm:rounded-2xl shadow-elevated border border-slate-200 dark:border-slate-800 max-h-[88vh] flex flex-col overflow-hidden animate-slideUpModal">
        <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between gap-3">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-wider text-brand-700">
              Convivência Escolar
            </p>
            <h3 id="terms-modal-title" className="text-base sm:text-lg font-bold text-slate-900">
              Termos de Uso e Envio Responsável
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-2 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
            aria-label="Fechar"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="p-5 space-y-4 overflow-y-auto text-sm text-slate-600 leading-relaxed">
          <p>
            O <strong className="text-slate-800">Echora</strong> existe para fortalecer o diálogo
            pedagógico e melhorar o ambiente escolar com respeito, escuta e responsabilidade.
          </p>

          <div className="rounded-xl bg-slate-50 border border-slate-200/80 p-3.5 flex items-start gap-3">
            <EyeOff className="h-4 w-4 text-brand-700 shrink-0 mt-0.5" />
            <div className="space-y-1">
              <p className="text-xs font-semibold text-slate-900">Como funciona o envio anônimo</p>
              <p className="text-xs text-slate-600 leading-relaxed">
                Quando um estudante ativa o modo anônimo, seu nome e seu e-mail não são exibidos para
                professores, coordenadores ou demais membros da unidade escolar.
              </p>
            </div>
          </div>

          <div className="rounded-xl bg-rose-50/60 border border-rose-200/80 p-3.5 flex items-start gap-3">
            <ShieldAlert className="h-4 w-4 text-rose-700 shrink-0 mt-0.5" />
            <div className="space-y-1">
              <p className="text-xs font-semibold text-rose-900">
                Atuação em casos de assédio, ameaça ou conduta grave
              </p>
              <p className="text-xs text-rose-900/85 leading-relaxed">
                O envio anônimo não protege práticas ilícitas ou abusivas. Em situações de{' '}
                <strong>
                  assédio, intimidação (bullying), ameaças, violência, discurso de ódio, calúnia,
                  difamação ou risco à integridade física e emocional
                </strong>{' '}
                de qualquer pessoa, os registros técnicos restritos à administração geral poderão ser
                auditados para adoção imediata das medidas protetivas, disciplinares e legais
                cabíveis.
              </p>
            </div>
          </div>

          <div className="rounded-xl bg-slate-50 border border-slate-200/80 p-3.5 flex items-start gap-3">
            <Scale className="h-4 w-4 text-slate-600 shrink-0 mt-0.5" />
            <div className="space-y-1">
              <p className="text-xs font-semibold text-slate-900">Boas práticas ao relatar</p>
              <ul className="text-xs text-slate-600 list-disc pl-4 space-y-1">
                <li>Descreva fatos, aulas ou situações de forma objetiva e construtiva.</li>
                <li>Não exponha dados pessoais sensíveis de colegas ou terceiros.</li>
                <li>
                  Em emergências presenciais imediatas, procure diretamente a equipe da sua escola.
                </li>
              </ul>
            </div>
          </div>
        </div>

        <div className="px-5 py-3.5 border-t border-slate-100 bg-slate-50/60 flex justify-end pb-safe">
          <button type="button" onClick={onClose} className="btn w-full sm:w-auto px-6">
            Li e compreendi
          </button>
        </div>
      </div>
    </div>
  )
}
