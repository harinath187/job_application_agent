import { createContext, useContext, useEffect, useMemo, useRef, useState } from 'react'
import PropTypes from 'prop-types'
import { uploadResume, getJobs, downloadFile } from '../api/agentApi.js'
import { POLLING_INTERVAL_MS } from '../utils/constants.js'

const JobAgentContext = createContext(null)

function getStatusFromJobs(jobs, isProcessing) {
  if (!isProcessing && jobs.length === 0) {
    return 'Waiting for upload'
  }

  if (jobs.some((job) => job.status === 'failed')) {
    return 'Processing failed'
  }

  if (jobs.length === 0) {
    return 'Parsing resume...'
  }

  const completeCount = jobs.filter((job) => job.status === 'complete').length
  if (completeCount === jobs.length) {
    return 'Complete!'
  }

  if (jobs.some((job) => job.status === 'tailored')) {
    return 'Tailoring resumes...'
  }

  return 'Searching jobs...'
}

export function JobAgentProvider({ children }) {
  const [sessionId, setSessionId] = useState('')
  const [jobs, setJobs] = useState([])
  const [status, setStatus] = useState('Waiting for upload')
  const [isProcessing, setIsProcessing] = useState(false)
  const [error, setError] = useState('')
  const intervalRef = useRef(null)

  useEffect(() => {
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
      }
    }
  }, [])

  const pollJobs = async (currentSessionId) => {
    try {
      const jobsData = await getJobs(currentSessionId)
      setJobs(jobsData)
      const processingStatus = getStatusFromJobs(jobsData, true)
      setStatus(processingStatus)

      if (jobsData.some((job) => job.status === 'failed')) {
        setError('One or more jobs failed during processing.')
        setIsProcessing(false)
        clearInterval(intervalRef.current)
        intervalRef.current = null
        return
      }

      const allComplete = jobsData.length > 0 && jobsData.every((job) => job.status === 'complete')
      if (allComplete) {
        setStatus('Complete!')
        setIsProcessing(false)
        clearInterval(intervalRef.current)
        intervalRef.current = null
      }
    } catch (err) {
      console.error('pollJobs error', err)
      setError('Unable to fetch job updates.')
      setIsProcessing(false)
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
        intervalRef.current = null
      }
    }
  }

  const startAgent = async ({ file, role, location }) => {
    try {
      setError('')
      setIsProcessing(true)
      setStatus('Parsing resume...')
      const response = await uploadResume(file, role, location)
      const session = response.session_id || response.sessionId || ''
      setSessionId(session)
      setStatus('Searching jobs...')

      if (intervalRef.current) {
        clearInterval(intervalRef.current)
      }

      intervalRef.current = setInterval(() => {
        if (session) {
          pollJobs(session)
        }
      }, POLLING_INTERVAL_MS)

      await pollJobs(session)
      return session
    } catch (err) {
      console.error('startAgent error', err)
      setError('Failed to upload resume. Please try again.')
      setIsProcessing(false)
      setStatus('Upload failed')
      throw err
    }
  }

  const handleDownload = async (filename) => {
    try {
      const blob = await downloadFile(filename)
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = filename
      document.body.appendChild(link)
      link.click()
      link.remove()
      URL.revokeObjectURL(url)
    } catch (err) {
      console.error('handleDownload error', err)
      setError('Unable to download file.')
    }
  }

  const contextValue = useMemo(
    () => ({
      sessionId,
      jobs,
      status,
      isProcessing,
      error,
      startAgent,
      handleDownload
    }),
    [sessionId, jobs, status, isProcessing, error]
  )

  return <JobAgentContext.Provider value={contextValue}>{children}</JobAgentContext.Provider>
}

JobAgentProvider.propTypes = {
  children: PropTypes.node.isRequired
}

export function useJobAgent() {
  const context = useContext(JobAgentContext)
  if (!context) {
    throw new Error('useJobAgent must be used within a JobAgentProvider')
  }
  return context
}
