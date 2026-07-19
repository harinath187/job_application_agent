import { CloudUpload } from 'lucide-react'
import PropTypes from 'prop-types'
import { ChevronDown, ChevronUp } from 'lucide-react'
import { ACCEPTED_FILE_TYPE, MAX_FILE_SIZE_MB } from '../../utils/constants.js'

export function UploadBox({
  onFileSelect,
  isProcessing,
  role,
  location,
  onRoleChange,
  onLocationChange,
  advancedOpen,
  onToggleAdvanced
}) {
  const handleFile = (file) => {
    if (!file) return
    if (file.type !== ACCEPTED_FILE_TYPE) {
      onFileSelect(null, 'Please upload a PDF file.')
      return
    }

    if (file.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
      onFileSelect(null, `File must be smaller than ${MAX_FILE_SIZE_MB}MB.`)
      return
    }

    onFileSelect(file)
  }

  const handleDrop = (event) => {
    event.preventDefault()
    if (isProcessing) return
    const file = event.dataTransfer.files?.[0]
    handleFile(file)
  }

  const handleChange = (event) => {
    const file = event.target.files?.[0]
    handleFile(file)
  }

  return (
    <>
      <label className={`group relative block cursor-pointer overflow-hidden rounded-3xl border-2 border-dashed ${isProcessing ? 'border-gray-700 bg-gray-900/80' : 'border-gray-700 bg-gray-950 hover:border-indigo-500'} p-10 text-center transition dark:border-gray-700 dark:bg-gray-950 dark:hover:border-indigo-500`}>
        <input type="file" className="sr-only" accept="application/pdf" onChange={handleChange} disabled={isProcessing} />
        <div onDrop={handleDrop} onDragOver={(event) => event.preventDefault()}>
          <div className="mx-auto mb-6 inline-flex h-16 w-16 items-center justify-center rounded-3xl bg-gray-800 text-indigo-400 transition group-hover:bg-gray-700">
            <CloudUpload size={32} />
          </div>
          <h2 className="text-xl font-semibold text-slate-900 dark:text-white">Drag your resume PDF here</h2>
          <p className="mt-2 text-sm text-slate-600 dark:text-gray-400">or click to browse</p>
          {isProcessing && <p className="mt-4 text-sm font-medium text-amber-600 dark:text-amber-300">Processing...</p>}
        </div>
      </label>
      <div className="rounded-3xl border border-gray-800 bg-gray-950/80 p-5 text-left dark:border-gray-800 dark:bg-gray-950/80">
        <button
          type="button"
          onClick={onToggleAdvanced}
          className="flex w-full items-center justify-between text-left text-sm font-semibold text-slate-900 transition hover:text-indigo-600 dark:text-white dark:hover:text-indigo-300"
          disabled={isProcessing}
        >
          <span>Advanced options</span>
          {advancedOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </button>
        {advancedOpen && (
          <div className="mt-4 grid gap-4">
            <label className="block text-left text-sm font-medium text-slate-700 dark:text-gray-300">
              Role override
              <input
                type="text"
                value={role}
                onChange={(event) => onRoleChange(event.target.value)}
                className="mt-2 w-full rounded-2xl border border-gray-300 bg-white px-4 py-3 text-sm text-slate-900 outline-none focus:border-indigo-500 dark:border-gray-700 dark:bg-gray-950 dark:text-white"
                placeholder="Optional: e.g. Product Manager"
                disabled={isProcessing}
              />
            </label>
            <label className="block text-left text-sm font-medium text-slate-700 dark:text-gray-300">
              Location override
              <input
                type="text"
                value={location}
                onChange={(event) => onLocationChange(event.target.value)}
                className="mt-2 w-full rounded-2xl border border-gray-300 bg-white px-4 py-3 text-sm text-slate-900 outline-none focus:border-indigo-500 dark:border-gray-700 dark:bg-gray-950 dark:text-white"
                placeholder="Optional: e.g. New York, NY"
                disabled={isProcessing}
              />
            </label>
            <p className="text-xs text-slate-500 dark:text-gray-500">
              Leave these blank to use inferred roles and metro-city fallback.
            </p>
          </div>
        )}
      </div>
    </>
  )
}

UploadBox.propTypes = {
  onFileSelect: PropTypes.func.isRequired,
  isProcessing: PropTypes.bool,
  role: PropTypes.string.isRequired,
  location: PropTypes.string.isRequired,
  onRoleChange: PropTypes.func.isRequired,
  onLocationChange: PropTypes.func.isRequired,
  advancedOpen: PropTypes.bool.isRequired,
  onToggleAdvanced: PropTypes.func.isRequired
}
