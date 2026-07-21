import PropTypes from 'prop-types'

export function Card({ children, className = '' }) {
  return <div className={`bg-white dark:bg-gray-900 rounded-xl border border-slate-200 dark:border-gray-800 shadow-lg p-6 ${className}`}>{children}</div>
}

Card.propTypes = {
  children: PropTypes.node.isRequired,
  className: PropTypes.string
}
