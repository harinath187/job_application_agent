import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import PropTypes from 'prop-types'
import { agentApi } from '../api/agentApi.js'
import { API_BASE_URL, API_BASE_PATH, POLLING_INTERVAL_MS } from '../utils/constants.js'

const JobAgentContext = createContext(null)
const STORAGE_KEY = 'jobAgentSession'
const THEME_STORAGE_KEY = 'jobAgentTheme'

function getInitialTheme() {
  if (typeof window === 'undefined') return 'dark'

  try {
    const storedTheme = localStorage.getItem(THEME_STORAGE_KEY)
    if (storedTheme === 'light' || storedTheme === 'dark') {
      return storedTheme
    }
  } catch {
    // ignore storage errors
  }

  return window.matchMedia?.('(prefers-color-scheme: light)').matches ? 'light' : 'dark'
}

function getStatusFromJobs(jobs, isProcessing) {
  if (!isProcessing && jobs.length === 0) return 'Waiting for upload'
  if (jobs.some((job) => job.status === 'failed')) return 'Processing failed'
  if (jobs.length === 0) return 'Parsing resume...'
  const completeCount = jobs.filter((job) => job.resume_path && job.cover_letter_path).length
  if (completeCount === jobs.length) return 'Complete!'
  if (jobs.some((job) => job.resume_path || job.cover_letter_path)) return 'Preparing application files...'
  return 'Searching jobs...'
}

function isTerminalStatus(status) {
  return status === 'Complete!' || status === 'Processing failed' || status === 'Stopped'
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

function buildStreamUrl(sessionId) {
  const base = API_BASE_URL ? `${API_BASE_URL.replace(/\/$/, '')}${API_BASE_PATH}` : API_BASE_PATH
  return `${base}/stream/${sessionId}`
}

export function JobAgentProvider({ children }) {
  const [sessionId, setSessionId] = useState('')
  const [jobs, setJobs] = useState([])
  const [status, setStatus] = useState('Waiting for upload')
  const [isProcessing, setIsProcessing] = useState(false)
  const [error, setError] = useState('')
  const [alertInfo, setAlertInfo] = useState({ alertsEnabled: false, alertEmail: null, alertMessage: '' })
  const [statusMessage, setStatusMessage] = useState('Waiting for upload')
  const [isComplete, setIsComplete] = useState(false)
  const [theme, setTheme] = useState(getInitialTheme)
  const intervalRef = useRef(null)
  const eventSourceRef = useRef(null)
  const fetchInFlightRef = useRef(false)
  const sessionStateRef = useRef({
    sessionId: '',
    jobs: [],
    status: 'Waiting for upload',
    isProcessing: false,
    alertInfo: { alertsEnabled: false, alertEmail: null, alertMessage: '' },
    statusMessage: 'Waiting for upload',
    isComplete: false
  })

  useEffect(() => {
    sessionStateRef.current = {
      sessionId,
      jobs,
      status,
      isProcessing,
      alertInfo,
      statusMessage,
      isComplete
    }
  }, [sessionId, jobs, status, isProcessing, alertInfo, statusMessage, isComplete])

  useEffect(() => {
    const root = document.documentElement
    root.classList.toggle('light', theme === 'light')
    root.classList.toggle('dark', theme === 'dark')

    try {
      localStorage.setItem(THEME_STORAGE_KEY, theme)
    } catch {
      // ignore storage errors
    }
  }, [theme])

  const persistSession = useCallback(
    (nextState) => {
      const currentState = loadStoredSession() || sessionStateRef.current
      saveStoredSession({
        sessionId: nextState.sessionId ?? currentState.sessionId,
        jobs: nextState.jobs ?? currentState.jobs,
        status: nextState.status ?? currentState.status,
        isProcessing: nextState.isProcessing ?? currentState.isProcessing,
        alertInfo: nextState.alertInfo ?? currentState.alertInfo,
        statusMessage: nextState.statusMessage ?? currentState.statusMessage,
        isComplete: nextState.isComplete ?? currentState.isComplete
      })
    },
    []
  )

  const clearSessionStorage = useCallback(() => {
    clearStoredSession()
  }, [])

  const toggleTheme = useCallback(() => {
    setTheme((currentTheme) => (currentTheme === 'dark' ? 'light' : 'dark'))
  }, [])

  const closeStream = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }
  }, [])

  const clearPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
  }, [])

  const fetchJobs = useCallback(
    async (currentSessionId) => {
      if (!currentSessionId) return null
      if (fetchInFlightRef.current) return null
      fetchInFlightRef.current = true
      try {
        const data = await agentApi.getJobStatus(currentSessionId)
        const jobsData = data.jobs || []
        const nextAlertInfo = {
          alertsEnabled: Boolean(data.alerts_enabled),
          alertEmail: data.alert_email || null,
          alertMessage: data.alert_message || ''
        }
        const nextStatus = getStatusFromJobs(jobsData, Boolean(data.status === 'processing' || jobsData.length === 0))
        const nextComplete = nextStatus === 'Complete!'
        const nextProcessing = !isTerminalStatus(nextStatus)

        setJobs(jobsData)
        setStatus(nextStatus)
        setIsProcessing(nextProcessing)
        setError('')
        setAlertInfo(nextAlertInfo)
        setIsComplete(nextComplete)
        persistSession({
          sessionId: currentSessionId,
          jobs: jobsData,
          status: nextStatus,
          isProcessing: nextProcessing,
          alertInfo: nextAlertInfo,
          statusMessage: loadStoredSession()?.statusMessage ?? nextStatus,
          isComplete: nextComplete
        })
        if (!nextProcessing) {
          clearPolling()
        }
        return data
      } catch (err) {
        console.error('fetchJobs error', err)
        setError('Unable to fetch job updates.')
        return null
      } finally {
        fetchInFlightRef.current = false
      }
    },
    [clearPolling, persistSession]
  )

  const startStream = useCallback(
    (currentSessionId) => {
      closeStream()
      const es = new EventSource(buildStreamUrl(currentSessionId))
      eventSourceRef.current = es

      es.onmessage = async (event) => {
        try {
          const { msg, done } = JSON.parse(event.data)
          setStatusMessage(msg)
          setStatus(msg)
          setIsProcessing(!done)
          setError('')
          setIsComplete(Boolean(done))
          persistSession({ sessionId: currentSessionId, status: msg, statusMessage: msg, isProcessing: !done, isComplete: Boolean(done) })

          if (done) {
            closeStream()
            await fetchJobs(currentSessionId)
            setStatusMessage(msg)
            setStatus(msg)
          }
        } catch (parseError) {
          console.error('stream parse error', parseError)
        }
      }

      es.onerror = () => {
        closeStream()
        const message = 'Connection lost - check backend logs.'
        setStatusMessage(message)
        setStatus(message)
        setError(message)
        setIsProcessing(false)
        clearPolling()
        persistSession({ status: message, statusMessage: message, isProcessing: false })
      }
    },
    [clearPolling, closeStream, fetchJobs, persistSession]
  )

  const loadSession = useCallback(
    async (targetSessionId, cachedJobs = []) => {
      if (!targetSessionId) return
      setSessionId(targetSessionId)
      if (cachedJobs.length > 0) {
        const initialStatus = getStatusFromJobs(cachedJobs, true)
        const initialProcessing = !isTerminalStatus(initialStatus)
        setJobs(cachedJobs)
        setStatus(initialStatus)
        setStatusMessage(initialStatus)
        setIsProcessing(initialProcessing)
        persistSession({ sessionId: targetSessionId, jobs: cachedJobs, status: initialStatus, statusMessage: initialStatus, isProcessing: initialProcessing })
      }
      clearPolling()
      if (cachedJobs.length > 0 && isTerminalStatus(getStatusFromJobs(cachedJobs, true))) {
        return
      }
      intervalRef.current = setInterval(() => {
        fetchJobs(targetSessionId)
      }, POLLING_INTERVAL_MS)
      await fetchJobs(targetSessionId)
    },
    [clearPolling, fetchJobs, persistSession]
  )

  const runAgent = useCallback(
    async ({ file = null, resumeId = '', role, location, experience }) => {
      try {
        setError('')
        setIsProcessing(true)
        const initialStatus = resumeId ? 'Loading saved resume...' : 'Parsing resume...'
        setStatus(initialStatus)
        setStatusMessage(initialStatus)
        setIsComplete(false)
        setAlertInfo({ alertsEnabled: false, alertEmail: null, alertMessage: '' })

        const response = await agentApi.uploadResume({ file, resumeId, role, location, experience })
        const session = response.jobReferenceId || response.session_id || response.sessionId || ''

        setSessionId(session)
        const searchingMessage = 'Searching LinkedIn, Indeed and Naukri...'
        setStatus('Searching jobs...')
        setStatusMessage(searchingMessage)
        persistSession({
          sessionId: session,
          status: 'Searching jobs...',
          statusMessage: searchingMessage,
          isProcessing: true,
          isComplete: false,
          alertInfo: { alertsEnabled: false, alertEmail: null, alertMessage: '' }
        })

        startStream(session)
        return session
      } catch (err) {
        console.error('startAgent error', err)
        const backendMessage = err?.response?.data?.detail
        setError(typeof backendMessage === 'string' && backendMessage.trim() ? backendMessage : 'Failed to upload resume. Please try again.')
        setIsProcessing(false)
        setStatus('Upload failed')
        setStatusMessage('Upload failed')
        persistSession({ status: 'Upload failed', statusMessage: 'Upload failed', isProcessing: false, isComplete: false })
        throw err
      }
    },
    [persistSession, startStream]
  )

  const startAgent = useCallback(
    async ({ file, role, location, experience }) => runAgent({ file, role, location, experience }),
    [runAgent]
  )

  const runWithSavedResume = useCallback(
    async ({ resumeId, role, location, experience }) => runAgent({ resumeId, role, location, experience }),
    [runAgent]
  )

  const stopAgent = useCallback(() => {
    closeStream()
    clearPolling()
    fetchInFlightRef.current = false
    setIsProcessing(false)
    setStatus('Stopped')
    setStatusMessage('Stopped')
    persistSession({ status: 'Stopped', statusMessage: 'Stopped', isProcessing: false, isComplete: false })
  }, [clearPolling, closeStream, persistSession])
  useEffect(() => {
    const stored = loadStoredSession()
    if (stored?.sessionId) {
      setSessionId(stored.sessionId)
      setJobs(stored.jobs || [])
      setStatus(stored.status || getStatusFromJobs(stored.jobs || [], false))
      setStatusMessage(stored.statusMessage || stored.status || getStatusFromJobs(stored.jobs || [], false))
      setIsProcessing(Boolean(stored.isProcessing))
      setIsComplete(Boolean(stored.isComplete))
      setAlertInfo(stored.alertInfo || { alertsEnabled: false, alertEmail: null, alertMessage: '' })
      loadSession(stored.sessionId, stored.jobs || [])
    }

    return () => {
      clearPolling()
      closeStream()
    }
  }, [clearPolling, closeStream, loadSession])

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
      statusMessage,
      isComplete,
      isProcessing,
      error,
      alertInfo,
      theme,
      toggleTheme,
      startAgent,
      runWithSavedResume,
      stopAgent,
      loadSession,
      clearSessionStorage,
      handleDownload
    }),
    [sessionId, jobs, status, statusMessage, isComplete, isProcessing, error, alertInfo, theme, startAgent, runWithSavedResume, stopAgent, loadSession, clearSessionStorage, toggleTheme]
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
