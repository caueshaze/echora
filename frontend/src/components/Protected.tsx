// src/components/Protected.tsx
import { ReactNode, useEffect, useMemo } from 'react'
import { Navigate, useLocation } from 'react-router-dom'

import { useAuth, Role } from '../context/AuthContext'
import { hasToken } from '../lib/auth'
import { EchoraLogo } from './brand/EchoraLogo'

type BackendRole = 'admin' | 'gestor' | 'professor' | 'aluno'
type AllowedRole = Role | BackendRole

const backendToFront: Record<BackendRole, Role> = {
  admin: 'admin',
  gestor: 'gestor',
  professor: 'professor',
  aluno: 'aluno',
}

type ProtectedProps = {
  children: ReactNode
  roles?: AllowedRole[]
  allow?: Role[] // compatibilidade com uso anterior
}

export function Protected({ children, roles, allow }: ProtectedProps) {
  const { session, loading, refresh } = useAuth()
  const location = useLocation()
  const tokenAvailable = hasToken()

  const normalizedRoles = useMemo(() => {
    const source = roles ?? allow ?? []
    return source
      .map((role) => {
        if (!role) return null
        if (role in backendToFront) {
          return backendToFront[role as BackendRole]
        }
        return role as Role
      })
      .filter((item): item is Role => Boolean(item))
  }, [roles, allow])

  useEffect(() => {
    if (tokenAvailable && !session && !loading) {
      void refresh()
    }
  }, [tokenAvailable, session, loading, refresh])

  if (!tokenAvailable) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  if (loading && !session) {
    return (
      <div className="min-h-screen bg-[#F6F8FA] dark:bg-[#0B1120] grid place-items-center px-4">
        <div className="flex flex-col items-center gap-4 animate-fadeUp">
          <div className="animate-pulse">
            <EchoraLogo size="lg" />
          </div>
          <div className="flex items-center gap-2 text-xs font-medium text-slate-500 dark:text-slate-400">
            <span className="h-1.5 w-1.5 rounded-full bg-brand-600 animate-ping" />
            <span>Validando sessão...</span>
          </div>
        </div>
      </div>
    )
  }

  if (!session) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  if (normalizedRoles.length > 0 && !normalizedRoles.includes(session.role)) {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}
