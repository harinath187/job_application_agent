import PropTypes from 'prop-types'

export function ResumePreview({ resumeUrl }) {
  return (
    <div className="rounded-3xl border border-gray-800 bg-gray-950 p-6 shadow-lg shadow-black/20">
      <div className="mb-4 flex items-center justify-between gap-4">
        <div>
          <p className="text-sm uppercase tracking-[0.24em] text-gray-500">Generated resume</p>
          <h3 className="mt-2 text-xl font-semibold text-white">Preview</h3>
        </div>
      </div>
      <div className="rounded-3xl border border-dashed border-gray-800 bg-gray-900 p-6 text-center text-sm text-gray-400">
        <p className="font-medium text-gray-200">Your tailored resume is ready.</p>
        <p className="mt-2">Use the download buttons in the job card to save it locally.</p>
      </div>
    </div>
  )
}

ResumePreview.propTypes = {
  resumeUrl: PropTypes.string
}
