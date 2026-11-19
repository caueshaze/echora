import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { ArrowLeft, Eye, EyeOff, Lock, Users } from 'lucide-react'

import { EchoraLogo } from '../components/brand/EchoraLogo'
import { useAuth, Role } from '../context/AuthContext'
import { API_BASE_URL } from '../lib/config'
import { clearToken, getToken } from '../lib/auth'

const redirectMap: Record<Role, string> = {
  aluno: '/aluno',
  professor: '/professor',
  gestor: '/gestor',
  admin: '/admin',
}

export default function Login() {
  const { login, refresh } = useAuth()
  const navigate = useNavigate()
  const [formData, setFormData] = useState({ username: '', password: '' })
  const [showPassword, setShowPassword] = useState(false)
  const [statusMessage, setStatusMessage] = useState<{
    type: 'error' | 'info'
    text: string
  } | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [mustChangePassword, setMustChangePassword] = useState(false)
  const [newPassword, setNewPassword] = useState('')

  const handleInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = event.target
    setFormData((prev) => ({ ...prev, [name]: value }))
    if (statusMessage?.type === 'error') {
      setStatusMessage(null)
    }
  }

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    const normalizedEmail = formData.username.trim().toLowerCase()
    const normalizedPassword = formData.password
    if (!normalizedEmail || !normalizedPassword) {
      setStatusMessage({ type: 'error', text: 'Informe seu e-mail e sua senha.' })
      return
    }
    setIsLoading(true)
    setStatusMessage({ type: 'info', text: 'Entrando...' })
    try {
      const result = await login(normalizedEmail, normalizedPassword)
      if (result.mustChangePassword) {
        setMustChangePassword(true)
        setStatusMessage({ type: 'info', text: 'Defina uma nova senha para continuar.' })
      } else {
        navigate(redirectMap[result.role] ?? '/')
      }
    } catch (error: any) {
      setStatusMessage({
        type: 'error',
        text: error?.message || 'E-mail ou senha incorretos. Confira os dados e tente novamente.',
      })
    } finally {
      setIsLoading(false)
    }
  }

  const handleChangePassword = async (event: React.FormEvent) => {
    event.preventDefault()
    setIsLoading(true)
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/auth/change-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${getToken()}` },
        body: JSON.stringify({ current_password: formData.password, new_password: newPassword }),
      })
      if (!response.ok) throw new Error('Não foi possível alterar a senha. Confira os requisitos e tente novamente.')
      clearToken()
      await refresh()
      setMustChangePassword(false)
      setNewPassword('')
      setFormData((current) => ({ ...current, password: '' }))
      setStatusMessage({ type: 'info', text: 'Senha alterada. Entre novamente com a nova senha.' })
    } catch (error: any) {
      setStatusMessage({ type: 'error', text: error?.message || 'Não foi possível alterar a senha.' })
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="relative min-h-screen overflow-hidden bg-[#F8FAFC] lg:bg-transparent flex flex-col lg:grid lg:grid-cols-12">
      {/* Desktop Soft Blended Background between Light and Deep Teal */}
      <div className="hidden lg:block absolute inset-0 pointer-events-none" aria-hidden="true">
        <div
          className="absolute -inset-36 blur-[72px]"
          style={{
            background:
              'linear-gradient(96deg, #FFFFFF 0%, #FFFFFF 45%, #0F544F 53%, #0B3E3B 75%, #082F2C 100%)',
          }}
        />
      </div>

      {/* Left Column: Clean Login Area */}
      <div className="relative z-10 lg:col-span-6 flex flex-col justify-between min-h-screen px-5 py-8 sm:px-10">
        {/* Top Brand Header */}
        <header className="flex items-center justify-between max-w-sm w-full mx-auto">
          <Link to="/" className="inline-flex items-center group" title="Ir para o início">
            <EchoraLogo size="md" />
          </Link>
        </header>

        {/* Centered Login Card / Form */}
        <main className="w-full max-w-sm mx-auto my-auto py-8 space-y-6">
          <div className="space-y-1.5">
            <h1 className="text-2xl sm:text-[28px] font-bold text-slate-900 tracking-tight">
              Acesse sua conta
            </h1>
            <p className="text-sm text-slate-500">
              Entre com o e-mail cadastrado pela sua escola.
            </p>
          </div>

          <form className="space-y-4" onSubmit={mustChangePassword ? handleChangePassword : handleSubmit}>
            <div>
              <label htmlFor="username" className="label">
                E-mail
              </label>
              <input
                id="username"
                name="username"
                type="email"
                autoComplete="email"
                className="input bg-white shadow-2xs"
                placeholder="voce@escola.edu.br"
                value={formData.username}
                onChange={handleInputChange}
                required
                disabled={isLoading || mustChangePassword}
              />
            </div>

            <div>
              <label htmlFor="password" className="label">
                Senha
              </label>
              <div className="relative">
                <input
                  id="password"
                  name="password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  className="input bg-white pr-10 shadow-2xs"
                  placeholder="Sua senha"
                  value={formData.password}
                  onChange={handleInputChange}
                  required
                  disabled={isLoading || mustChangePassword}
                />
                <button
                  type="button"
                  tabIndex={-1}
                  onClick={() => setShowPassword((prev) => !prev)}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 p-1.5 text-slate-400 hover:text-slate-600 rounded"
                  aria-label={showPassword ? 'Ocultar senha' : 'Mostrar senha'}
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            {mustChangePassword && (
              <div>
                <label htmlFor="new-password" className="label">Nova senha</label>
                <input id="new-password" type="password" autoComplete="new-password" className="input"
                  minLength={12} maxLength={72} required value={newPassword}
                  onChange={(event) => setNewPassword(event.target.value)} disabled={isLoading} />
              </div>
            )}

            {statusMessage && (
              <div
                className={`rounded-lg px-3.5 py-2.5 text-xs font-medium border ${
                  statusMessage.type === 'error'
                    ? 'bg-rose-50 border-rose-200 text-rose-700'
                    : 'bg-slate-50 border-slate-200 text-slate-600'
                }`}
              >
                {statusMessage.text}
              </div>
            )}

            <button type="submit" className="btn w-full py-3 shadow-xs" disabled={isLoading}>
              {isLoading ? 'Aguarde...' : mustChangePassword ? 'Alterar senha' : 'Entrar'}
            </button>
          </form>

          <p className="text-xs text-slate-500 leading-relaxed">
            Primeiro acesso ou esqueceu a senha? Procure a coordenação da sua escola ou escreva para{' '}
            <a
              href="mailto:suporte@echora.dev"
              className="font-medium text-brand-700 hover:underline"
            >
              suporte@echora.dev
            </a>
            .
          </p>
        </main>

        {/* Subtle Aligned Footer */}
        <footer className="flex items-center justify-between max-w-sm w-full mx-auto text-xs text-slate-400">
          <Link
            to="/"
            className="inline-flex items-center gap-1.5 text-slate-500 hover:text-slate-800 font-medium transition-colors"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Voltar ao site
          </Link>
          <div className="flex items-center gap-4">
            <Link to="/privacy" className="hover:text-slate-600 transition-colors">
              Privacidade
            </Link>
            <Link to="/terms" className="hover:text-slate-600 transition-colors">
              Termos
            </Link>
          </div>
        </footer>
      </div>

      {/* Right Column: Calm Institutional Context (Desktop only, no duplicate logo) */}
      <aside className="hidden lg:flex lg:col-span-6 relative z-10 items-center justify-center pl-24 pr-12 xl:pl-28 xl:pr-16">
        <div className="max-w-md space-y-6 text-white">
          <div className="space-y-3">
            <span className="inline-flex items-center gap-2 rounded-full bg-white/10 border border-white/15 px-3 py-1 text-xs font-medium text-teal-100">
              Ambiente Escolar Seguro
            </span>
            <h2 className="text-3xl xl:text-[34px] font-display font-bold text-white leading-tight">
              Escuta próxima para fortalecer o dia a dia na escola.
            </h2>
            <p className="text-teal-50/85 text-[15px] leading-relaxed">
              Alunos, professores e coordenação conectados no mesmo espaço, com diálogo organizado
              por turma e privacidade em cada relato.
            </p>
          </div>

          <div className="space-y-3 pt-2">
            <div className="flex items-start gap-3.5 rounded-xl bg-white/10 backdrop-blur-xs border border-white/15 p-4">
              <Users className="h-5 w-5 text-teal-200 shrink-0 mt-0.5" strokeWidth={1.75} />
              <div>
                <p className="text-sm font-semibold text-white">Cada perfil no seu espaço</p>
                <p className="text-xs text-teal-100/80 mt-0.5 leading-relaxed">
                  Você visualiza apenas as turmas, disciplinas e mensagens da sua rotina.
                </p>
              </div>
            </div>

            <div className="flex items-start gap-3.5 rounded-xl bg-white/10 backdrop-blur-xs border border-white/15 p-4">
              <Lock className="h-5 w-5 text-teal-200 shrink-0 mt-0.5" strokeWidth={1.75} />
              <div>
                <p className="text-sm font-semibold text-white">Sigilo e proteção de dados</p>
                <p className="text-xs text-teal-100/80 mt-0.5 leading-relaxed">
                  Mensagens protegidas por criptografia em trânsito e em repouso.
                </p>
              </div>
            </div>
          </div>
        </div>
      </aside>
    </div>
  )
}
