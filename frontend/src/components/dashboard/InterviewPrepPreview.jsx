import PropTypes from 'prop-types'

const CATEGORIES = [
  { key: 'technical_questions', label: 'Technical' },
  { key: 'behavioral_questions', label: 'Behavioral' },
  { key: 'resume_specific_questions', label: 'Resume-specific' },
]

const TALKING_POINT_KEYS = {
  technical_questions: 'technical',
  behavioral_questions: 'behavioral',
  resume_specific_questions: 'resume_specific',
}

export function InterviewPrepPreview({ interviewPrep, loading, error, onGenerate }) {
  return (
    <div className="rounded-3xl border border-slate-200 dark:border-gray-800 bg-white dark:bg-gray-950 p-6 shadow-lg shadow-black/5 dark:shadow-black/20">
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-sm uppercase tracking-[0.24em] text-slate-500 dark:text-gray-500">Interview prep</p>
          <h3 className="mt-2 text-xl font-semibold text-slate-900 dark:text-white">Likely questions & talking points</h3>
        </div>
        <button
          onClick={onGenerate}
          disabled={loading}
          className="inline-flex items-center justify-center rounded-2xl bg-indigo-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {loading ? 'Generating…' : interviewPrep ? 'Regenerate' : 'Generate Interview Prep'}
        </button>
      </div>

      {error && <p className="text-sm text-red-600 dark:text-red-300">{error}</p>}

      {!interviewPrep && !loading && !error && (
        <div className="rounded-3xl border border-dashed border-slate-300 dark:border-gray-800 bg-slate-50 dark:bg-gray-900 p-6 text-center text-sm text-slate-600 dark:text-gray-400">
          <p>Generate a tailored set of likely interview questions for this job.</p>
        </div>
      )}

      {interviewPrep && (
        <div className="space-y-6">
          {CATEGORIES.map(({ key, label }) => {
            const questions = interviewPrep[key] || []
            if (!questions.length) return null
            const talkingPoints = interviewPrep.suggested_talking_points?.[TALKING_POINT_KEYS[key]] || []
            return (
              <div key={key}>
                <h4 className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-500 dark:text-gray-500">{label}</h4>
                <ul className="mt-3 list-disc space-y-2 pl-5 text-sm text-slate-700 dark:text-gray-300">
                  {questions.map((question, index) => (
                    <li key={index}>{question}</li>
                  ))}
                </ul>
                {talkingPoints.length > 0 && (
                  <div className="mt-3 rounded-2xl bg-slate-50 dark:bg-gray-900 p-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500 dark:text-gray-500">Talking points</p>
                    <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-600 dark:text-gray-400">
                      {talkingPoints.map((point, index) => (
                        <li key={index}>{point}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

InterviewPrepPreview.propTypes = {
  interviewPrep: PropTypes.shape({
    technical_questions: PropTypes.arrayOf(PropTypes.string),
    behavioral_questions: PropTypes.arrayOf(PropTypes.string),
    resume_specific_questions: PropTypes.arrayOf(PropTypes.string),
    suggested_talking_points: PropTypes.object,
  }),
  loading: PropTypes.bool,
  error: PropTypes.string,
  onGenerate: PropTypes.func.isRequired,
}
