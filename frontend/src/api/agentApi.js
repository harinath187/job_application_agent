import axios from 'axios'
import { API_BASE_URL, API_BASE_PATH } from '../utils/constants.js'

const baseURL = API_BASE_URL ? `${API_BASE_URL.replace(/\/$/, '')}${API_BASE_PATH}` : API_BASE_PATH

const http = axios.create({
  baseURL,
  headers: {
    'Content-Type': 'application/json'
  }
})

async function uploadResume(file, role, location) {
  try {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('role', role)
    formData.append('location', location)

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

export const agentApi = {
  uploadResume,
  getJobStatus,
  getJobDetail,
  downloadFile
}
