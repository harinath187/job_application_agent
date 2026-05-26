import axios from 'axios'
import { API_BASE_URL } from '../utils/constants.js'

const http = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json'
  }
})

async function uploadResume(file) {
  try {
    const formData = new FormData()
    formData.append('file', file)

    const response = await axios.post(`${API_BASE_URL}/api/upload`, formData, {
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
    const response = await http.get('/api/jobs', {
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
    const response = await http.get(`/api/jobs/${jobId}`)
    return response.data
  } catch (error) {
    console.error('getJobDetail error', error)
    throw error
  }
}

async function downloadFile(filename) {
  try {
    const response = await axios.get(`${API_BASE_URL}/api/download`, {
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
