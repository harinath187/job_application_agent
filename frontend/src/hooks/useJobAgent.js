import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import PropTypes from 'prop-types'
import { agentApi } from '../api/agentApi.js'
import { POLLING_INTERVAL_MS } from '../utils/constants.js'

const JobAgentContext = createContext(null)
const STORAGE_KEY = 'jobAgentSession'

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

function loadStoredSession() {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

function saveStoredSession(data) {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(data))
  } catch {
    // ignore storage errors
  }
}

function clearStoredSession() {
  try {
    sessionStorage.removeItem(STORAGE_KEY)
  } catch {
    // ignore storage errors
  }
}

export function JobAgentProvider({ children }) {
  const [sessionId, setSessionId] = useState('')
  const [jobs, setJobs] = useState([])
  const [status, setStatus] = useState('Waiting for upload')
  const [isProcessing, setIsProcessing] = useState(false)
  const [error, setError] = useState('')
  const [alertInfo, setAlertInfo] = useState({ alertsEnabled: false, alertEmail: null, alertMessage: '' })
  const intervalRef = useRef(null)

  const persistSession = useCallback(
    (nextState) => {
      const currentState = loadStoredSession() || {}
      saveStoredSession({
        sessionId: nextState.sessionId ?? currentState.sessionId ?? sessionId,
        jobs: nextState.jobs ?? currentState.jobs ?? jobs,
        status: nextState.status ?? currentState.status ?? status,
        isProcessing: nextState.isProcessing ?? currentState.isProcessing ?? isProcessing,
        alertInfo: nextState.alertInfo ?? currentState.alertInfo ?? alertInfo
      })
    },
    [alertInfo, jobs, sessionId, status, isProcessing]
  )

  const clearSessionStorage = useCallback(() => {
    clearStoredSession()
  }, [])

  const pollJobs = useCallback(
    async (currentSessionId) => {
      try {
        const data = await agentApi.getJobStatus(currentSessionId)
        const jobsData = data.jobs || []
        const processingStatus = getStatusFromJobs(jobsData, true)
        const nextAlertInfo = {
          alertsEnabled: Boolean(data.alerts_enabled),
          alertEmail: data.alert_email || null,
          alertMessage: data.alert_message || ''
        }

        setJobs(jobsData)
        setStatus(processingStatus)
        setIsProcessing(true)
        setError('')
        setAlertInfo(nextAlertInfo)
        persistSession({ sessionId: currentSessionId, jobs: jobsData, status: processingStatus, isProcessing: true, alertInfo: nextAlertInfo })

        if (jobsData.some((job) => job.status === 'failed')) {
          setError('One or more jobs failed during processing.')
          setIsProcessing(false)
          if (intervalRef.current) {
            clearInterval(intervalRef.current)
            intervalRef.current = null
          }
          persistSession({ isProcessing: false })
          return
        }

        const allComplete = jobsData.length > 0 && jobsData.every((job) => job.status === 'complete')
        if (allComplete) {
          setStatus('Complete!')
          setIsProcessing(false)
          if (intervalRef.current) {
            clearInterval(intervalRef.current)
            intervalRef.current = null
          }
          persistSession({ status: 'Complete!', isProcessing: false })
        }
      } catch (err) {
        console.error('pollJobs error', err)
        setError('Unable to fetch job updates.')
        setIsProcessing(false)
        if (intervalRef.current) {
          clearInterval(intervalRef.current)
          intervalRef.current = null
        }
        persistSession({ isProcessing: false })
      }
    },
    [persistSession]
  )

  const loadSession = useCallback(
    async (targetSessionId, cachedJobs = []) => {
      if (!targetSessionId) {
        return
      }

      setSessionId(targetSessionId)
      if (cachedJobs.length > 0) {
        const initialStatus = getStatusFromJobs(cachedJobs, true)
        setJobs(cachedJobs)
        setStatus(initialStatus)
        setIsProcessing(true)
        persistSession({ sessionId: targetSessionId, jobs: cachedJobs, status: initialStatus, isProcessing: true })
      }

      if (intervalRef.current) {
        clearInterval(intervalRef.current)
      }

      intervalRef.current = setInterval(() => {
        pollJobs(targetSessionId)
      }, POLLING_INTERVAL_MS)

      await pollJobs(targetSessionId)
    },
    [persistSession, pollJobs]
  )

  const startAgent = useCallback(
    async ({ file, role, location, experience }) => {
      try {
        setError('')
        setIsProcessing(true)
        setStatus('Parsing resume...')
        setAlertInfo({ alertsEnabled: false, alertEmail: null, alertMessage: '' })

        const response = await agentApi.uploadResume(file, role, location, experience)
        const session = response.jobReferenceId || response.session_id || response.sessionId || ''

        setSessionId(session)
        setStatus('Searching jobs...')
        persistSession({ sessionId: session, status: 'Searching jobs...', isProcessing: true, alertInfo: { alertsEnabled: false, alertEmail: null, alertMessage: '' } })

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
        persistSession({ status: 'Upload failed', isProcessing: false })
        throw err
      }
    },
    [persistSession, pollJobs]
  )

  useEffect(() => {
    const stored = loadStoredSession()
    if (stored?.sessionId) {
      setSessionId(stored.sessionId)
      setJobs(stored.jobs || [])
      setStatus(stored.status || getStatusFromJobs(stored.jobs || [], false))
      setIsProcessing(Boolean(stored.isProcessing))
      setAlertInfo(stored.alertInfo || { alertsEnabled: false, alertEmail: null, alertMessage: '' })
      loadSession(stored.sessionId, stored.jobs || [])
    }

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
      }
    }
  }, [loadSession])

  const handleDownload = async (filename) => {
    try {
      const blob = await agentApi.downloadFile(filename)
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
      alertInfo,
      startAgent,
      loadSession,
      clearSessionStorage,
      handleDownload
    }),
    [sessionId, jobs, status, isProcessing, error, alertInfo, startAgent, loadSession, clearSessionStorage]
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
