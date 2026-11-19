interface EchoraLogoProps {
  size?: 'sm' | 'md' | 'lg'
  variant?: 'default' | 'light'
  iconOnly?: boolean
  subtitle?: string
}

const SIZE_MAP = {
  sm: { box: 'h-8 w-8 rounded-lg', text: 'text-base', sub: 'text-[11px]' },
  md: { box: 'h-9 w-9 rounded-lg', text: 'text-lg', sub: 'text-xs' },
  lg: { box: 'h-10 w-10 rounded-xl', text: 'text-xl', sub: 'text-xs' },
}

export function EchoraLogo({
  size = 'md',
  variant = 'default',
  iconOnly = false,
  subtitle,
}: EchoraLogoProps) {
  const dimensions = SIZE_MAP[size]
  const isLight = variant === 'light'

  return (
    <span className="inline-flex items-center gap-2.5 select-none" role={iconOnly ? 'img' : undefined} aria-label={iconOnly ? 'Echora' : undefined}>
      <span
        className={`${dimensions.box} shrink-0 grid place-items-center ${
          isLight ? 'bg-white dark:bg-white p-1' : ''
        }`}
        aria-hidden="true"
      >
        <img src="/favicon.svg" alt="" className="h-full w-full object-contain" />
      </span>
      {!iconOnly && (
        <span className="flex flex-col leading-none">
          <span
            className={`font-display font-bold tracking-tight ${dimensions.text} ${
              isLight ? 'text-white' : 'text-slate-900 dark:text-white'
            }`}
          >
            echora
          </span>
          {subtitle && (
            <span
              className={`mt-0.5 font-normal ${dimensions.sub} ${
                isLight ? 'text-teal-200/90' : 'text-slate-500 dark:text-slate-400'
              }`}
            >
              {subtitle}
            </span>
          )}
        </span>
      )}
    </span>
  )
}
