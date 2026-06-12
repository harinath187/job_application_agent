import { CloudUpload } from 'lucide-react'
import PropTypes from 'prop-types'
import { ACCEPTED_FILE_TYPE, MAX_FILE_SIZE_MB } from '../../utils/constants.js'

export function UploadBox({ onFileSelect, isProcessing }) {
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
  )
}

UploadBox.propTypes = {
  onFileSelect: PropTypes.func.isRequired,
  isProcessing: PropTypes.bool
}
