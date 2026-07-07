import { useEffect, useState } from 'react'
import PropTypes from 'prop-types'
import { Edit2, Trash2, FileText } from 'lucide-react'
import { UploadBox } from './UploadBox.jsx'
import { Button } from '../ui/Button.jsx'
import { agentApi } from '../../api/agentApi.js'

const tabs = [
  { id: 'upload', label: 'Upload new' },
  { id: 'saved', label: 'Use saved resume' }
]

export function ResumeSelector({ isProcessing, onSelectionChange }) {
  const [activeTab, setActiveTab] = useState('upload')
  const [selectedFile, setSelectedFile] = useState(null)
  const [selectedResumeId, setSelectedResumeId] = useState('')
  const [resumes, setResumes] = useState([])
  const [editingId, setEditingId] = useState('')
  const [draftLabel, setDraftLabel] = useState('')
  const [error, setError] = useState('')

  const refreshResumes = async () => {
    const data = await agentApi.listResumes()
    setResumes(data.resumes || [])
  }

  useEffect(() => {
    refreshResumes().catch(() => setError('Unable to load saved resumes.'))
  }, [])

  useEffect(() => {
    if (activeTab === 'upload') {
      onSelectionChange?.({ file: selectedFile, resumeId: '' })
    } else {
      onSelectionChange?.({ file: null, resumeId: selectedResumeId })
    }
  }, [activeTab, onSelectionChange, selectedFile, selectedResumeId])

  const handleFileSelect = (file, validationError) => {
    setError(validationError || '')
    setSelectedFile(file || null)
    setSelectedResumeId('')
    if (file && !validationError) {
      setActiveTab('upload')
    }
  }

  const handleSelectResume = (resumeId) => {
    setSelectedResumeId(resumeId)
    setSelectedFile(null)
    setError('')
    setActiveTab('saved')
  }

  const handleRename = async (resumeId) => {
    try {
      await agentApi.renameResume(resumeId, draftLabel.trim())
      setEditingId('')
      setDraftLabel('')
      await refreshResumes()
    } catch {
      setError('Unable to rename resume.')
    }
  }

  const handleDelete = async (resumeId) => {
    try {
      await agentApi.deleteResume(resumeId)
      if (selectedResumeId === resumeId) {
        setSelectedResumeId('')
      }
      await refreshResumes()
    } catch {
      setError('Unable to delete resume.')
    }
  }

  return (
    <div className="space-y-5">
      <div className="inline-flex rounded-full border border-gray-800 bg-gray-950 p-1">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setActiveTab(tab.id)}
            className={`rounded-full px-4 py-2 text-sm font-medium transition ${
              activeTab === tab.id ? 'bg-indigo-600 text-white' : 'text-gray-400 hover:text-white'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === 'upload' ? (
        <UploadBox onFileSelect={handleFileSelect} isProcessing={isProcessing} />
      ) : (
        <div className="space-y-3">
          {resumes.length === 0 ? (
            <p className="rounded-3xl border border-gray-800 bg-gray-950 p-6 text-sm text-gray-400">No saved resumes yet.</p>
          ) : (
            resumes.map((resume) => (
              <div
                key={resume.id}
                className={`rounded-3xl border p-4 text-left transition ${
                  selectedResumeId === resume.id ? 'border-indigo-500 bg-gray-950' : 'border-gray-800 bg-gray-950/60'
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    {editingId === resume.id ? (
                      <div className="flex gap-2">
                        <input
                          value={draftLabel}
                          onChange={(event) => setDraftLabel(event.target.value)}
                          className="w-full rounded-xl border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-white outline-none"
                        />
                        <Button
                          variant="secondary"
                          onClick={() => handleRename(resume.id)}
                          disabled={!draftLabel.trim()}
                        >
                          Save
                        </Button>
                      </div>
                    ) : (
                      <button
                        type="button"
                        className="flex items-center gap-2 text-left"
                        onClick={() => handleSelectResume(resume.id)}
                      >
                        <FileText size={16} className="text-indigo-300" />
                        <span className="font-semibold text-white">{resume.label}</span>
                      </button>
                    )}
                    <p className="mt-2 text-sm text-gray-400">
                      {resume.extracted_role || 'Role not captured'} / {resume.extracted_location || 'Location not captured'}
                    </p>
                    <p className="mt-1 text-xs text-gray-500">
                      Uploaded {resume.uploaded_at ? new Date(resume.uploaded_at).toLocaleDateString() : 'recently'}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => {
                        setEditingId(resume.id)
                        setDraftLabel(resume.label)
                      }}
                      className="rounded-full border border-gray-800 p-2 text-gray-400 transition hover:text-white"
                      aria-label="Rename resume"
                    >
                      <Edit2 size={14} />
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDelete(resume.id)}
                      className="rounded-full border border-gray-800 p-2 text-gray-400 transition hover:text-red-300"
                      aria-label="Delete resume"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {error && <p className="text-sm text-red-400">{error}</p>}
    </div>
  )
}

ResumeSelector.propTypes = {
  isProcessing: PropTypes.bool,
  onSelectionChange: PropTypes.func.isRequired
}
