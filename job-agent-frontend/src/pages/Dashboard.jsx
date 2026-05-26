import { useEffect, useMemo, useState } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { Sidebar } from '../components/layout/Sidebar.jsx'
import { StatusBar } from '../components/dashboard/StatusBar.jsx'
import { JobCard } from '../components/dashboard/JobCard.jsx'
import { ResumePreview } from '../components/dashboard/ResumePreview.jsx'
import { CoverLetterPreview } from '../components/dashboard/CoverLetterPreview.jsx'
import { agentApi } from '../api/agentApi.js'
import { Button } from '../components/ui/Button.jsx'

export function Dashboard() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const jobReferenceId = searchParams.get('jobReferenceId')
  const [jobs, setJobs] = useState([])
  const [status, setStatus] = useState('Waiting for upload...')
  const [error, setError] = useState('')

  const jobsComplete = useMemo(() => jobs.filter((job) => job.status === 'complete').length, [jobs])

  useEffect(() => {
    if (!jobReferenceId) {
      navigate('/')
      return
    }

    const fetchJobs = async () => {
      try {
        const data = await agentApi.getJobStatus(jobReferenceId)
        setJobs(data.jobs || [])
        setStatus(data.status || 'Waiting for results...')
      } catch (fetchError) {
        setError('Unable to retrieve job status.')
      }
    }

    let intervalId = null

    const poll = async () => {
      await fetchJobs()
      intervalId = setInterval(async () => {
        try {
          const data = await agentApi.getJobStatus(jobReferenceId)
          setJobs(data.jobs || [])
          setStatus(data.status || 'Waiting for results...')
          if (data.status === 'Complete!' || data.status === 'Processing failed') {
            if (intervalId) clearInterval(intervalId)
          }
        } catch {
          if (intervalId) clearInterval(intervalId)
          setError('Polling failed. Please reload the page.')
        }
      }, 5000)
    }

    poll()
    return () => {
      if (intervalId) clearInterval(intervalId)
    }
  }, [jobReferenceId, navigate])

  const handleDownload = async (url) => {
    try {
      await agentApi.downloadFile(url)
    } catch {
      setError('Download failed. Please try again.')
    }
  }

  const handleViewDetail = (jobId) => {
    navigate(`/jobs/${jobId}`)
  }

  return (
    <div className="flex min-h-[calc(100vh-64px)] bg-gray-950 text-white">
      <Sidebar />
      <main className="flex-1 px-6 py-8">
        <div className="mx-auto max-w-7xl space-y-8">
          <div className="rounded-[2.5rem] border border-gray-800 bg-gray-900 p-8 shadow-2xl shadow-black/25">
            <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <p className="text-sm uppercase tracking-[0.28em] text-indigo-300">Pipeline overview</p>
                <h1 className="mt-3 text-3xl font-semibold text-white">Processing your tailored applications</h1>
                <p className="mt-3 max-w-2xl text-gray-400">This page polls the backend for live updates as the agent sources jobs, tailors resumes, and generates cover letters.</p>
              </div>
              <div className="flex items-center gap-3">
                <Button onClick={() => navigate('/')} variant="secondary">Upload a new resume</Button>
              </div>
            </div>
          </div>

          <StatusBar status={status} jobsTotal={jobs.length} jobsComplete={jobsComplete} />
          {error && <div className="rounded-3xl border border-red-700 bg-red-950 p-4 text-sm text-red-200">{error}</div>}

          <div className="grid gap-6 xl:grid-cols-[2fr_1fr]">
            <section className="space-y-6">
              {jobs.map((job) => (
                <JobCard
                  key={job.id}
                  job={job}
                  onDownloadResume={handleDownload}
                  onDownloadCoverLetter={handleDownload}
                  onViewDetail={handleViewDetail}
                />
              ))}
            </section>
            <aside className="space-y-6">
              <ResumePreview resumeUrl={jobsComplete > 0 ? jobs.find((job) => job.resume_path)?.resume_path : ''} />
              <CoverLetterPreview coverLetterUrl={jobsComplete > 0 ? jobs.find((job) => job.cover_letter_path)?.cover_letter_path : ''} />
            </aside>
          </div>
        </div>
      </main>
    </div>
  )
}
