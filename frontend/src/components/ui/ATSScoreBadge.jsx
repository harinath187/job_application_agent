import PropTypes from 'prop-types'

// Thresholds are inclusive lower bounds: score >= 80 -> good, >= 50 -> fair, else poor.
function toneForScore(score) {
  if (score >= 80) return 'good'
  if (score >= 50) return 'fair'
  return 'poor'
}

const toneStyles = {
  good: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-400',
  fair: 'bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-400',
  poor: 'bg-red-100 text-red-700 dark:bg-red-500/20 dark:text-red-400'
}

export function ATSScoreBadge({ score, label = 'ATS Score' }) {
  const clampedScore = Math.max(0, Math.min(100, Math.round(score || 0)))
  const tone = toneForScore(clampedScore)

  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold ${toneStyles[tone]}`}>
      {label}: {clampedScore}
    </span>
  )
}

ATSScoreBadge.propTypes = {
  score: PropTypes.number.isRequired,
  label: PropTypes.string
}
