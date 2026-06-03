import PropTypes from 'prop-types'

const stageLabel = (status) => {
  if (status === 'Searching jobs...') return 'Searching jobs...'
  if (status === 'Tailoring resumes...') return 'Tailoring resumes...'
  if (status === 'Complete!') return 'Complete!'
  if (status === 'Processing failed') return 'Processing failed'
  if (status.includes('Processing jobs')) return status // Show incremental progress message
  if (status === 'Fetching jobs...') return 'Fetching jobs...'
  if (status === 'Processing...') return 'Processing...'
  return 'Parsing resume...'
}

export function StatusBar({ status, jobsTotal, jobsComplete }) {
  const progress = jobsTotal > 0 ? Math.min((jobsComplete / jobsTotal) * 100, 100) : 0

  return (
    <div className="space-y-4 rounded-3xl border border-gray-800 bg-gray-900 p-6 shadow-lg shadow-black/20">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="text-sm uppercase tracking-[0.24em] text-gray-500">Pipeline status</p>
          <h3 className="mt-2 text-xl font-semibold text-white">{stageLabel(status)}</h3>
        </div>
        <div className="rounded-full bg-gray-800 px-4 py-2 text-sm font-semibold text-gray-300">
          {jobsComplete} of {jobsTotal} jobs complete
        </div>
      </div>
      <div className="h-3 overflow-hidden rounded-full bg-gray-800">
        <div className="h-full rounded-full bg-indigo-600 transition-all duration-500" style={{ width: `${progress}%` }} />
      </div>
    </div>
  )
}

StatusBar.propTypes = {
  status: PropTypes.string.isRequired,
  jobsTotal: PropTypes.number.isRequired,
  jobsComplete: PropTypes.number.isRequired
}
