import PropTypes from 'prop-types'
import { CheckCircle2, Loader2 } from 'lucide-react'

const STEP_PATTERNS = [
  { step: 1, patterns: ['Extracting text from resume'] },
  { step: 2, patterns: ['Identifying role, location and skills'] },
  { step: 3, patterns: ['Searching LinkedIn, Indeed and Naukri'] },
  { step: 4, patterns: ['Found '] },
  { step: 5, patterns: ['Tailoring resume for'] },
  { step: 6, patterns: ['Writing cover letter for'] },
  { step: 7, patterns: ['All done!'] }
]

function getStepFromMessage(message) {
  const match = STEP_PATTERNS.find(({ patterns }) => patterns.some((pattern) => message.includes(pattern)))
  return match ? match.step : 0
}

export function StatusBar({ statusMessage, isComplete }) {
  const step = getStepFromMessage(statusMessage)

  return (
    <div className="space-y-4 rounded-3xl border border-gray-800 bg-gray-900 p-6 shadow-lg shadow-black/20">
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className={`flex h-11 w-11 items-center justify-center rounded-full ${isComplete ? 'bg-emerald-500/15 text-emerald-400' : 'bg-indigo-500/15 text-indigo-300'}`}>
            {isComplete ? <CheckCircle2 size={22} /> : <Loader2 className="animate-spin" size={22} />}
          </div>
          <div>
            <p className="text-sm uppercase tracking-[0.24em] text-gray-500">Pipeline status</p>
            <h3 className="mt-1 text-xl font-semibold text-white">{statusMessage}</h3>
          </div>
        </div>
        <div className="rounded-full bg-gray-800 px-4 py-2 text-sm font-semibold text-gray-300">
          Step {step || 0} of 7
        </div>
      </div>

      <div className="h-2 overflow-hidden rounded-full bg-gray-800">
        <div
          className={`h-full rounded-full transition-all duration-500 ${isComplete ? 'bg-emerald-500' : 'bg-indigo-600'}`}
          style={{ width: `${(step / 7) * 100}%` }}
        />
      </div>
    </div>
  )
}

StatusBar.propTypes = {
  statusMessage: PropTypes.string.isRequired,
  isComplete: PropTypes.bool.isRequired
}
