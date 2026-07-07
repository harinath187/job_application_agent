import { useEffect, useState } from 'react'
import PropTypes from 'prop-types'
import { ArrowUpRight, FileText, Download } from 'lucide-react'
import { Badge } from '../ui/Badge.jsx'
import { agentApi } from '../../api/agentApi.js'
import { truncateText } from '../../utils/formatters.js'
import { CURRENCY_SYMBOL } from '../../utils/constants.js'

const statusOptions = ['new', 'applied', 'interview', 'rejected']
const statusLabels = {
  new: 'New',
  applied: 'Applied',
  interview: 'Interview',
  rejected: 'Rejected'
}

function getMatchBadgeClasses(matchPct = 0) {
  if (matchPct >= 80) return 'bg-green-100 text-green-700'
  if (matchPct >= 50) return 'bg-yellow-100 text-yellow-800'
  return 'bg-red-100 text-red-700'
}

function formatSalary(job) {
  const min = job.salary_min
  const max = job.salary_max
  const interval = job.salary_interval
  if (min == null || max == null || !interval) return ''
  const formatter = new Intl.NumberFormat('en-IN')
  return `${CURRENCY_SYMBOL}${formatter.format(min)} - ${CURRENCY_SYMBOL}${formatter.format(max)} / ${interval}`
}

export function JobCard({ job, onDownloadResume, onDownloadCoverLetter, onViewDetail, onStatusChange, onPrepInterview }) {
  const [status, setStatus] = useState(job.status || 'new')
  const [isSaving, setIsSaving] = useState(false)

  useEffect(() => {
    setStatus(job.status || 'new')
  }, [job.status])

  const handleStatusChange = async (event) => {
    const nextStatus = event.target.value
    const previousStatus = status
    setStatus(nextStatus)
    onStatusChange?.(job.id, nextStatus)

    try {
      setIsSaving(true)
      await agentApi.updateJobStatus(job.id, nextStatus)
    } catch (error) {
      setStatus(previousStatus)
      onStatusChange?.(job.id, previousStatus)
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="group relative rounded-3xl border border-gray-800 bg-gray-950 p-6 text-slate-600 transition hover:border-indigo-500/50 dark:border-gray-800 dark:bg-gray-950 dark:text-gray-400">
      <div className="absolute right-6 top-6">
        <Badge label={statusLabels[status] || 'New'} variant={statusOptions.includes(status) ? status : 'new'} />
      </div>

      <div className="mb-4 flex items-start justify-between gap-4 pr-24">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-lg font-semibold text-slate-900 dark:text-white">{job.title}</h3>
            <span className={`rounded-full px-3 py-1 text-xs font-semibold ${getMatchBadgeClasses(job.match_pct ?? 0)}`}>
              {job.match_pct ?? 0}%
            </span>
            {job.salary_min != null && job.salary_max != null && job.salary_interval && (
              <span className="rounded-full bg-gray-100 px-3 py-1 text-xs font-semibold text-gray-700">
                {formatSalary(job)}
              </span>
            )}
          </div>
          <p className="mt-1 text-sm text-slate-600 dark:text-gray-400">
            {job.company} - {job.location}
          </p>
        </div>
      </div>

      <p className="mb-4 text-sm leading-6 text-slate-600 dark:text-gray-400">{truncateText(job.description, 120)}</p>
      <a href={job.job_url} target="_blank" rel="noreferrer" className="mb-4 inline-flex items-center gap-2 text-sm font-medium text-indigo-300 hover:text-white">
        View listing <ArrowUpRight size={16} />
      </a>

      <div className="mb-4 max-w-xs">
        <label className="mb-2 block text-xs font-semibold uppercase tracking-[0.24em] text-gray-500">
          Status
        </label>
        <select
          value={status}
          onChange={handleStatusChange}
          disabled={isSaving}
          className="w-full rounded-xl border border-gray-800 bg-gray-900 px-3 py-2 text-sm text-gray-200 outline-none transition focus:border-indigo-500 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {statusOptions.map((option) => (
            <option key={option} value={option}>
              {statusLabels[option]}
            </option>
          ))}
        </select>
      </div>

      <div className="mt-6 flex flex-wrap gap-3">
        <button
          type="button"
          className="inline-flex items-center justify-center rounded-xl border border-gray-800 bg-gray-900 px-4 py-2 text-sm font-medium text-gray-200 transition hover:border-indigo-500/50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-gray-800 dark:bg-gray-900 dark:text-gray-200"
          onClick={() => onDownloadResume(job.resume_path)}
          disabled={!job.resume_path}
        >
          <FileText size={16} />
          Resume
        </button>
        <button
          type="button"
          className="inline-flex items-center justify-center rounded-xl border border-gray-800 bg-gray-900 px-4 py-2 text-sm font-medium text-gray-200 transition hover:border-indigo-500/50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-gray-800 dark:bg-gray-900 dark:text-gray-200"
          onClick={() => onDownloadCoverLetter(job.cover_letter_path)}
          disabled={!job.cover_letter_path}
        >
          <Download size={16} />
          Cover Letter
        </button>
        <button
          type="button"
          className="ml-auto inline-flex items-center justify-center rounded-xl bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-indigo-700"
          onClick={() => onViewDetail(job.id)}
        >
          Details
        </button>
        <button
          type="button"
          className="inline-flex items-center justify-center rounded-xl border border-gray-800 bg-gray-900 px-4 py-2 text-sm font-medium text-gray-200 transition hover:border-indigo-500/50"
          onClick={() => onPrepInterview?.(job.id)}
        >
          Prep for interview
        </button>
      </div>
    </div>
  )
}

JobCard.propTypes = {
  job: PropTypes.shape({
    id: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    title: PropTypes.string,
    company: PropTypes.string,
    location: PropTypes.string,
    description: PropTypes.string,
    job_url: PropTypes.string,
    resume_path: PropTypes.string,
    cover_letter_path: PropTypes.string,
    salary_min: PropTypes.number,
    salary_max: PropTypes.number,
    salary_interval: PropTypes.string,
    match_pct: PropTypes.number,
    status: PropTypes.string
  }).isRequired,
  onDownloadResume: PropTypes.func.isRequired,
  onDownloadCoverLetter: PropTypes.func.isRequired,
  onViewDetail: PropTypes.func.isRequired,
  onStatusChange: PropTypes.func,
  onPrepInterview: PropTypes.func
}
