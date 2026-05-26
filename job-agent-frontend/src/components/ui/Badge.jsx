import PropTypes from 'prop-types'

const variants = {
  new: 'bg-gray-700 text-gray-300',
  processing: 'bg-amber-500/20 text-amber-400',
  tailored: 'bg-indigo-500/20 text-indigo-400',
  complete: 'bg-emerald-500/20 text-emerald-400',
  failed: 'bg-red-500/20 text-red-400'
}

export function Badge({ label, variant = 'new' }) {
  return <span className={`rounded-full px-3 py-1 text-xs font-semibold ${variants[variant] || variants.new}`}>{label}</span>
}

Badge.propTypes = {
  label: PropTypes.string.isRequired,
  variant: PropTypes.oneOf(['new', 'processing', 'tailored', 'complete', 'failed'])
}
