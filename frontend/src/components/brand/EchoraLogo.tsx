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
    <span className="inline-flex items-center gap-2.5 select-none">
      <span
        className={`${dimensions.box} shrink-0 grid place-items-center ${
          isLight
            ? 'bg-white/15 ring-1 ring-white/20'
            : 'bg-brand-700 shadow-xs ring-1 ring-brand-800/10'
        }`}
        aria-hidden="true"
      >
        <svg
          viewBox="0 0 36 36"
          fill="none"
          className="h-[72%] w-[72%]"
          xmlns="http://www.w3.org/2000/svg"
        >
          <circle cx="13.5" cy="18" r="3.2" fill="#FFFFFF" />
          <path
            d="M19.8 13a7 7 0 0 1 0 10"
            stroke="#FFFFFF"
            strokeWidth="2.5"
            strokeLinecap="round"
          />
          <path
            d="M24.2 9.5a11.8 11.8 0 0 1 0 17"
            stroke={isLight ? '#5EEAD4' : '#99F6E4'}
            strokeWidth="2.5"
            strokeLinecap="round"
          />
        </svg>
      </span>
      {!iconOnly && (
        <span className="flex flex-col leading-none">
          <span
            className={`font-display font-bold tracking-tight ${dimensions.text} ${
              isLight ? 'text-white' : 'text-slate-900'
            }`}
          >
            echora
          </span>
          {subtitle && (
            <span
              className={`mt-0.5 font-normal ${dimensions.sub} ${
                isLight ? 'text-teal-200/90' : 'text-slate-500'
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
