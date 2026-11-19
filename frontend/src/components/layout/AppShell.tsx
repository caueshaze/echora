import { type ReactNode, useEffect, useState } from 'react'
import { LogOut, Menu, RefreshCw, X } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

import { EchoraLogo } from '../brand/EchoraLogo'
import { ThemeToggle } from './ThemeToggle'

export type NavItem<T extends string> = {
  id: T
  label: string
  shortLabel?: string
  icon: LucideIcon
  group?: string
  badge?: number
}

interface AppShellProps<T extends string> {
  userName: string
  userEmail?: string | null
  roleLabel: string
  pageTitle: string
  pageSubtitle?: string
  items: Array<NavItem<T>>
  bottomNavIds?: T[]
  activeId: T
  onSelect: (id: T) => void
  onLogout: () => void
  onRefresh?: () => void
  refreshLoading?: boolean
  refreshLabel?: string
  headerExtra?: ReactNode
  children: ReactNode
}

export function AppShell<T extends string>({
  userName,
  userEmail,
  roleLabel,
  pageTitle,
  pageSubtitle,
  items,
  bottomNavIds,
  activeId,
  onSelect,
  onLogout,
  onRefresh,
  refreshLoading = false,
  refreshLabel = 'Atualizar',
  headerExtra,
  children,
}: AppShellProps<T>) {
  const [drawerOpen, setDrawerOpen] = useState(false)

  useEffect(() => {
    setDrawerOpen(false)
  }, [activeId])

  useEffect(() => {
    if (!drawerOpen) return
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setDrawerOpen(false)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => {
      document.body.style.overflow = previousOverflow
      window.removeEventListener('keydown', handleKeyDown)
    }
  }, [drawerOpen])

  const groupedItems = groupNavItems(items)
  const bottomItems = bottomNavIds
    ? bottomNavIds
        .map((id) => items.find((item) => item.id === id))
        .filter((item): item is NavItem<T> => Boolean(item))
    : []
  const hasBottomNav = bottomItems.length > 0
  const showMobileMenuTrigger = !hasBottomNav || items.length > bottomItems.length

  const initials = getInitials(userName || roleLabel)

  return (
    <div className="min-h-screen bg-[#F6F8FA] text-slate-900 flex flex-col lg:flex-row">
      {/* Desktop Sidebar */}
      <aside className="hidden lg:flex lg:w-64 lg:flex-col lg:fixed lg:inset-y-0 bg-white dark:bg-slate-900 border-r border-slate-200/80 dark:border-slate-800 z-30">
        <div className="h-16 px-5 flex items-center justify-between gap-2 border-b border-slate-100 dark:border-slate-800">
          <EchoraLogo size="md" />
          <div className="flex items-center gap-1.5">
            <span className="text-[11px] font-medium px-2 py-0.5 rounded-md bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300">
              {roleLabel}
            </span>
            <ThemeToggle compact className="border-transparent bg-transparent dark:bg-transparent" />
          </div>
        </div>

        <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-5">
          {groupedItems.map(({ group, entries }) => (
            <div key={group || '__root__'}>
              {group && (
                <p className="px-3 mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                  {group}
                </p>
              )}
              <ul className="space-y-0.5">
                {entries.map((item) => {
                  const Icon = item.icon
                  const isActive = item.id === activeId
                  return (
                    <li key={item.id}>
                      <button
                        type="button"
                        onClick={() => onSelect(item.id)}
                        className={`relative group w-full flex items-center justify-between gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                          isActive
                            ? 'bg-brand-50 dark:bg-brand-950/60 text-brand-800 dark:text-brand-300 font-semibold'
                            : 'text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800/70 hover:text-slate-900 dark:hover:text-slate-100 font-medium'
                        }`}
                      >
                        {isActive && (
                          <span
                            aria-hidden="true"
                            className="absolute left-0 top-1/2 -translate-y-1/2 h-5 w-1 rounded-r-full bg-brand-600 dark:bg-brand-400"
                          />
                        )}
                        <span className="flex items-center gap-2.5 truncate">
                          <Icon
                            className={`h-4 w-4 shrink-0 transition-transform duration-150 group-hover:scale-105 ${
                              isActive ? 'text-brand-700 dark:text-brand-400' : 'text-slate-400'
                            }`}
                            strokeWidth={isActive ? 2 : 1.75}
                          />
                          <span className="truncate">{item.label}</span>
                        </span>
                        {typeof item.badge === 'number' && item.badge > 0 && (
                          <span
                            className={`text-xs px-1.5 py-0.5 rounded-full font-medium tabular-nums ${
                              isActive
                                ? 'bg-brand-700 dark:bg-brand-600 text-white'
                                : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300'
                            }`}
                          >
                            {item.badge}
                          </span>
                        )}
                      </button>
                    </li>
                  )
                })}
              </ul>
            </div>
          ))}
        </nav>

        <div className="p-3 border-t border-slate-100">
          <div className="flex items-center gap-3 px-2 py-2 rounded-lg">
            <div className="h-9 w-9 rounded-full bg-brand-100 text-brand-800 font-semibold text-xs grid place-items-center shrink-0">
              {initials}
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-slate-900 truncate">{userName}</p>
              <p className="text-xs text-slate-500 truncate">{userEmail || roleLabel}</p>
            </div>
            <button
              type="button"
              onClick={onLogout}
              title="Sair da conta"
              aria-label="Sair da conta"
              className="p-2 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors"
            >
              <LogOut className="h-4 w-4" strokeWidth={1.75} />
            </button>
          </div>
        </div>
      </aside>

      {/* Mobile Topbar */}
      <header className="lg:hidden sticky top-0 z-30 h-14 bg-white/95 backdrop-blur border-b border-slate-200/80 px-4 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2.5 min-w-0">
          {showMobileMenuTrigger && (
            <button
              type="button"
              onClick={() => setDrawerOpen(true)}
              className="p-2 -ml-2 rounded-lg text-slate-600 hover:bg-slate-100 active:bg-slate-200"
              aria-label="Abrir menu de navegação"
            >
              <Menu className="h-5 w-5" strokeWidth={1.75} />
            </button>
          )}
          <EchoraLogo size="sm" iconOnly={showMobileMenuTrigger} />
          {showMobileMenuTrigger && (
            <span className="text-sm font-semibold text-slate-900 truncate">{pageTitle}</span>
          )}
        </div>

        <div className="flex items-center gap-1.5 shrink-0">
          <ThemeToggle compact className="border-transparent bg-transparent dark:bg-transparent" />
          {onRefresh && (
            <button
              type="button"
              onClick={onRefresh}
              disabled={refreshLoading}
              aria-label={refreshLabel}
              className="p-2 rounded-lg text-slate-600 hover:bg-slate-100 disabled:opacity-50"
            >
              <RefreshCw
                className={`h-4 w-4 ${refreshLoading ? 'animate-spin text-brand-700' : ''}`}
                strokeWidth={1.75}
              />
            </button>
          )}
          <button
            type="button"
            onClick={onLogout}
            aria-label="Sair"
            className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium text-slate-600 hover:text-rose-600 hover:bg-rose-50"
          >
            <LogOut className="h-4 w-4" strokeWidth={1.75} />
            <span className="hidden sm:inline">Sair</span>
          </button>
        </div>
      </header>

      {/* Mobile Navigation Drawer */}
      {drawerOpen && (
        <div className="lg:hidden fixed inset-0 z-50 flex">
          <button
            type="button"
            className="fixed inset-0 bg-slate-900/40 dark:bg-slate-950/70 backdrop-blur-[1px] animate-fadeIn"
            aria-label="Fechar menu"
            onClick={() => setDrawerOpen(false)}
          />
          <div className="relative w-72 max-w-[85vw] bg-white dark:bg-slate-900 h-full shadow-elevated flex flex-col z-10 animate-slideInLeft">
            <div className="h-14 px-4 flex items-center justify-between border-b border-slate-100">
              <EchoraLogo size="sm" subtitle={roleLabel} />
              <button
                type="button"
                onClick={() => setDrawerOpen(false)}
                className="p-2 rounded-lg text-slate-500 hover:bg-slate-100"
                aria-label="Fechar"
              >
                <X className="h-5 w-5" strokeWidth={1.75} />
              </button>
            </div>

            <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-5">
              {groupedItems.map(({ group, entries }) => (
                <div key={group || '__mobile_root__'}>
                  {group && (
                    <p className="px-3 mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                      {group}
                    </p>
                  )}
                  <ul className="space-y-0.5">
                    {entries.map((item) => {
                      const Icon = item.icon
                      const isActive = item.id === activeId
                      return (
                        <li key={item.id}>
                          <button
                            type="button"
                            onClick={() => onSelect(item.id)}
                            className={`w-full flex items-center justify-between gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                              isActive
                                ? 'bg-brand-50 text-brand-800 font-semibold'
                                : 'text-slate-700 hover:bg-slate-50 font-medium'
                            }`}
                          >
                            <span className="flex items-center gap-3 truncate">
                              <Icon
                                className={`h-4 w-4 shrink-0 ${
                                  isActive ? 'text-brand-700' : 'text-slate-400'
                                }`}
                                strokeWidth={isActive ? 2 : 1.75}
                              />
                              <span className="truncate">{item.label}</span>
                            </span>
                            {typeof item.badge === 'number' && item.badge > 0 && (
                              <span className="text-xs px-2 py-0.5 rounded-full bg-brand-100 text-brand-800 font-medium tabular-nums">
                                {item.badge}
                              </span>
                            )}
                          </button>
                        </li>
                      )
                    })}
                  </ul>
                </div>
              ))}
            </nav>

            <div className="p-4 border-t border-slate-100 bg-slate-50/60">
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-slate-900 truncate">{userName}</p>
                  <p className="text-xs text-slate-500 truncate">{userEmail || roleLabel}</p>
                </div>
                <button
                  type="button"
                  onClick={onLogout}
                  className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium text-rose-700 bg-rose-50 hover:bg-rose-100"
                >
                  <LogOut className="h-3.5 w-3.5" strokeWidth={1.75} />
                  Sair
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Main Content Area */}
      <div className="flex-1 lg:pl-64 flex flex-col min-w-0">
        <main
          className={`flex-1 w-full max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-5 lg:py-8 space-y-6 ${
            hasBottomNav ? 'pb-[calc(6rem+env(safe-area-inset-bottom,0px))] lg:pb-10' : 'pb-10'
          }`}
        >
          {/* Page Header */}
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h1 className="text-xl sm:text-2xl font-bold text-slate-900">{pageTitle}</h1>
              {pageSubtitle && (
                <p className="text-sm text-slate-500 mt-0.5">{pageSubtitle}</p>
              )}
            </div>
            <div className="flex items-center gap-2">
              {headerExtra}
              {onRefresh && (
                <button
                  type="button"
                  onClick={onRefresh}
                  disabled={refreshLoading}
                  className="hidden lg:inline-flex btn-secondary text-xs py-2 min-h-[36px]"
                >
                  <RefreshCw
                    className={`h-3.5 w-3.5 ${refreshLoading ? 'animate-spin text-brand-700' : ''}`}
                    strokeWidth={1.75}
                  />
                  {refreshLoading ? 'Sincronizando...' : refreshLabel}
                </button>
              )}
            </div>
          </div>

          <div key={activeId} className="animate-fadeUp space-y-6">
            {children}
          </div>
        </main>
      </div>

      {/* Mobile Bottom Navigation Bar */}
      {hasBottomNav && (
        <nav
          aria-label="Navegação rápida"
          className="lg:hidden fixed bottom-0 inset-x-0 z-30 bg-white/95 dark:bg-slate-900/95 backdrop-blur border-t border-slate-200/80 dark:border-slate-800 pb-safe"
        >
          <ul
            className="grid h-16 px-1"
            style={{ gridTemplateColumns: `repeat(${bottomItems.length}, minmax(0, 1fr))` }}
          >
            {bottomItems.map((item) => {
              const Icon = item.icon
              const isActive = item.id === activeId
              return (
                <li key={item.id} className="flex">
                  <button
                    type="button"
                    onClick={() => onSelect(item.id)}
                    className={`relative flex-1 flex flex-col items-center justify-center gap-1 text-[11px] transition-colors ${
                      isActive
                        ? 'text-brand-700 dark:text-brand-400 font-semibold'
                        : 'text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200 font-medium'
                    }`}
                  >
                    {isActive && (
                      <span
                        aria-hidden="true"
                        className="absolute top-0 left-1/2 -translate-x-1/2 h-0.5 w-6 rounded-full bg-brand-600 dark:bg-brand-400"
                      />
                    )}
                    <span className="relative">
                      <Icon
                        className={`h-5 w-5 transition-transform duration-150 ${
                          isActive ? 'scale-105' : ''
                        }`}
                        strokeWidth={isActive ? 2.1 : 1.75}
                      />
                      {typeof item.badge === 'number' && item.badge > 0 && (
                        <span className="absolute -top-1 -right-2 h-4 min-w-[16px] px-1 rounded-full bg-brand-700 dark:bg-brand-600 text-white text-[10px] font-semibold grid place-items-center">
                          {item.badge > 9 ? '9+' : item.badge}
                        </span>
                      )}
                    </span>
                    <span className="truncate max-w-[68px]">
                      {item.shortLabel || item.label}
                    </span>
                  </button>
                </li>
              )
            })}
          </ul>
        </nav>
      )}
    </div>
  )
}

function groupNavItems<T extends string>(items: Array<NavItem<T>>) {
  const ROOT = ''
  const map = new Map<string, Array<NavItem<T>>>()
  for (const item of items) {
    const key = item.group ?? ROOT
    const list = map.get(key) ?? []
    list.push(item)
    map.set(key, list)
  }
  return Array.from(map.entries()).map(([group, entries]) => ({ group, entries }))
}

function getInitials(name: string) {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return 'EC'
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase()
}
