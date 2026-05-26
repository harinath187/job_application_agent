import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { UploadBox } from '../components/dashboard/UploadBox.jsx'
import { Button } from '../components/ui/Button.jsx'
import { agentApi } from '../api/agentApi.js'

export function Home() {
  const navigate = useNavigate()
  const [error, setError] = useState('')
  const [isProcessing, setIsProcessing] = useState(false)

  const handleFileSelect = async (file, validationError) => {
    setError(validationError || '')
    if (!file || validationError) return

    setIsProcessing(true)
    const formData = new FormData()
    formData.append('resume', file)

    try {
      const { jobReferenceId } = await agentApi.uploadResume(formData)
      navigate(`/dashboard?jobReferenceId=${jobReferenceId}`)
    } catch (uploadError) {
      setError('Upload failed. Please try again.')
    } finally {
      setIsProcessing(false)
    }
  }

  return (
    <main className="mx-auto flex min-h-[calc(100vh-64px)] max-w-7xl flex-col gap-8 px-6 py-10">
      <section className="rounded-[2.5rem] border border-gray-800 bg-gray-950 p-10 shadow-2xl shadow-black/25">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
          <div className="max-w-2xl space-y-4">
            <p className="text-sm uppercase tracking-[0.28em] text-indigo-300">Career assistant</p>
            <h1 className="text-4xl font-semibold text-white sm:text-5xl">Tailored job applications in minutes.</h1>
            <p className="text-base leading-8 text-gray-400">Upload your resume and let the agent generate customized resumes and cover letters for relevant roles. Track progress in real time and download the final application files.</p>
          </div>
          <div className="rounded-[2rem] border border-gray-800 bg-gray-900 p-8 text-center shadow-xl shadow-black/20">
            <h2 className="text-xl font-semibold text-white">Ready to start?</h2>
            <p className="mt-2 text-sm text-gray-400">Upload a PDF resume and begin the intelligent job search pipeline.</p>
            <div className="mt-6">
              <UploadBox onFileSelect={handleFileSelect} isProcessing={isProcessing} />
            </div>
          </div>
        </div>
        {error && <p className="mt-6 text-sm text-red-400">{error}</p>}
      </section>
    </main>
  )
}
