import PropTypes from 'prop-types'

export function CoverLetterPreview({ coverLetterUrl }) {
  return (
    <div className="rounded-3xl border border-gray-800 bg-gray-950 p-6 shadow-lg shadow-black/20">
      <div className="mb-4 flex items-center justify-between gap-4">
        <div>
          <p className="text-sm uppercase tracking-[0.24em] text-gray-500">Generated cover letter</p>
          <h3 className="mt-2 text-xl font-semibold text-white">Preview</h3>
        </div>
      </div>
      <div className="rounded-3xl border border-dashed border-gray-800 bg-gray-900 p-6 text-center text-sm text-gray-400">
        <p className="font-medium text-gray-200">Your tailored cover letters are ready.</p>
        <p className="mt-2">Download the version for each job from the dashboard cards.</p>
      </div>
      {coverLetterUrl && (
        <a
          href={coverLetterUrl}
          download
          className="mt-6 inline-flex w-full items-center justify-center rounded-2xl bg-emerald-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-emerald-500"
        >
          Download Cover Letter
        </a>
      )}
    </div>
  )
}

CoverLetterPreview.propTypes = {
  coverLetterUrl: PropTypes.string
}
