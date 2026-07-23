import PropTypes from 'prop-types'
import { ATSScoreBadge } from '../ui/ATSScoreBadge.jsx'

function KeywordChip({ keyword, matched }) {
  const toneClass = matched
    ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-400'
    : 'bg-slate-200 text-slate-700 dark:bg-gray-700 dark:text-gray-300'
  return <span className={`rounded-full px-3 py-1 text-xs font-medium ${toneClass}`}>{keyword}</span>
}

KeywordChip.propTypes = {
  keyword: PropTypes.string.isRequired,
  matched: PropTypes.bool.isRequired
}

export function ATSMatchPreview({ atsMatch, loading, error, onCheck }) {
  return (
    <div className="rounded-3xl border border-slate-200 dark:border-gray-800 bg-white dark:bg-gray-950 p-6 shadow-lg shadow-black/5 dark:shadow-black/20">
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-sm uppercase tracking-[0.24em] text-slate-500 dark:text-gray-500">ATS match</p>
          <h3 className="mt-2 text-xl font-semibold text-slate-900 dark:text-white">How well does your resume match this job?</h3>
        </div>
        <button
          onClick={onCheck}
          disabled={loading}
          className="inline-flex items-center justify-center rounded-2xl bg-indigo-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {loading ? (
            <span className="inline-flex items-center gap-2">
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
              Checking…
            </span>
          ) : atsMatch ? (
            'Recheck ATS Match'
          ) : (
            'Check ATS Match for This Job'
          )}
        </button>
      </div>

      {error && <p className="text-sm text-red-600 dark:text-red-300">{error}</p>}

      {!atsMatch && !loading && !error && (
        <div className="rounded-3xl border border-dashed border-slate-300 dark:border-gray-800 bg-slate-50 dark:bg-gray-900 p-6 text-center text-sm text-slate-600 dark:text-gray-400">
          <p>Check how your resume's keywords line up with this job description.</p>
        </div>
      )}

      {atsMatch && (
        <div className="space-y-4">
          <ATSScoreBadge score={atsMatch.match_score} label="Match Score" />

          {atsMatch.matched_keywords?.length > 0 && (
            <div>
              <h4 className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-500 dark:text-gray-500">Matched keywords</h4>
              <div className="mt-2 flex flex-wrap gap-2">
                {atsMatch.matched_keywords.map((keyword) => (
                  <KeywordChip key={keyword} keyword={keyword} matched />
                ))}
              </div>
            </div>
          )}

          {atsMatch.missing_keywords?.length > 0 && (
            <div>
              <h4 className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-500 dark:text-gray-500">Missing keywords</h4>
              <div className="mt-2 flex flex-wrap gap-2">
                {atsMatch.missing_keywords.map((keyword) => (
                  <KeywordChip key={keyword} keyword={keyword} matched={false} />
                ))}
              </div>
            </div>
          )}

          {atsMatch.notes && (
            <div className="rounded-2xl bg-slate-50 dark:bg-gray-900 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500 dark:text-gray-500">Notes</p>
              <p className="mt-2 text-sm text-slate-600 dark:text-gray-400">{atsMatch.notes}</p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

ATSMatchPreview.propTypes = {
  atsMatch: PropTypes.shape({
    match_score: PropTypes.number,
    matched_keywords: PropTypes.arrayOf(PropTypes.string),
    missing_keywords: PropTypes.arrayOf(PropTypes.string),
    notes: PropTypes.string
  }),
  loading: PropTypes.bool,
  error: PropTypes.string,
  onCheck: PropTypes.func.isRequired
}
