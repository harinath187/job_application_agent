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
  const [theme, setTheme] = useState(() => {
    if (typeof window !== 'undefined') {
      return window.localStorage.getItem('theme') || 'dark'
    }
    return 'dark'
  })
  const intervalRef = useRef(null)
  const isPollingRef = useRef(false)

  const clearPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
    isPollingRef.current = false
  }, [])

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

  const toggleTheme = useCallback(() => {
    setTheme((current) => (current === 'dark' ? 'light' : 'dark'))
  }, [])

  useEffect(() => {
    if (typeof document === 'undefined') {
      return
    }

    document.documentElement.classList.toggle('light', theme === 'light')
    document.documentElement.classList.toggle('dark', theme === 'dark')
    window.localStorage.setItem('theme', theme)
  }, [theme])

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

  const startPolling = useCallback(
    (currentSessionId) => {
      if (!currentSessionId) {
        return
      }

      clearPolling()
      intervalRef.current = setInterval(async () => {
        if (isPollingRef.current) {
          return
        }

        isPollingRef.current = true
        try {
          await pollJobs(currentSessionId)
        } finally {
          isPollingRef.current = false
        }
      }, POLLING_INTERVAL_MS)
    },
    [clearPolling, pollJobs]
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

      startPolling(targetSessionId)
      await pollJobs(targetSessionId)
    },
    [persistSession, pollJobs, startPolling]
  )

  const startAgent = useCallback(
    async ({ file, role, location }) => {
      try {
        setError('')
        setIsProcessing(true)
        setStatus('Parsing resume...')
        setAlertInfo({ alertsEnabled: false, alertEmail: null, alertMessage: '' })

        const response = await agentApi.uploadResume(file, role, location)
        const session = response.jobReferenceId || response.session_id || response.sessionId || ''

        setSessionId(session)
        setStatus('Searching jobs...')
        persistSession({ sessionId: session, status: 'Searching jobs...', isProcessing: true, alertInfo: { alertsEnabled: false, alertEmail: null, alertMessage: '' } })

        startPolling(session)
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

  const stopAgent = useCallback(() => {
    clearPolling()

    setIsProcessing(false)
    setStatus('Stopped')
    persistSession({ status: 'Stopped', isProcessing: false })
  }, [clearPolling, persistSession])

  useEffect(() => {
    const stored = loadStoredSession()
    if (stored?.sessionId) {
      setSessionId(stored.sessionId)
      setJobs(stored.jobs || [])
      setStatus(stored.status || getStatusFromJobs(stored.jobs || [], false))
      setIsProcessing(Boolean(stored.isProcessing))
      setAlertInfo(stored.alertInfo || { alertsEnabled: false, alertEmail: null, alertMessage: '' })
      if (stored.status !== 'Stopped') {
        loadSession(stored.sessionId, stored.jobs || [])
      }
    }

    return () => {
      clearPolling()
    }
    // We intentionally only run this effect once on mount to restore any persisted session.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

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
      theme,
      startAgent,
      stopAgent,
      loadSession,
      clearSessionStorage,
      handleDownload,
      toggleTheme
    }),
    [sessionId, jobs, status, isProcessing, error, alertInfo, theme, startAgent, stopAgent, loadSession, clearSessionStorage, toggleTheme]
  )

  return (
    <JobAgentContext.Provider value={contextValue}>
      <div className={theme === 'dark' ? 'min-h-screen bg-gray-950 text-white' : 'min-h-screen bg-slate-50 text-slate-900'}>
        {children}
      </div>
    </JobAgentContext.Provider>
  )
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
