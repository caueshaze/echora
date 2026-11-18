import { LogOut } from 'lucide-react'
import { EchoraLogo } from './brand/EchoraLogo'

interface HeaderProps {
  current?: 'aluno' | 'professor' | 'gestor' | 'admin'
  onLogout: () => void
}

export default function Header({ onLogout }: HeaderProps) {
  return (
    <header className="sticky top-0 z-20 bg-white/95 backdrop-blur border-b border-slate-200/80">
      <div className="max-w-6xl mx-auto px-4 h-14 flex items-center justify-between">
        <EchoraLogo size="sm" />
        <button
          type="button"
          className="btn-secondary py-1.5 px-3 min-h-[36px] text-xs"
          onClick={onLogout}
        >
          <LogOut className="h-3.5 w-3.5" strokeWidth={1.75} />
          Sair
        </button>
      </div>
    </header>
  )
}
