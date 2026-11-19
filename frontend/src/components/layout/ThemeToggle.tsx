import { Moon, Sun } from 'lucide-react'
import { useTheme } from '../../context/ThemeContext'

interface ThemeToggleProps {
  className?: string
  compact?: boolean
}

export function ThemeToggle({ className = '', compact = false }: ThemeToggleProps) {
  const { theme, toggleTheme } = useTheme()
  const isDark = theme === 'dark'

  return (
    <button
      type="button"
      onClick={toggleTheme}
      aria-label={isDark ? 'Ativar modo claro' : 'Ativar modo noturno'}
      title={isDark ? 'Mudar para modo claro' : 'Mudar para modo noturno'}
      className={`group inline-flex items-center justify-center gap-1.5 rounded-lg border border-slate-200/80 dark:border-slate-700/80 bg-white/80 dark:bg-slate-800/80 text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-white transition-all duration-200 active:scale-95 ${
        compact ? 'p-2' : 'px-2.5 py-2 text-xs font-medium'
      } ${className}`}
    >
      <span className="relative h-4 w-4 grid place-items-center transition-transform duration-200 group-hover:scale-110 group-hover:rotate-12">
        {isDark ? (
          <Sun className="h-4 w-4 text-amber-400" strokeWidth={1.85} />
        ) : (
          <Moon className="h-4 w-4 text-slate-600" strokeWidth={1.85} />
        )}
      </span>
      {!compact && <span className="hidden sm:inline">{isDark ? 'Claro' : 'Noturno'}</span>}
    </button>
  )
}
