import { MouseEvent, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { ArrowRight, Menu, X } from 'lucide-react'

import { EchoraLogo } from '../brand/EchoraLogo'

const navItems = [
  { label: 'Como funciona', target: 'como-funciona' },
  { label: 'Para cada perfil', target: 'perfis' },
  { label: 'Segurança', target: 'seguranca' },
  { label: 'Dúvidas', target: 'faq' },
  { label: 'Contato', target: 'contato' },
]

export function Navbar() {
  const [open, setOpen] = useState(false)
  const location = useLocation()
  const navigate = useNavigate()
  const isLanding = location.pathname === '/'

  const scrollToSection = (target: string) => {
    const element = document.getElementById(target)
    if (element) {
      element.scrollIntoView({ behavior: 'smooth' })
      return
    }
    if (target === 'inicio') {
      window.scrollTo({ top: 0, behavior: 'smooth' })
    }
  }

  const handleNavClick = (event: MouseEvent<HTMLAnchorElement>, target: string) => {
    event.preventDefault()
    setOpen(false)
    if (isLanding) {
      scrollToSection(target)
    } else {
      navigate({ pathname: '/', hash: `#${target}` })
    }
  }

  return (
    <header className="sticky top-0 z-40 bg-white/95 backdrop-blur border-b border-slate-200/80" id="top">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
        <Link to="/" className="flex items-center" onClick={() => setOpen(false)}>
          <EchoraLogo size="md" />
        </Link>

        <nav className="hidden md:flex items-center gap-7 text-sm font-medium text-slate-600">
          {navItems.map((item) => (
            <a
              key={item.target}
              href={`#${item.target}`}
              className="hover:text-slate-900 transition-colors"
              onClick={(event) => handleNavClick(event, item.target)}
            >
              {item.label}
            </a>
          ))}
        </nav>

        <div className="hidden md:flex items-center gap-3">
          <Link to="/login" className="btn py-2 min-h-[38px] px-4">
            Entrar
            <ArrowRight className="h-4 w-4" strokeWidth={1.75} />
          </Link>
        </div>

        <button
          type="button"
          className="md:hidden p-2 -mr-2 rounded-lg text-slate-600 hover:bg-slate-100"
          onClick={() => setOpen((prev) => !prev)}
          aria-label={open ? 'Fechar menu' : 'Abrir menu'}
        >
          {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </div>

      {open && (
        <div className="md:hidden border-t border-slate-100 bg-white px-4 pb-5 pt-2 shadow-elevated">
          <nav className="flex flex-col divide-y divide-slate-100 text-sm font-medium text-slate-700">
            {navItems.map((item) => (
              <a
                key={item.target}
                href={`#${item.target}`}
                className="py-3 hover:text-brand-700"
                onClick={(event) => handleNavClick(event, item.target)}
              >
                {item.label}
              </a>
            ))}
          </nav>
          <div className="pt-4">
            <Link
              to="/login"
              className="btn w-full"
              onClick={() => setOpen(false)}
            >
              Acessar minha conta
              <ArrowRight className="h-4 w-4" strokeWidth={1.75} />
            </Link>
          </div>
        </div>
      )}
    </header>
  )
}
