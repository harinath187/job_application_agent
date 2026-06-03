import PropTypes from 'prop-types'

const variantStyles = {
  primary: 'bg-indigo-600 hover:bg-indigo-700 text-white',
  secondary: 'bg-gray-800 hover:bg-gray-700 text-gray-200',
  danger: 'bg-red-600 hover:bg-red-700 text-white',
  ghost: 'bg-transparent text-slate-900 hover:bg-slate-200 dark:text-white dark:hover:bg-white/10'
}

export function Button({ label, children, onClick, variant = 'primary', disabled, loading, icon, type = 'button' }) {
  const baseStyles = 'inline-flex items-center justify-center rounded-lg px-4 py-2 text-sm font-medium transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-indigo-500'
  const disabledStyles = disabled ? 'opacity-50 cursor-not-allowed' : ''
  const styleClass = `${baseStyles} ${variantStyles[variant] || variantStyles.primary} ${disabledStyles}`

  return (
    <button type={type} className={styleClass} onClick={onClick} disabled={disabled || loading}>
      {loading ? (
        <span className="inline-flex items-center gap-2">
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
          Loading
        </span>
      ) : (
        <>
          {icon && <span className="mr-2">{icon}</span>}
          {label || children}
        </>
      )}
    </button>
  )
}

Button.propTypes = {
  label: PropTypes.string,
  onClick: PropTypes.func,
  variant: PropTypes.oneOf(['primary', 'secondary', 'danger', 'ghost']),
  disabled: PropTypes.bool,
  loading: PropTypes.bool,
  icon: PropTypes.node,
  type: PropTypes.oneOf(['button', 'submit', 'reset'])
}
