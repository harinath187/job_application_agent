import PropTypes from 'prop-types'

export function CoverLetterPreview({ coverLetterUrl }) {
  return (
    <div className="rounded-3xl border border-slate-200 dark:border-gray-800 bg-white dark:bg-gray-950 p-6 shadow-lg shadow-black/5 dark:shadow-black/20">
      <div className="mb-4 flex items-center justify-between gap-4">
        <div>
          <p className="text-sm uppercase tracking-[0.24em] text-slate-500 dark:text-gray-500">Generated cover letter</p>
          <h3 className="mt-2 text-xl font-semibold text-slate-900 dark:text-white">Preview</h3>
        </div>
      </div>
      <div className="rounded-3xl border border-dashed border-slate-300 dark:border-gray-800 bg-slate-50 dark:bg-gray-900 p-6 text-center text-sm text-slate-600 dark:text-gray-400">
        <p className="font-medium text-slate-800 dark:text-gray-200">Your tailored cover letters are ready.</p>
        <p className="mt-2">Download the version for each job from the dashboard cards.</p>
      </div>
    </div>
  )
}

CoverLetterPreview.propTypes = {
  coverLetterUrl: PropTypes.string
}
