export function formatDate(isoString) {
  if (!isoString) return ''
  const date = new Date(isoString)
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric'
  })
}

export function truncateText(text, maxLength) {
  if (!text) return ''
  return text.length > maxLength ? `${text.slice(0, maxLength).trim()}...` : text
}

export function formatFileSize(bytes) {
  if (bytes === undefined || bytes === null) return ''
  const mb = bytes / 1024 / 1024
  return `${mb.toFixed(1)} MB`
}

export function sanitiseCompanyName(name) {
  if (!name) return ''
  return name
    .toLowerCase()
    .trim()
    .replace(/\s+/g, '-')
    .replace(/[^a-z0-9-]/g, '')
}

function getFileExtension(path) {
  const basename = path.split('/').pop() || path
  const dotIndex = basename.lastIndexOf('.')
  return dotIndex > -1 ? basename.slice(dotIndex) : ''
}

/**
 * Builds a human-readable download filename (e.g. "50Hertz - Front End Developer - Cover Letter.docx")
 * from job title/company, falling back to the server-generated basename when either is missing.
 */
export function buildDownloadFilename(job, label, serverPath) {
  const extension = getFileExtension(serverPath || '')
  const parts = [job?.company, job?.title, label].filter((part) => part && part.trim())
  if (parts.length === 0) {
    return (serverPath || '').split('/').pop() || serverPath
  }
  return `${parts.join(' - ')}${extension}`
}
