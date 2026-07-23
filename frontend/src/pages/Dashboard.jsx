import { useEffect, useMemo } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { Sidebar } from '../components/layout/Sidebar.jsx'
import { StatusBar } from '../components/dashboard/StatusBar.jsx'
import { JobCard } from '../components/dashboard/JobCard.jsx'
import { AlertOptIn } from '../components/dashboard/AlertOptIn.jsx'
import { Button } from '../components/ui/Button.jsx'
import { ATSScoreBadge } from '../components/ui/ATSScoreBadge.jsx'
import { useJobAgent } from '../hooks/useJobAgent.jsx'

export function Dashboard() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const jobReferenceId = searchParams.get('jobReferenceId')
  const { sessionId, jobs, status, error, alertInfo, atsStructureResult, isProcessing, stopAgent, loadSession, handleDownload, submitExperienceLevel, refreshAlertStatus } = useJobAgent()

  const jobsComplete = useMemo(() => jobs.filter((job) => job.status === 'complete' || job.status === 'completed').length, [jobs])
  const sortedJobs = useMemo(() => {
    const getMatchScore = (job) => {
      if (typeof job.skill_match_percentage === 'number') return job.skill_match_percentage
      const matched = job.matched_skills?.length || 0
      const total = matched + (job.missing_skills?.length || 0)
      return total > 0 ? (matched / total) * 100 : 0
    }
    return [...jobs].sort((a, b) => getMatchScore(b) - getMatchScore(a))
  }, [jobs])
  const isComplete = status === 'Complete!'
  const needsExperienceInput = status === 'needs_experience_input'

  useEffect(() => {
    if (!jobReferenceId && !sessionId) {
      navigate('/')
      return
    }

    // Always refetch when opening a specific record, even if it's the same
    // session we last viewed — its alert status may have changed elsewhere
    // (e.g. disabled from Manage Alerts) since we last loaded it.
    if (jobReferenceId) {
      loadSession(jobReferenceId)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobReferenceId])

  const handleViewDetail = (jobId) => {
    navigate(`/jobs/${jobId}`)
  }

  return (
    <div className="flex min-h-[calc(100vh-64px)] bg-slate-50 text-slate-900 dark:bg-gray-950 dark:text-white">
      <Sidebar />
      <main className="flex-1 px-6 py-8">
        <div className="mx-auto max-w-7xl space-y-8">
          <div className="rounded-[2.5rem] border border-slate-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-8 shadow-2xl shadow-black/5 dark:shadow-black/25">
            <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <p className="text-sm uppercase tracking-[0.28em] text-indigo-600 dark:text-indigo-300">Pipeline overview</p>
                <h1 className="mt-3 text-3xl font-semibold text-indigo-600 dark:text-indigo-300">Processing your tailored applications</h1>
                <p className="mt-3 max-w-2xl text-slate-600 dark:text-gray-400">This page polls the backend for live updates as the agent sources jobs, tailors resumes, and generates cover letters.</p>
              </div>
              <div className="flex flex-wrap items-center gap-3">
                {isProcessing && (
                  <Button onClick={stopAgent} variant="danger">Stop</Button>
                )}
                <Button onClick={() => navigate('/')} variant="secondary">Upload a new resume</Button>
              </div>
            </div>
          </div>

          <StatusBar status={status} jobsTotal={jobs.length} jobsComplete={jobsComplete} />
          {error && <div className="rounded-3xl border border-red-300 dark:border-red-700 bg-red-50 dark:bg-red-950 p-4 text-sm text-red-700 dark:text-red-200">{error}</div>}
          {atsStructureResult && (
            <div className="rounded-3xl border border-slate-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-6 shadow-lg shadow-black/5 dark:shadow-black/20">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-sm uppercase tracking-[0.24em] text-slate-500 dark:text-gray-500">Resume ATS check</p>
                  <h3 className="mt-2 text-lg font-semibold text-slate-900 dark:text-white">How ATS-friendly is your resume?</h3>
                </div>
                <ATSScoreBadge score={atsStructureResult.score} />
              </div>
              {atsStructureResult.is_likely_scanned && (
                <p className="mt-3 text-sm text-red-600 dark:text-red-300">
                  Your resume looks like a scanned image or non-machine-readable PDF; most ATS systems cannot read it at all.
                </p>
              )}
              {atsStructureResult.failed_checks?.length > 0 && (
                <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-slate-600 dark:text-gray-400">
                  {atsStructureResult.failed_checks.map((check) => (
                    <li key={check.check_name}>{check.message}</li>
                  ))}
                </ul>
              )}
            </div>
          )}
          {needsExperienceInput && (
            <div className="rounded-3xl border border-amber-500/30 bg-amber-100 dark:bg-amber-950/40 p-5 text-amber-900 dark:text-amber-50">
              <h2 className="text-lg font-semibold">Pick your experience level</h2>
              <p className="mt-2 text-sm text-amber-800/80 dark:text-amber-100/80">We paused the pipeline because the resume did not provide a reliable experience signal.</p>
              <div className="mt-4 flex flex-wrap gap-3">
                {[
                  ['Fresher', 'fresher'],
                  ['1-2', '1-2'],
                  ['3-5', '3-5'],
                  ['5+', '5+']
                ].map(([label, value]) => (
                  <Button key={value} variant="secondary" onClick={() => submitExperienceLevel(value)} disabled={isProcessing}>
                    {label}
                  </Button>
                ))}
              </div>
            </div>
          )}
          <AlertOptIn
            isComplete={isComplete}
            alertsEnabled={alertInfo.alertsEnabled}
            alertEmail={alertInfo.alertEmail}
            alertMessage={alertInfo.alertMessage}
            alertDisabledByUser={alertInfo.alertDisabledByUser}
            onAlertsToggled={refreshAlertStatus}
          />

          <div className="grid gap-6">
            <section className="space-y-6">
              {sortedJobs.map((job) => (
                <JobCard
                  key={job.id}
                  job={job}
                  onDownloadResume={handleDownload}
                  onDownloadCoverLetter={handleDownload}
                  onViewDetail={handleViewDetail}
                />
              ))}
            </section>
          </div>
        </div>
      </main>
    </div>
  )
}
