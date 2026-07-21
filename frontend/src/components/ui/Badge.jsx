import PropTypes from 'prop-types'

const variants = {
  new: 'bg-slate-200 text-slate-700 dark:bg-gray-700 dark:text-gray-300',
  processing: 'bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-400',
  tailored: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-500/20 dark:text-indigo-400',
  complete: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-400',
  failed: 'bg-red-100 text-red-700 dark:bg-red-500/20 dark:text-red-400'
}

export function Badge({ label, variant = 'new' }) {
  return <span className={`rounded-full px-3 py-1 text-xs font-semibold ${variants[variant] || variants.new}`}>{label}</span>
}

Badge.propTypes = {
  label: PropTypes.string.isRequired,
  variant: PropTypes.oneOf(['new', 'processing', 'tailored', 'complete', 'failed'])
}
