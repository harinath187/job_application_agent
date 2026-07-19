import axios from 'axios'
import { API_BASE_URL, API_BASE_PATH } from '../utils/constants.js'

const baseURL = API_BASE_URL ? `${API_BASE_URL.replace(/\/$/, '')}${API_BASE_PATH}` : API_BASE_PATH

const http = axios.create({
  baseURL,
  headers: {
    'Content-Type': 'application/json'
  }
})

async function uploadResume(file, role, location, experience = '') {
  try {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('role', role)
    formData.append('location', location)
    if (experience && experience.trim()) {
      formData.append('experience', experience.trim())
    }

    const response = await http.post('/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })

    return response.data
  } catch (error) {
    console.error('uploadResume error', error)
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

async function submitExperienceLevel(sessionId, experienceLevel) {
  try {
    const response = await http.post(`/sessions/${sessionId}/experience`, {
      experience_level: experienceLevel
    })
    return response.data
  } catch (error) {
    console.error('submitExperienceLevel error', error)
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
  getJobStatus,
  submitExperienceLevel,
  getSearchHistory,
  getSearchHistoryItem,
  deleteSearchHistoryItem,
  deleteSearchHistoryItems,
  getJobDetail,
  downloadFile,
  subscribeToAlerts,
  getActiveAlertUsers,
  getAlertHistory,
  toggleAlerts,
  unsubscribe
}
