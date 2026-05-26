import PropTypes from 'prop-types'

export function Card({ children, className = '' }) {
  return <div className={`bg-gray-900 rounded-xl border border-gray-800 shadow-lg p-6 ${className}`}>{children}</div>
}

Card.propTypes = {
  children: PropTypes.node.isRequired,
  className: PropTypes.string
}
