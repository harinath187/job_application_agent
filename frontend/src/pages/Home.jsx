import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { UploadBox } from '../components/dashboard/UploadBox.jsx'
import { Button } from '../components/ui/Button.jsx'
import { useJobAgent } from '../hooks/useJobAgent.jsx'

const EXPERIENCE_OPTIONS = [
  { label: 'Fresher', value: 'fresher' },
  { label: '1-2', value: '1-2' },
  { label: '3-5', value: '3-5' },
  { label: '5+', value: '5+' }
]

export function Home() {
  const navigate = useNavigate()
  const { startAgent, status, submitExperienceLevel } = useJobAgent()
  const [selectedFile, setSelectedFile] = useState(null)
  const [role, setRole] = useState('')
  const [location, setLocation] = useState('')
  const [experience, setExperience] = useState('')
  const [advancedOpen, setAdvancedOpen] = useState(false)
  const [error, setError] = useState('')
  const [isProcessing, setIsProcessing] = useState(false)
  const [uploadKey, setUploadKey] = useState(0)
  const needsExperienceInput = status === 'needs_experience_input'

  const handleFileSelect = (file, validationError) => {
    setError(validationError || '')
    if (!file || validationError) {
      setSelectedFile(null)
      return
    }

    setSelectedFile(file)
  }

  const handleExperienceSelect = async (experienceLevel) => {
    try {
      await submitExperienceLevel(experienceLevel)
    } catch (err) {
      setError('Unable to resume the session. Please try again.')
    }
  }

  const handleRemoveFile = () => {
    setSelectedFile(null)
    setError('')
    setUploadKey((current) => current + 1)
  }

  const handleRun = async () => {
    if (!selectedFile) {
      setError('Please upload a resume before running the agent.')
      return
    }

    setError('')
    setIsProcessing(true)

    try {
      const sessionId = await startAgent({
        file: selectedFile,
        role: role.trim(),
        location: location.trim(),
        experience: experience.trim()
      })
      const query = new URLSearchParams({ jobReferenceId: sessionId }).toString()
      navigate(`/dashboard?${query}`)
    } catch (uploadError) {
      setError('Upload failed. Please ensure the backend is running and try again.')
    } finally {
      setIsProcessing(false)
    }
  }

  return (
    <main className="mx-auto flex min-h-[calc(100vh-64px)] max-w-7xl flex-col gap-8 px-6 py-10">
      <section className="rounded-[2.5rem] border border-gray-800 bg-gray-950 p-10 shadow-2xl shadow-black/25">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
          <div className="max-w-2xl space-y-4">
            <p className="text-sm uppercase tracking-[0.28em] text-indigo-300 dark:text-indigo-300">Career assistant</p>
            <h1 className="text-4xl font-semibold text-slate-900 dark:text-white sm:text-5xl">Tailored job applications in minutes.</h1>
            <p className="text-base leading-8 text-slate-600 dark:text-gray-400">Upload your resume and let the agent generate customized resumes and cover letters for relevant roles. Track progress in real time and download the final application files.</p>
          </div>
          <div className="rounded-[2rem] border border-gray-800 bg-gray-900 p-8 text-center shadow-xl shadow-black/20 dark:border-gray-800 dark:bg-gray-900">
            <h2 className="text-xl font-semibold text-slate-900 dark:text-white">Ready to start?</h2>
            <p className="mt-2 text-sm text-slate-700 dark:text-gray-400">Upload a PDF resume and begin the intelligent job search pipeline.</p>
            <div className="mt-6 space-y-6">
              <UploadBox
                key={uploadKey}
                onFileSelect={handleFileSelect}
                isProcessing={isProcessing}
                role={role}
                location={location}
                onRoleChange={setRole}
                onLocationChange={setLocation}
                advancedOpen={advancedOpen}
                onToggleAdvanced={() => setAdvancedOpen((current) => !current)}
              />

              {selectedFile && (
                <div className="flex items-center gap-3 rounded-2xl border border-gray-800 bg-gray-950/60 px-4 py-3 text-sm text-slate-600 dark:text-gray-300 dark:bg-gray-950/60 dark:border-gray-800">
                  <div className="min-w-0 flex-1 text-left">
                    <p className="text-xs uppercase tracking-[0.24em] text-slate-500 dark:text-gray-500">Selected resume</p>
                    <p className="truncate font-medium text-slate-900 dark:text-white">{selectedFile.name}</p>
                  </div>
                  <button
                    type="button"
                    onClick={handleRemoveFile}
                    disabled={isProcessing}
                    className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-red-500/30 bg-red-500/10 text-red-600 transition hover:border-red-400 hover:bg-red-500/20 hover:text-white disabled:cursor-not-allowed disabled:opacity-50 dark:text-red-200"
                    aria-label="Remove selected resume"
                    title="Remove selected resume"
                  >
                    Remove
                  </button>
                </div>
              )}

              <label className="block text-left text-sm font-medium text-slate-700 dark:text-gray-300">
                Experience (optional)
                <select
                  value={experience}
                  onChange={(event) => setExperience(event.target.value)}
                  className="mt-2 w-full rounded-2xl border border-gray-300 bg-white px-4 py-3 text-sm text-slate-900 outline-none focus:border-indigo-500 dark:border-gray-700 dark:bg-gray-950 dark:text-white"
                  disabled={isProcessing}
                >
                  <option value="" className="bg-white text-slate-900 dark:bg-gray-950 dark:text-white">
                    Auto / not specified
                  </option>
                  {EXPERIENCE_OPTIONS.map((option) => (
                    <option
                      key={option.value}
                      value={option.value}
                      className="bg-white text-slate-900 dark:bg-gray-950 dark:text-white"
                    >
                      {option.label}
                    </option>
                  ))}
                </select>
                <p className="mt-2 text-xs text-slate-500 dark:text-gray-500">
                  Optional. Leave this blank to let the parser infer experience from the resume.
                </p>
              </label>

              <div className="flex justify-center">
                <Button
                  onClick={handleRun}
                  disabled={!selectedFile || isProcessing}
                >
                  {isProcessing ? 'Running...' : 'Run'}
                </Button>
              </div>
            </div>
          </div>
        </div>
        {error && <p className="mt-6 text-sm text-red-400">{error}</p>}
      </section>
      {needsExperienceInput && (
        <section className="rounded-[2rem] border border-amber-500/30 bg-amber-950/40 p-6 text-amber-50 shadow-lg shadow-black/20">
          <h2 className="text-lg font-semibold">Select your experience level</h2>
          <p className="mt-2 text-sm text-amber-100/80">The parser could not determine your experience automatically. Pick the closest match so we can continue.</p>
          <div className="mt-4 flex flex-wrap gap-3">
            {EXPERIENCE_OPTIONS.map((option) => (
              <Button key={option.value} variant="secondary" onClick={() => handleExperienceSelect(option.value)} disabled={isProcessing}>
                {option.label}
              </Button>
            ))}
          </div>
        </section>
      )}
    </main>
  )
}
