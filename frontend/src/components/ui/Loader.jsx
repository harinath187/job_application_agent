import PropTypes from 'prop-types'

export function Loader({ message = '', fullscreen = false }) {
  return (
    <div className={fullscreen ? 'fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-6' : 'flex flex-col items-center gap-3'}>
      <span className="h-10 w-10 animate-spin rounded-full border-4 border-slate-300 dark:border-gray-700 border-t-indigo-500" />
      {message && <p className="text-sm text-slate-500 dark:text-gray-400">{message}</p>}
    </div>
  )
}

Loader.propTypes = {
  message: PropTypes.string,
  fullscreen: PropTypes.bool
}
