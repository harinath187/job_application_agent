import axios from 'axios'
import { API_BASE_URL, API_BASE_PATH } from '../utils/constants.js'

const baseURL = API_BASE_URL ? `${API_BASE_URL.replace(/\/$/, '')}${API_BASE_PATH}` : API_BASE_PATH

const http = axios.create({
  baseURL,
  headers: {
    Accept: 'application/json'
  }
})

async function uploadResume({ file = null, resumeId = '', role, location, experience = '' }) {
  try {
    const formData = new FormData()
    if (file) {
      formData.append('file', file)
    }
    if (resumeId) {
      formData.append('resume_id', resumeId)
    }
    formData.append('role', role)
    formData.append('location', location)
    if (experience && experience.trim()) {
      formData.append('experience', experience.trim())
    }

    const response = await http.post('/upload', formData, {
      headers: {}
    })

    return response.data
  } catch (error) {
    console.error('uploadResume error', error)
    throw error
  }
}

async function saveResume(file, label = '', extractedRole = '', extractedLocation = '') {
  try {
    const formData = new FormData()
    formData.append('file', file)
    if (label) formData.append('label', label)
    if (extractedRole) formData.append('extracted_role', extractedRole)
    if (extractedLocation) formData.append('extracted_location', extractedLocation)

    const response = await http.post('/resumes', formData, {
      headers: {}
    })
    return response.data
  } catch (error) {
    console.error('saveResume error', error)
    throw error
  }
}

async function getJobStatus(sessionId) {
  try {
    const response = await http.get('/jobs', {
      params: {
        session_id: sessionId
      }
    })
    return response.data
  } catch (error) {
    console.error('getJobStatus error', error)
    throw error
  }
}

async function getJobDetail(jobId) {
  try {
    const response = await http.get(`/jobs/${jobId}`)
    return response.data
  } catch (error) {
    console.error('getJobDetail error', error)
    throw error
  }
}

async function getJobSkillsGap(jobId) {
  try {
    const response = await http.get(`/jobs/${jobId}/skills-gap`)
    return response.data
  } catch (error) {
    console.error('getJobSkillsGap error', error)
    throw error
  }
}

async function getJobInterviewPrep(jobId) {
  try {
    const response = await http.get(`/jobs/${jobId}/interview-prep`)
    return response.data
  } catch (error) {
    console.error('getJobInterviewPrep error', error)
    throw error
  }
}

async function regenerateJobInterviewPrep(jobId) {
  try {
    const response = await http.post(`/jobs/${jobId}/interview-prep/regenerate`)
    return response.data
  } catch (error) {
    console.error('regenerateJobInterviewPrep error', error)
    throw error
  }
}

async function downloadFile(filename) {
  try {
    const response = await http.get('/download', {
      params: {
        file: filename
      },
      responseType: 'blob'
    })

    return response.data
  } catch (error) {
    console.error('downloadFile error', error)
    throw error
  }
}

async function subscribeToAlerts(payload) {
  try {
    const response = await http.post('/alerts/subscribe', payload)
    return response.data
  } catch (error) {
    console.error('subscribeToAlerts error', error)
    throw error
  }
}

async function getAlertHistory(email) {
  try {
    const response = await http.get('/alerts/history', { params: { email } })
    return response.data
  } catch (error) {
    console.error('getAlertHistory error', error)
    throw error
  }
}

async function getSearchHistory() {
  try {
    const response = await http.get('/search-history')
    return response.data
  } catch (error) {
    console.error('getSearchHistory error', error)
    throw error
  }
}

async function getSearchHistoryItem(sessionId) {
  try {
    const response = await http.get(`/search-history/${sessionId}`)
    return response.data
  } catch (error) {
    console.error('getSearchHistoryItem error', error)
    throw error
  }
}

async function listResumes() {
  try {
    const response = await http.get('/resumes')
    return response.data
  } catch (error) {
    console.error('listResumes error', error)
    throw error
  }
}

async function renameResume(resumeId, label) {
  try {
    const formData = new FormData()
    formData.append('label', label)
    const response = await http.patch(`/resumes/${resumeId}`, formData, {
      headers: {}
    })
    return response.data
  } catch (error) {
    console.error('renameResume error', error)
    throw error
  }
}

async function deleteResume(resumeId) {
  try {
    const response = await http.delete(`/resumes/${resumeId}`)
    return response.data
  } catch (error) {
    console.error('deleteResume error', error)
    throw error
  }
}

async function updateJobStatus(jobId, status) {
  try {
    const response = await http.patch(`/jobs/${jobId}/status`, { status })
    return response.data
  } catch (error) {
    console.error('updateJobStatus error', error)
    throw error
  }
}

async function deleteSearchHistoryItem(sessionId) {
  try {
    const response = await http.delete(`/search-history/${sessionId}`)
    return response.data
  } catch (error) {
    console.error('deleteSearchHistoryItem error', error)
    throw error
  }
}

async function deleteSearchHistoryItems(sessionIds) {
  try {
    const response = await http.delete('/search-history', {
      params: { session_ids: sessionIds }
    })
    return response.data
  } catch (error) {
    console.error('deleteSearchHistoryItems error', error)
    throw error
  }
}

async function getActiveAlertUsers() {
  try {
    const response = await http.get('/alerts/active-users')
    return response.data
  } catch (error) {
    console.error('getActiveAlertUsers error', error)
    throw error
  }
}

async function toggleAlerts(payload) {
  try {
    const response = await http.patch('/alerts/toggle', payload)
    return response.data
  } catch (error) {
    console.error('toggleAlerts error', error)
    throw error
  }
}

async function unsubscribe(email) {
  try {
    const response = await http.delete('/alerts/unsubscribe', { params: { email } })
    return response.data
  } catch (error) {
    console.error('unsubscribe error', error)
    throw error
  }
}

export const agentApi = {
  uploadResume,
  saveResume,
  getJobStatus,
  listResumes,
  renameResume,
  deleteResume,
  getSearchHistory,
  getSearchHistoryItem,
  deleteSearchHistoryItem,
  deleteSearchHistoryItems,
  getJobDetail,
  getJobSkillsGap,
  getJobInterviewPrep,
  regenerateJobInterviewPrep,
  updateJobStatus,
  downloadFile,
  subscribeToAlerts,
  getActiveAlertUsers,
  getAlertHistory,
  toggleAlerts,
  unsubscribe
}
