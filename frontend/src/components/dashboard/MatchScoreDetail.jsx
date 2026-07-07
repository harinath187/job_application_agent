import PropTypes from 'prop-types'

function getBarColor(matchPct) {
  if (matchPct >= 80) return 'bg-green-500'
  if (matchPct >= 50) return 'bg-yellow-500'
  return 'bg-red-500'
}

export function MatchScoreDetail({ matchPct = 0, missingKeywords = [] }) {
  const safePct = Math.max(0, Math.min(100, Number(matchPct) || 0))
  const hasMissing = Array.isArray(missingKeywords) && missingKeywords.length > 0

  return (
    <details className="rounded-3xl border border-gray-800 bg-gray-900 p-6">
      <summary className="cursor-pointer list-none text-sm font-semibold text-white outline-none">
        ATS match score
      </summary>
      <div className="mt-5 space-y-5">
        <div>
          <div className="mb-2 flex items-center justify-between text-sm text-gray-400">
            <span>Match percentage</span>
            <span className="font-semibold text-white">{safePct}%</span>
          </div>
          <div className="h-3 overflow-hidden rounded-full bg-gray-800">
            <div className={`h-full rounded-full ${getBarColor(safePct)}`} style={{ width: `${safePct}%` }} />
          </div>
        </div>

        <div>
          <h3 className="text-sm font-semibold text-white">Missing keywords</h3>
          {hasMissing ? (
            <div className="mt-3 flex flex-wrap gap-2">
              {missingKeywords.map((keyword) => (
                <span key={keyword} className="rounded-full bg-gray-800 px-3 py-1 text-xs font-medium text-gray-200">
                  {keyword}
                </span>
              ))}
            </div>
          ) : (
            <p className="mt-2 text-sm text-gray-400">No missing keywords were identified.</p>
          )}
        </div>

        <p className="text-sm text-gray-400">
          Add these keywords to your resume to improve your ATS match.
        </p>
      </div>
    </details>
  )
}

MatchScoreDetail.propTypes = {
  matchPct: PropTypes.number,
  missingKeywords: PropTypes.arrayOf(PropTypes.string)
}
