import PropTypes from 'prop-types'

const variants = {
  new: 'bg-blue-100 text-blue-700',
  applied: 'bg-yellow-100 text-yellow-700',
  interview: 'bg-green-100 text-green-700',
  rejected: 'bg-red-100 text-red-700'
}

export function Badge({ label, variant = 'new' }) {
  return <span className={`rounded-full px-3 py-1 text-xs font-semibold ${variants[variant] || variants.new}`}>{label}</span>
}

Badge.propTypes = {
  label: PropTypes.string.isRequired,
  variant: PropTypes.oneOf(['new', 'applied', 'interview', 'rejected'])
}
