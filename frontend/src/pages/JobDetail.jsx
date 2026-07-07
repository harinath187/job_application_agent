import { useEffect, useState } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { agentApi } from '../api/agentApi.js'
import { Button } from '../components/ui/Button.jsx'
import { Badge } from '../components/ui/Badge.jsx'
import { MatchScoreDetail } from '../components/dashboard/MatchScoreDetail.jsx'
import { InterviewPrepModal } from '../components/dashboard/InterviewPrepModal.jsx'
import { SkillsGapCard } from '../components/dashboard/SkillsGapCard.jsx'

const statusLabels = {
  new: 'New',
  applied: 'Applied',
  interview: 'Interview',
  rejected: 'Rejected'
}

export function JobDetail() {
  const { jobId } = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  const [job, setJob] = useState(null)
  const [error, setError] = useState('')
  const [skillsGap, setSkillsGap] = useState(null)
  const [isGapLoading, setIsGapLoading] = useState(false)
  const [gapExpanded, setGapExpanded] = useState(false)
  const [prepOpen, setPrepOpen] = useState(false)

  useEffect(() => {
    const fetchJob = async () => {
      try {
        const data = await agentApi.getJobDetail(jobId)
        setJob(data.job)
      } catch {
        setError('Unable to load job details.')
      }
    }

    fetchJob()
  }, [jobId])

  useEffect(() => {
    const loadSkillsGap = async () => {
      if (!gapExpanded || skillsGap) return
      try {
        setIsGapLoading(true)
        const data = await agentApi.getJobSkillsGap(jobId)
        setSkillsGap(data)
      } catch {
        setSkillsGap({ missing_skills: [], transferable_skills: [], suggestions: [] })
      } finally {
        setIsGapLoading(false)
      }
    }

    loadSkillsGap()
  }, [gapExpanded, jobId, skillsGap])

  const handleDownload = async (filename) => {
    try {
      const blob = await agentApi.downloadFile(filename)
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = filename.split('/').pop() || filename
      document.body.appendChild(link)
      link.click()
      link.remove()
      URL.revokeObjectURL(url)
    } catch {
      setError('Unable to download file.')
    }
  }

  const handleBack = () => {
    if (window.history.length > 1 && location.key !== 'default') {
      navigate(-1)
      return
    }

    navigate('/search-history')
  }

  if (error) {
    return <div className="mx-auto max-w-4xl px-6 py-10 text-sm text-red-300">{error}</div>
  }

  if (!job) {
    return <div className="mx-auto max-w-4xl px-6 py-10 text-gray-300">Loading job details...</div>
  }

  return (
    <main className="mx-auto max-w-5xl px-6 py-10">
      <div className="mb-6 flex items-center gap-3">
        <Button onClick={handleBack} variant="ghost">
          <ArrowLeft size={16} />
          Back
        </Button>
      </div>
      <div className="rounded-[2.5rem] border border-gray-800 bg-gray-950 p-8 shadow-2xl shadow-black/25">
        <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-3xl font-semibold text-white">{job.title}</h1>
            <p className="mt-2 text-gray-400">
              {job.company} · {job.location}
            </p>
          </div>
          <Badge
            label={statusLabels[job.status] || 'New'}
            variant={['new', 'applied', 'interview', 'rejected'].includes(job.status) ? job.status : 'new'}
          />
        </div>

        <section className="space-y-6 text-gray-300">
          <div>
            <h2 className="text-lg font-semibold text-white">Job description</h2>
            <p className="mt-3 whitespace-pre-line text-sm leading-7 text-gray-300">{job.description}</p>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="rounded-3xl border border-gray-800 bg-gray-900 p-6">
              <h3 className="text-sm font-semibold uppercase tracking-[0.22em] text-gray-500">Resume</h3>
              <p className="mt-3 text-sm text-gray-400">{job.resume_path ? 'Tailored resume ready for download.' : 'Awaiting generated resume.'}</p>
            </div>
            <div className="rounded-3xl border border-gray-800 bg-gray-900 p-6">
              <h3 className="text-sm font-semibold uppercase tracking-[0.22em] text-gray-500">Cover letter</h3>
              <p className="mt-3 text-sm text-gray-400">{job.cover_letter_path ? 'Tailored cover letter ready for download.' : 'Awaiting generated cover letter.'}</p>
            </div>
          </div>
          <MatchScoreDetail matchPct={job.match_pct ?? 0} missingKeywords={job.missing_keywords || []} />
          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => setPrepOpen(true)}
              className="inline-flex items-center justify-center rounded-2xl bg-indigo-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-indigo-500"
            >
              Prep for interview
            </button>
          </div>
          <details
            className="rounded-3xl border border-gray-800 bg-gray-900 p-6"
            onToggle={(event) => setGapExpanded(event.currentTarget.open)}
          >
            <summary className="cursor-pointer list-none text-sm font-semibold text-white outline-none">
              Skills gap analysis
            </summary>
            <div className="mt-5">
              {isGapLoading ? (
                <p className="text-sm text-gray-400">Loading skills gap analysis...</p>
              ) : (
                <SkillsGapCard
                  missingSkills={skillsGap?.missing_skills || []}
                  transferableSkills={skillsGap?.transferable_skills || []}
                  suggestions={skillsGap?.suggestions || []}
                />
              )}
            </div>
          </details>
          {job.resume_path && (
            <button onClick={() => handleDownload(job.resume_path)} className="inline-flex items-center justify-center rounded-2xl bg-indigo-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-indigo-500">
              Download Resume
            </button>
          )}
          {job.cover_letter_path && (
            <button onClick={() => handleDownload(job.cover_letter_path)} className="inline-flex items-center justify-center rounded-2xl bg-emerald-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-emerald-500">
              Download Cover Letter
            </button>
          )}
        </section>
      </div>
      <InterviewPrepModal jobId={job.id} isOpen={prepOpen} onClose={() => setPrepOpen(false)} />
    </main>
  )
}
