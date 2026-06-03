import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Navbar } from './components/layout/Navbar.jsx'
import { Home } from './pages/Home.jsx'
import { Dashboard } from './pages/Dashboard.jsx'
import { JobDetail } from './pages/JobDetail.jsx'
import { ManageAlerts } from './pages/ManageAlerts.jsx'
import { JobAgentProvider } from './hooks/useJobAgent.jsx'

export function App() {
  return (
    <JobAgentProvider>
      <BrowserRouter>
        <div className="min-h-screen bg-gray-950 text-white">
          <Navbar />
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/jobs/:jobId" element={<JobDetail />} />
            <Route path="/manage-alerts" element={<ManageAlerts />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </div>
      </BrowserRouter>
    </JobAgentProvider>
  )
}
