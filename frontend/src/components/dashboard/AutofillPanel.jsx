import PropTypes from 'prop-types'

export function AutofillPanel({ result, loading, error, onAutofill }) {
  return (
    <div className="rounded-3xl border border-slate-200 dark:border-gray-800 bg-white dark:bg-gray-950 p-6 shadow-lg shadow-black/5 dark:shadow-black/20">
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-sm uppercase tracking-[0.24em] text-slate-500 dark:text-gray-500">Autofill assist</p>
          <h3 className="mt-2 text-xl font-semibold text-slate-900 dark:text-white">Pre-fill this application form</h3>
        </div>
        <button
          onClick={onAutofill}
          disabled={loading}
          className="inline-flex items-center justify-center rounded-2xl bg-indigo-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {loading ? (
            <span className="inline-flex items-center gap-2">
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
              Opening browser…
            </span>
          ) : (
            'Autofill Application'
          )}
        </button>
      </div>

      {error && <p className="text-sm text-red-600 dark:text-red-300">{error}</p>}

      {!result && !loading && !error && (
        <div className="rounded-3xl border border-dashed border-slate-300 dark:border-gray-800 bg-slate-50 dark:bg-gray-900 p-6 text-center text-sm text-slate-600 dark:text-gray-400">
          <p>Opens a visible browser window and pre-fills the fields it can. You always review and submit manually.</p>
        </div>
      )}

      {result && !result.success && (
        <p className="text-sm text-red-600 dark:text-red-300">{result.error || 'Unable to autofill this application.'}</p>
      )}

      {result && result.success && (
        <div className="space-y-4">
          <div className="rounded-2xl bg-emerald-50 dark:bg-emerald-500/10 p-4 text-sm text-emerald-700 dark:text-emerald-400">
            Form has been filled in the opened browser window. Please review all fields and submit manually.
          </div>

          {result.fields_filled?.length > 0 && (
            <div>
              <h4 className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-500 dark:text-gray-500">Fields filled</h4>
              <div className="mt-2 flex flex-wrap gap-2">
                {result.fields_filled.map((field) => (
                  <span key={field} className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-medium text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-400">
                    {field}
                  </span>
                ))}
              </div>
            </div>
          )}

          {result.fields_skipped?.length > 0 && (
            <div>
              <h4 className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-500 dark:text-gray-500">Needs your input</h4>
              <ul className="mt-2 space-y-1.5 text-sm text-slate-600 dark:text-gray-400">
                {result.fields_skipped.map((field) => (
                  <li key={field.field_name}>
                    <span className="font-medium text-slate-800 dark:text-gray-200">{field.field_name}</span> — {field.reason}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

AutofillPanel.propTypes = {
  result: PropTypes.shape({
    fields_filled: PropTypes.arrayOf(PropTypes.string),
    fields_skipped: PropTypes.arrayOf(PropTypes.shape({
      field_name: PropTypes.string,
      reason: PropTypes.string,
    })),
    success: PropTypes.bool,
    error: PropTypes.string,
  }),
  loading: PropTypes.bool,
  error: PropTypes.string,
  onAutofill: PropTypes.func.isRequired,
}
