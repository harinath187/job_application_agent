import { useEffect, useMemo, useState } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { Sidebar } from '../components/layout/Sidebar.jsx'
import { StatusBar } from '../components/dashboard/StatusBar.jsx'
import { JobCard } from '../components/dashboard/JobCard.jsx'
import { ResumePreview } from '../components/dashboard/ResumePreview.jsx'
import { CoverLetterPreview } from '../components/dashboard/CoverLetterPreview.jsx'
import { InterviewPrepModal } from '../components/dashboard/InterviewPrepModal.jsx'
import { AlertOptIn } from '../components/dashboard/AlertOptIn.jsx'
import { Button } from '../components/ui/Button.jsx'
import { useJobAgent } from '../hooks/useJobAgent.jsx'

export function Dashboard() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const jobReferenceId = searchParams.get('jobReferenceId')
  const { sessionId, jobs, statusMessage, isComplete, error, alertInfo, isProcessing, stopAgent, loadSession, handleDownload } = useJobAgent()
  const [locationFilter, setLocationFilter] = useState('')
  const [sortBy, setSortBy] = useState('match')
  const [searchQuery, setSearchQuery] = useState('')
  const [prepJobId, setPrepJobId] = useState('')

  const jobsComplete = useMemo(() => jobs.filter((job) => job.resume_path && job.cover_letter_path).length, [jobs])
  const locations = useMemo(
    () => Array.from(new Set(jobs.map((job) => job.location).filter(Boolean))).sort((a, b) => a.localeCompare(b)),
    [jobs]
  )

  const displayedJobs = useMemo(
    () =>
      [...jobs]
        .filter((job) => !locationFilter || job.location === locationFilter)
        .filter((job) => {
          if (!searchQuery) return true
          const query = searchQuery.toLowerCase()
          return (job.title || '').toLowerCase().includes(query) || (job.company || '').toLowerCase().includes(query)
        })
        .sort((a, b) =>
          sortBy === 'match'
            ? (b.match_pct ?? 0) - (a.match_pct ?? 0)
            : sortBy === 'newest'
              ? new Date(b.created_at || 0) - new Date(a.created_at || 0)
              : (a.company || '').localeCompare(b.company || '')
        ),
    [jobs, locationFilter, searchQuery, sortBy]
  )

  const hasActiveFilters = Boolean(locationFilter || searchQuery || sortBy !== 'match')

  const clearFilters = () => {
    setLocationFilter('')
    setSortBy('match')
    setSearchQuery('')
  }

  useEffect(() => {
    const activeSession = jobReferenceId || sessionId
    if (!activeSession) {
      navigate('/')
      return
    }

    if (jobReferenceId && jobReferenceId !== sessionId) {
      loadSession(jobReferenceId)
    }
  }, [jobReferenceId, sessionId, loadSession, navigate])

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
                <h1 className="mt-3 text-3xl font-semibold text-indigo-300">Processing your tailored applications</h1>
                <p className="mt-3 max-w-2xl text-gray-400">This page polls the backend for live updates as the agent sources jobs, tailors resumes, and generates cover letters.</p>
              </div>
              <div className="flex flex-wrap items-center gap-3">
                {isProcessing && (
                  <Button onClick={stopAgent} variant="danger">Stop</Button>
                )}
                <Button onClick={() => navigate('/')} variant="secondary">Upload a new resume</Button>
              </div>
            </div>
          </div>

          <StatusBar statusMessage={statusMessage} isComplete={isComplete} />
          {error && <div className="rounded-3xl border border-red-700 bg-red-950 p-4 text-sm text-red-200">{error}</div>}
          <AlertOptIn
            isComplete={isComplete}
            alertsEnabled={alertInfo.alertsEnabled}
            alertEmail={alertInfo.alertEmail}
            alertMessage={alertInfo.alertMessage}
          />

          <div className="grid gap-6 xl:grid-cols-[2fr_1fr]">
            <section className="space-y-6">
              <div className="flex flex-wrap gap-3 mb-6">
                <select
                  value={locationFilter}
                  onChange={(event) => setLocationFilter(event.target.value)}
                  className={`rounded-lg border border-gray-200 px-3 py-2 text-sm text-slate-900 outline-none ${locationFilter ? 'ring-2 ring-blue-500' : ''}`}
                >
                  <option value="">All locations</option>
                  {locations.map((location) => (
                    <option key={location} value={location}>
                      {location}
                    </option>
                  ))}
                </select>

                <select
                  value={sortBy}
                  onChange={(event) => setSortBy(event.target.value)}
                  className={`rounded-lg border border-gray-200 px-3 py-2 text-sm text-slate-900 outline-none ${sortBy !== 'match' ? 'ring-2 ring-blue-500' : ''}`}
                >
                  <option value="match">Best match</option>
                  <option value="newest">Newest first</option>
                  <option value="company">Company A–Z</option>
                </select>

                <div className="relative">
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(event) => setSearchQuery(event.target.value)}
                    placeholder="Search title or company"
                    className={`rounded-lg border border-gray-200 px-3 py-2 pr-9 text-sm text-slate-900 outline-none ${searchQuery ? 'ring-2 ring-blue-500' : ''}`}
                  />
                  {searchQuery && (
                    <button
                      type="button"
                      onClick={() => setSearchQuery('')}
                      className="absolute right-2 top-1/2 -translate-y-1/2 text-lg leading-none text-slate-500 hover:text-slate-800"
                      aria-label="Clear search"
                    >
                      ×
                    </button>
                  )}
                </div>
              </div>

              {displayedJobs.length === 0 && hasActiveFilters ? (
                <div className="rounded-3xl border border-gray-800 bg-gray-900 p-6 text-sm text-gray-300">
                  <p>No jobs match your filters.</p>
                  <button
                    type="button"
                    onClick={clearFilters}
                    className="mt-4 inline-flex items-center rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
                  >
                    Clear filters
                  </button>
                </div>
              ) : (
                displayedJobs.map((job) => (
                  <JobCard
                    key={job.id}
                    job={job}
                    onDownloadResume={handleDownload}
                    onDownloadCoverLetter={handleDownload}
                    onViewDetail={handleViewDetail}
                    onPrepInterview={setPrepJobId}
                  />
                ))
              )}
            </section>
            <aside className="space-y-6">
              <ResumePreview resumeUrl={jobsComplete > 0 ? jobs.find((job) => job.resume_path)?.resume_path : ''} />
              <CoverLetterPreview coverLetterUrl={jobsComplete > 0 ? jobs.find((job) => job.cover_letter_path)?.cover_letter_path : ''} />
            </aside>
          </div>
        </div>
      </main>
      <InterviewPrepModal jobId={prepJobId} isOpen={Boolean(prepJobId)} onClose={() => setPrepJobId('')} />
    </div>
  )
}
