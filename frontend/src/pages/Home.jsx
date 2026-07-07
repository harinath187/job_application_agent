import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ResumeSelector } from '../components/dashboard/ResumeSelector.jsx'
import { Button } from '../components/ui/Button.jsx'
import { useJobAgent } from '../hooks/useJobAgent.jsx'

const EXPERIENCE_OPTIONS = ['Entry level', '1-3 years', '3-5 years', '5+ years']

export function Home() {
  const navigate = useNavigate()
  const { startAgent, runWithSavedResume, error: agentError } = useJobAgent()
  const [selectedFile, setSelectedFile] = useState(null)
  const [selectedResumeId, setSelectedResumeId] = useState('')
  const [role, setRole] = useState('')
  const [location, setLocation] = useState('')
  const [experience, setExperience] = useState('')
  const [error, setError] = useState('')
  const [isProcessing, setIsProcessing] = useState(false)
  const activeError = error || agentError
  const isSwapWarning = typeof activeError === 'string' && activeError.toLowerCase().includes('swapped')

  const handleSelectionChange = ({ file, resumeId }) => {
    setSelectedFile(file || null)
    setSelectedResumeId(resumeId || '')
  }

  const handleRun = async () => {
    if ((!selectedFile && !selectedResumeId) || !role.trim() || !location.trim()) {
      setError('Please select a resume and enter both role and location.')
      return
    }

    setError('')
    setIsProcessing(true)

    try {
      const sessionId = selectedResumeId
        ? await runWithSavedResume({
            resumeId: selectedResumeId,
            role: role.trim(),
            location: location.trim(),
            experience: experience.trim()
          })
        : await startAgent({
            file: selectedFile,
            role: role.trim(),
            location: location.trim(),
            experience: experience.trim()
          })
      const query = new URLSearchParams({ jobReferenceId: sessionId }).toString()
      navigate(`/dashboard?${query}`)
    } catch (uploadError) {
      const backendMessage = uploadError?.response?.data?.detail
      setError(typeof backendMessage === 'string' && backendMessage.trim() ? backendMessage : 'Upload failed. Please ensure the backend is running and try again.')
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
              <ResumeSelector isProcessing={isProcessing} onSelectionChange={handleSelectionChange} />

              <div className="grid gap-4 sm:grid-cols-2">
                <label className="block text-left text-sm font-medium text-slate-700 dark:text-gray-300">
                  Job Title / Role
                  <input
                    type="text"
                    value={role}
                    onChange={(event) => setRole(event.target.value)}
                    required
                    className="mt-2 w-full rounded-2xl border border-gray-300 bg-white px-4 py-3 text-sm text-slate-900 outline-none focus:border-indigo-500 dark:border-gray-700 dark:bg-gray-950 dark:text-white"
                    placeholder="e.g. Product Manager"
                    disabled={isProcessing}
                  />
                  </label>

                <label className="block text-left text-sm font-medium text-slate-700 dark:text-gray-300">
                  Location
                  <input
                    type="text"
                    value={location}
                    onChange={(event) => setLocation(event.target.value)}
                    required
                    className="mt-2 w-full rounded-2xl border border-gray-300 bg-white px-4 py-3 text-sm text-slate-900 outline-none focus:border-indigo-500 dark:border-gray-700 dark:bg-gray-950 dark:text-white"
                    placeholder="e.g. New York, NY"
                    disabled={isProcessing}
                  />
                </label>
              </div>

              {activeError && (
                <p
                  className={`-mt-2 text-sm ${isSwapWarning ? 'font-semibold text-red-300' : 'text-red-400'}`}
                >
                  {activeError}
                </p>
              )}

              <label className="block text-left text-sm font-medium text-slate-700 dark:text-gray-300">
                Experience (optional)
                <select
                  value={experience}
                  onChange={(event) => setExperience(event.target.value)}
                  className="mt-2 w-full rounded-2xl border border-gray-300 bg-white px-4 py-3 text-sm text-slate-900 outline-none focus:border-indigo-500 dark:border-gray-700 dark:bg-gray-950 dark:text-white"
                  disabled={isProcessing}
                >
                  <option value="" className="text-slate-900">
                    Auto / not specified
                  </option>
                  {EXPERIENCE_OPTIONS.map((option) => (
                    <option key={option} value={option} className="text-slate-900">
                      {option}
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
                  disabled={(!selectedFile && !selectedResumeId) || !role.trim() || !location.trim() || isProcessing}
                >
                  {isProcessing ? 'Running...' : 'Run'}
                </Button>
              </div>
            </div>
          </div>
        </div>
      </section>
    </main>
  )
}
