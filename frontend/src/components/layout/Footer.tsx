import { Link } from 'react-router-dom'

import { EchoraLogo } from '../brand/EchoraLogo'

export function Footer() {
  return (
    <footer className="bg-white border-t border-slate-200/80 text-slate-600">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-10 flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
        <div className="space-y-2">
          <EchoraLogo size="sm" />
          <p className="text-sm text-slate-500 max-w-sm">
            Comunicação estruturada e acompanhamento de clima escolar para instituições de ensino.
          </p>
        </div>

        <div className="flex flex-wrap gap-x-6 gap-y-2 text-sm font-medium text-slate-600">
          <Link to="/privacy" className="hover:text-brand-700 transition-colors">
            Privacidade
          </Link>
          <Link to="/terms" className="hover:text-brand-700 transition-colors">
            Termos de Uso
          </Link>
          <a href="mailto:contato@echora.dev" className="hover:text-brand-700 transition-colors">
            contato@echora.dev
          </a>
        </div>
      </div>

      <div className="border-t border-slate-100">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-4 flex flex-col sm:flex-row items-center justify-between gap-2 text-xs text-slate-400">
          <span>© {new Date().getFullYear()} Echora. Todos os direitos reservados.</span>
          <span>Dados protegidos com criptografia AES-256-GCM.</span>
        </div>
      </div>
    </footer>
  )
}
