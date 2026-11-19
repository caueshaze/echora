import { createContext, type ReactNode, useCallback, useContext, useEffect, useState } from 'react'

export type ThemeMode = 'light' | 'dark'

interface ThemeContextValue {
  theme: ThemeMode
  setTheme: (next: ThemeMode) => void
  toggleTheme: () => void
}

const STORAGE_KEY = 'echora_theme'

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined)

function getInitialTheme(): ThemeMode {
  if (typeof window === 'undefined') return 'light'
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved === 'dark' || saved === 'light') {
      return saved
    }
    if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
      return 'dark'
    }
  } catch {
    // Ignore storage access failures in restricted environments
  }
  return 'light'
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<ThemeMode>(getInitialTheme)

  useEffect(() => {
    const root = document.documentElement
    root.classList.toggle('dark', theme === 'dark')
    try {
      localStorage.setItem(STORAGE_KEY, theme)
    } catch {
      // Ignore storage write failures
    }
    const themeMeta = document.querySelector('meta[name="theme-color"]')
    if (themeMeta) {
      themeMeta.setAttribute('content', theme === 'dark' ? '#0B1120' : '#F8FAFC')
    }
  }, [theme])

  const setTheme = useCallback((next: ThemeMode) => {
    setThemeState(next)
  }, [])

  const toggleTheme = useCallback(() => {
    setThemeState((prev) => (prev === 'dark' ? 'light' : 'dark'))
  }, [])

  return (
    <ThemeContext.Provider value={{ theme, setTheme, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme() {
  const ctx = useContext(ThemeContext)
  if (!ctx) {
    throw new Error('useTheme deve ser usado dentro de ThemeProvider')
  }
  return ctx
}
