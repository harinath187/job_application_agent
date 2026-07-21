import { useEffect, useState } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { agentApi } from '../api/agentApi.js'
import { Button } from '../components/ui/Button.jsx'
import { Badge } from '../components/ui/Badge.jsx'
import { buildDownloadFilename } from '../utils/formatters.js'

const HEADING_PATTERN = /^[A-Za-z][A-Za-z0-9 /&'-]{0,60}:$/

// Recognized section headings, grouped under a canonical label. The order here
// drives the display order of the templated sections.
const SECTION_GROUPS = [
  { key: 'summary', label: 'Summary', match: /^(summary|overview|about( the| this)? (role|job|position)|job summary|description)$/i },
  { key: 'responsibilities', label: 'Responsibilities', match: /^(responsibilities|key responsibilities|what you.?ll do|duties|role and responsibilities)$/i },
  { key: 'requirements', label: 'Requirements', match: /^(requirements|qualifications|what we.?re looking for|who you are|skills( required)?|preferred qualifications|minimum qualifications)$/i },
  { key: 'benefits', label: 'Benefits', match: /^(benefits|perks|what we offer|compensation( and benefits)?)$/i },
]

const EXPERIENCE_PATTERN = /(\d+\+?\s*(?:-\s*\d+\s*)?\s*(?:years?|yrs?)\s*(?:of\s*)?(?:experience)?)/i
const PACKAGE_PATTERN = /(₹\s?\d[\d,.]*\s?(?:lpa|lakhs?)?|(?:rs\.?|inr)\s?\d[\d,.]*|\$\s?\d[\d,.]*\s?(?:k|per\s*(?:hour|year|annum))?(?:\s?-\s?\$?\s?\d[\d,.]*\s?(?:k|per\s*(?:hour|year|annum))?)?|ctc[:\s]*[^\n]*\d[^\n]{0,40})/i

function extractQuickFacts(description) {
  if (!description) return { experience: null, package: null }
  const experienceMatch = description.match(EXPERIENCE_PATTERN)
  const packageMatch = description.match(PACKAGE_PATTERN)
  return {
    experience: experienceMatch ? experienceMatch[1].trim() : null,
    package: packageMatch ? packageMatch[1].trim() : null,
  }
}

function matchSectionGroup(headingText) {
  const normalized = headingText.replace(/:$/, '').trim()
  return SECTION_GROUPS.find((group) => group.match.test(normalized)) || null
}

function renderBlock(block, key) {
  const lines = block.split('\n').map((line) => line.trim()).filter(Boolean)
  const isBulletBlock = lines.length > 0 && lines.every((line) => line.startsWith('- '))

  if (isBulletBlock) {
    return (
      <ul key={key} className="list-disc space-y-1.5 pl-5">
        {lines.map((line, lineIndex) => (
          <li key={lineIndex}>{line.replace(/^- /, '')}</li>
        ))}
      </ul>
    )
  }

  return (
    <p key={key} className="whitespace-pre-line">
      {lines.join('\n')}
    </p>
  )
}

function QuickFact({ label, value }) {
  if (!value) return null
  return (
    <div className="rounded-2xl border border-slate-200 dark:border-gray-800 bg-slate-50 dark:bg-gray-900 px-4 py-3">
      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500 dark:text-gray-500">{label}</p>
      <p className="mt-1 text-sm font-medium text-slate-900 dark:text-white">{value}</p>
    </div>
  )
}

function JobDescription({ job }) {
  const description = job?.description
  if (!description) {
    return <p className="mt-3 text-sm text-slate-500 dark:text-gray-500">No description provided.</p>
  }

  const blocks = description.split(/\n{2,}/).map((block) => block.trim()).filter(Boolean)
  const { experience, package: packageInfo } = extractQuickFacts(description)

  // Group blocks under recognized section headings; anything before the first
  // recognized heading (or when no headings are recognized at all) falls
  // under "Summary" so the description never renders empty.
  const sections = []
  let current = { key: 'summary', label: 'Summary', blocks: [] }
  let sawHeading = false

  blocks.forEach((block) => {
    const lines = block.split('\n').map((line) => line.trim()).filter(Boolean)
    const isHeading = lines.length === 1 && HEADING_PATTERN.test(lines[0])
    const group = isHeading ? matchSectionGroup(lines[0]) : null

    if (isHeading && group) {
      if (current.blocks.length) sections.push(current)
      sawHeading = true
      current = { key: group.key, label: group.label, blocks: [] }
      return
    }

    if (isHeading && !group) {
      // Unrecognized heading: keep it visible as a sub-heading within the
      // current section rather than dropping it.
      current.blocks.push(block)
      return
    }

    current.blocks.push(block)
  })
  if (current.blocks.length) sections.push(current)

  // Merge sections that share the same key (e.g. multiple "Requirements" headings)
  const merged = []
  sections.forEach((section) => {
    const existing = merged.find((s) => s.key === section.key)
    if (existing) {
      existing.blocks.push(...section.blocks)
    } else {
      merged.push(section)
    }
  })

  return (
    <div className="mt-3 space-y-6">
      {(experience || packageInfo) && (
        <div className="grid gap-3 sm:grid-cols-2">
          <QuickFact label="Experience" value={experience} />
          <QuickFact label="Package" value={packageInfo} />
        </div>
      )}
      {merged.map((section) => (
        <div key={section.key}>
          {sawHeading && (
            <h3 className="text-sm font-semibold uppercase tracking-[0.15em] text-slate-500 dark:text-gray-500">
              {section.label}
            </h3>
          )}
          <div className={`space-y-3 text-sm leading-7 text-slate-700 dark:text-gray-300 ${sawHeading ? 'mt-2' : ''}`}>
            {section.blocks.map((block, blockIndex) => renderBlock(block, blockIndex))}
          </div>
        </div>
      ))}
    </div>
  )
}

export function JobDetail() {
  const { jobId } = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  const [job, setJob] = useState(null)
  const [error, setError] = useState('')

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

  const handleDownload = async (filename, label) => {
    try {
      const blob = await agentApi.downloadFile(filename)
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = buildDownloadFilename(job, label, filename)
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
    return (
      <div className="mx-auto max-w-4xl px-6 py-10 text-sm text-red-600 dark:text-red-300">{error}</div>
    )
  }

  if (!job) {
    return <div className="mx-auto max-w-4xl px-6 py-10 text-slate-600 dark:text-gray-300">Loading job details…</div>
  }

  return (
    <main className="mx-auto max-w-5xl px-6 py-10">
      <div className="mb-6 flex items-center gap-3">
        <Button onClick={handleBack} variant="ghost">
          <ArrowLeft size={16} />
          Back
        </Button>
      </div>
      <div className="rounded-[2.5rem] border border-slate-200 dark:border-gray-800 bg-white dark:bg-gray-950 p-8 shadow-2xl shadow-black/5 dark:shadow-black/25">
        <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-3xl font-semibold text-slate-900 dark:text-white">{job.title}</h1>
            <p className="mt-2 text-slate-600 dark:text-gray-400">{job.company} · {job.location}</p>
          </div>
          <Badge label={job.status || 'pending'} variant={job.status === 'complete' ? 'complete' : job.status === 'failed' ? 'failed' : 'processing'} />
        </div>

        <section className="space-y-6 text-slate-700 dark:text-gray-300">
          <div>
            <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Job description</h2>
            <JobDescription job={job} />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            {/* Resume tailoring is disabled; status block commented out.
            <div className="rounded-3xl border border-slate-200 dark:border-gray-800 bg-slate-50 dark:bg-gray-900 p-6">
              <h3 className="text-sm font-semibold uppercase tracking-[0.22em] text-slate-500 dark:text-gray-500">Resume</h3>
              <p className="mt-3 text-sm text-slate-600 dark:text-gray-400">{job.resume_path ? 'Tailored resume ready for download.' : 'Awaiting generated resume.'}</p>
            </div>
            */}
            <div className="rounded-3xl border border-slate-200 dark:border-gray-800 bg-slate-50 dark:bg-gray-900 p-6">
              <h3 className="text-sm font-semibold uppercase tracking-[0.22em] text-slate-500 dark:text-gray-500">Cover letter</h3>
              <p className="mt-3 text-sm text-slate-600 dark:text-gray-400">{job.cover_letter_path ? 'Tailored cover letter ready for download.' : 'Awaiting generated cover letter.'}</p>
            </div>
          </div>
          {/* Resume tailoring is disabled; download button commented out.
          {job.resume_path && (
            <button onClick={() => handleDownload(job.resume_path)} className="inline-flex items-center justify-center rounded-2xl bg-indigo-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-indigo-500">
              Download Resume
            </button>
          )}
          */}
          {job.cover_letter_path && (
            <button onClick={() => handleDownload(job.cover_letter_path, 'Cover Letter')} className="inline-flex items-center justify-center rounded-2xl bg-emerald-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-emerald-500">
              Download Cover Letter
            </button>
          )}
        </section>
      </div>
    </main>
  )
}
