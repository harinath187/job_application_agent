import React from 'react'
import ReactDOM from 'react-dom/client'
import { App } from './App.jsx'
import './index.css'

const storedTheme = localStorage.getItem('jobAgentTheme')
const preferredTheme = storedTheme === 'light' || storedTheme === 'dark'
  ? storedTheme
  : window.matchMedia?.('(prefers-color-scheme: light)').matches
    ? 'light'
    : 'dark'

document.documentElement.classList.toggle('light', preferredTheme === 'light')
document.documentElement.classList.toggle('dark', preferredTheme === 'dark')

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
