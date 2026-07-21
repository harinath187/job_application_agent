import { useEffect, useState } from 'react'
import { agentApi } from '../api/agentApi.js'
import { Button } from '../components/ui/Button.jsx'

export function ManageAlerts() {
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [usersLoading, setUsersLoading] = useState(false)
  const [activeUsers, setActiveUsers] = useState([])
  const [history, setHistory] = useState([])
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const loadActiveUsers = async () => {
    setUsersLoading(true)
    setError('')
    try {
      const res = await agentApi.getActiveAlertUsers()
      setActiveUsers(res.users || [])
    } catch (err) {
      setError('Failed to load active alert emails')
    } finally {
      setUsersLoading(false)
    }
  }

  useEffect(() => {
    loadActiveUsers()
  }, [])

  const lookupForEmail = async (targetEmail) => {
    setError('')
    setMessage('')
    setHistory([])
    if (!targetEmail || !targetEmail.includes('@')) {
      setError('Please enter a valid email address')
      return
    }
    setLoading(true)
    try {
      const res = await agentApi.getAlertHistory(targetEmail)
      setHistory(res.history || [])
      if ((res.history || []).length === 0) setMessage('No notifications found for this email')
    } catch (err) {
      setError('Lookup failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  const lookup = async () => {
    await lookupForEmail(email)
  }

  const disableAll = async (targetEmail = email) => {
    const normalizedEmail = targetEmail.trim()
    if (!normalizedEmail) {
      setError('Please enter or select an email address first')
      return
    }
    setError('')
    try {
      await agentApi.toggleAlerts({ email: normalizedEmail, active: false })
      setMessage(`All alerts have been disabled for ${normalizedEmail}`)
      await loadActiveUsers()
    } catch (err) {
      setError('Failed to disable alerts')
    }
  }

  const deleteAll = async (targetEmail = email) => {
    const normalizedEmail = targetEmail.trim()
    if (!normalizedEmail) {
      setError('Please enter or select an email address first')
      return
    }
    const ok = window.confirm(`Delete all alert data for ${targetEmail}? This cannot be undone.`)
    if (!ok) return
    setError('')
    try {
      await agentApi.unsubscribe(normalizedEmail)
      setHistory([])
      if (normalizedEmail === email.trim()) setEmail('')
      setMessage(`Alert data removed for ${normalizedEmail}.`)
      await loadActiveUsers()
    } catch (err) {
      setError('Failed to delete data')
    }
  }

  return (
    <main className="mx-auto max-w-4xl px-6 py-10">
      <h1 className="text-2xl font-semibold">Manage Alerts</h1>

      <section className="mt-6 rounded-xl border border-slate-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-6">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold">Active Alert Emails</h2>
            <p className="mt-1 text-sm text-slate-600 dark:text-gray-400">Emails with active job alert preferences.</p>
          </div>
          <Button onClick={loadActiveUsers} loading={usersLoading} variant="secondary">Refresh</Button>
        </div>

        <div className="mt-5 overflow-x-auto">
          {activeUsers.length === 0 ? (
            <div className="rounded-2xl border border-slate-200 dark:border-gray-800 bg-slate-50 dark:bg-gray-950 p-4 text-sm text-slate-600 dark:text-gray-400">
              {usersLoading ? 'Loading active alerts...' : 'No active alert emails found.'}
            </div>
          ) : (
            <table className="w-full table-auto text-sm">
              <thead>
                <tr className="text-left text-xs text-slate-500 dark:text-gray-400">
                  <th className="px-2 py-2">Email</th>
                  <th className="px-2 py-2">Preferences</th>
                  <th className="px-2 py-2">Created</th>
                  <th className="px-2 py-2">Actions</th>
                </tr>
              </thead>
              <tbody>
                {activeUsers.map((user) => (
                  <tr key={user.id} className="border-t border-slate-200 dark:border-gray-800">
                    <td className="px-2 py-3 align-top text-slate-900 dark:text-gray-100">{user.email}</td>
                    <td className="px-2 py-3 align-top">{user.active_preferences}</td>
                    <td className="px-2 py-3 align-top">{new Date(user.created_at).toLocaleString()}</td>
                    <td className="px-2 py-3 align-top">
                      <div className="flex flex-wrap gap-2">
                        <Button onClick={() => { setEmail(user.email); lookupForEmail(user.email) }} variant="secondary">History</Button>
                        <Button onClick={() => disableAll(user.email)} variant="secondary">Disable</Button>
                        <Button onClick={() => deleteAll(user.email)} variant="danger">Delete</Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </section>

      <section className="mt-6 rounded-xl border border-slate-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-6">
        <div className="flex gap-3">
          <input
            type="email"
            placeholder="Enter your email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="flex-1 rounded-2xl border border-slate-300 dark:border-gray-700 bg-white dark:bg-gray-950 px-4 py-2 text-sm text-slate-900 dark:text-white outline-none"
          />
          <Button onClick={lookup} loading={loading}>Lookup</Button>
        </div>
        {error && <div className="mt-4 text-sm text-red-600 dark:text-red-400">{error}</div>}
        {message && <div className="mt-4 text-sm text-emerald-600 dark:text-emerald-300">{message}</div>}
      </section>

      <section className="mt-6">
        {history.length > 0 && (
          <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4">
            <table className="w-full table-auto text-sm">
              <thead>
                <tr className="text-left text-xs text-slate-500 dark:text-gray-400">
                  <th className="px-2 py-2">Date</th>
                  <th className="px-2 py-2">Channel</th>
                  <th className="px-2 py-2">Job Title</th>
                  <th className="px-2 py-2">Company</th>
                  <th className="px-2 py-2">Status</th>
                </tr>
              </thead>
              <tbody>
                {history.map((row, idx) => (
                  <tr key={idx} className="border-t border-slate-200 dark:border-gray-800">
                    <td className="px-2 py-3 align-top">{new Date(row.sent_at).toLocaleString()}</td>
                    <td className="px-2 py-3 align-top">
                      <span className="inline-flex items-center rounded-full bg-slate-200 dark:bg-gray-800 text-slate-700 dark:text-gray-200 px-3 py-1 text-xs">
                        {row.channel === 'telegram' ? 'Telegram' : 'Email'}
                      </span>
                    </td>
                    <td className="px-2 py-3 align-top">{row.job_title}</td>
                    <td className="px-2 py-3 align-top">{row.company}</td>
                    <td className="px-2 py-3 align-top">
                      <span className={`inline-flex items-center rounded-full px-3 py-1 text-xs ${row.status === 'sent' ? 'bg-emerald-700 text-emerald-100' : 'bg-red-700 text-red-100'}`}>
                        {row.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="mt-6 flex gap-3">
          <Button onClick={() => disableAll()} variant="secondary" disabled={!email.trim()}>Disable All Alerts</Button>
          <Button onClick={() => deleteAll()} variant="danger" disabled={!email.trim()}>Delete All My Data</Button>
        </div>
      </section>
    </main>
  )
}

export default ManageAlerts
