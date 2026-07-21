import { useState } from 'react'
import PropTypes from 'prop-types'
import { ArrowUpRight, Download } from 'lucide-react'
// FileText icon was used by the resume download button (now disabled)
import { Badge } from '../ui/Badge.jsx'
import { truncateText } from '../../utils/formatters.js'

const statusVariant = {
  pending: 'processing',
  tailored: 'tailored',
  complete: 'complete',
  completed: 'complete',
  failed: 'failed',
  failed_empty_data: 'failed',
  failed_rate_limit: 'failed'
}

const statusMessage = {
  failed_empty_data: 'Resume data incomplete — please retry',
  failed_rate_limit: 'Rate limit hit — please retry later'
}

const BAR_LENGTH = 10

function SkillMatchBar({ percentage }) {
  const filled = Math.round((percentage / 100) * BAR_LENGTH)
  const bar = '█'.repeat(filled) + '░'.repeat(BAR_LENGTH - filled)
  return (
    <p className="mb-1 font-mono text-sm font-medium text-indigo-600 dark:text-indigo-300">
      {bar} {Math.round(percentage)}%
    </p>
  )
}

SkillMatchBar.propTypes = {
  percentage: PropTypes.number.isRequired
}

export function JobCard({ job, onDownloadResume, onDownloadCoverLetter, onViewDetail }) {
  const [showSkills, setShowSkills] = useState(false)
  const matchedCount = job.matched_skills?.length || 0
  const totalCount = matchedCount + (job.missing_skills?.length || 0)
  const matchPercentage = typeof job.skill_match_percentage === 'number'
    ? job.skill_match_percentage
    : totalCount > 0 ? (matchedCount / totalCount) * 100 : 0

  return (
    <div className="group rounded-3xl border border-slate-200 bg-white p-6 text-slate-600 transition hover:border-indigo-500/50 dark:border-gray-800 dark:bg-gray-950 dark:text-gray-400">
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold text-slate-900 dark:text-white">{job.title}</h3>
          <p className="mt-1 text-sm text-slate-600 dark:text-gray-400">
            {job.company} · {job.location}
          </p>
        </div>
        <Badge label={job.status || 'pending'} variant={statusVariant[job.status] || 'new'} />
      </div>
      <p className="mb-4 text-sm leading-6 text-slate-600 dark:text-gray-400">{truncateText(job.description, 120)}</p>
      {totalCount > 0 && (
        <div className="mb-4">
          <button
            type="button"
            className="w-full text-left"
            onClick={() => setShowSkills((prev) => !prev)}
            aria-expanded={showSkills}
          >
            <SkillMatchBar percentage={matchPercentage} />
            <p className="text-sm font-medium text-slate-600 underline decoration-dotted underline-offset-4 dark:text-gray-400">
              {matchedCount} of {totalCount} required skills matched
            </p>
          </button>
          {showSkills && (
            <div className="mt-3 grid gap-3 rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm dark:border-gray-800 dark:bg-gray-900 sm:grid-cols-2">
              {matchedCount > 0 && (
                <div>
                  <p className="mb-1 font-semibold text-emerald-600 dark:text-emerald-400">Matched</p>
                  <ul className="space-y-1">
                    {job.matched_skills.map((skill) => (
                      <li key={skill} className="text-slate-600 dark:text-gray-300">✓ {skill}</li>
                    ))}
                  </ul>
                </div>
              )}
              {job.missing_skills?.length > 0 && (
                <div>
                  <p className="mb-1 font-semibold text-red-500 dark:text-red-400">Missing</p>
                  <ul className="space-y-1">
                    {job.missing_skills.map((skill) => (
                      <li key={skill} className="text-slate-600 dark:text-gray-300">✗ {skill}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      )}
      {statusMessage[job.status] && (
        <p className="mb-4 text-sm font-medium text-amber-500 dark:text-amber-400">{statusMessage[job.status]}</p>
      )}
      <a href={job.job_url} target="_blank" rel="noreferrer" className="mb-4 inline-flex items-center gap-2 text-sm font-medium text-indigo-600 hover:text-indigo-700 dark:text-indigo-300 dark:hover:text-white">
        View listing <ArrowUpRight size={16} />
      </a>
      <div className="mt-6 flex flex-wrap gap-3">
        {/* Resume tailoring is disabled; download button commented out.
        <button
          type="button"
          className="inline-flex items-center justify-center rounded-xl border border-slate-300 bg-slate-100 px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-indigo-500/50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-gray-800 dark:bg-gray-900 dark:text-gray-200"
          onClick={() => onDownloadResume(job.resume_path)}
          disabled={!job.resume_path || job.status !== 'complete'}
        >
          <FileText size={16} />
          Resume
        </button>
        */}
        <button
          type="button"
          className="inline-flex items-center justify-center rounded-xl border border-slate-300 bg-slate-100 px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-indigo-500/50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-gray-800 dark:bg-gray-900 dark:text-gray-200"
          onClick={() => onDownloadCoverLetter(job.cover_letter_path, job, 'Cover Letter')}
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
    status: PropTypes.string,
    skill_match_percentage: PropTypes.number,
    matched_skills: PropTypes.arrayOf(PropTypes.string),
    missing_skills: PropTypes.arrayOf(PropTypes.string)
  }).isRequired,
  onDownloadResume: PropTypes.func.isRequired,
  onDownloadCoverLetter: PropTypes.func.isRequired,
  onViewDetail: PropTypes.func.isRequired
}
