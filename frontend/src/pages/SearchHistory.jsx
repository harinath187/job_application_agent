import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowRight, Clock3, FileText, MapPin, Trash2, User } from 'lucide-react'
import { agentApi } from '../api/agentApi.js'
import { Button } from '../components/ui/Button.jsx'

export function SearchHistory() {
  const navigate = useNavigate()
  const [history, setHistory] = useState([])
  const [selectedIds, setSelectedIds] = useState([])
  const [loading, setLoading] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    refreshHistory()
  }, [])

  const openHistory = (sessionId) => {
    navigate(`/dashboard?jobReferenceId=${sessionId}`)
  }

  const refreshHistory = async () => {
    setLoading(true)
    setError('')
    try {
      const data = await agentApi.getSearchHistory()
      setHistory(data.history || [])
      setSelectedIds((current) => current.filter((sessionId) => (data.history || []).some((item) => item.session_id === sessionId)))
    } catch {
      setError('Unable to load search history.')
    } finally {
      setLoading(false)
    }
  }

  const toggleSelected = (sessionId) => {
    setSelectedIds((current) =>
      current.includes(sessionId)
        ? current.filter((id) => id !== sessionId)
        : [...current, sessionId]
    )
  }

  const deleteOne = async (sessionId) => {
    const item = history.find((entry) => entry.session_id === sessionId)
    const label = item?.role ? `${item.role} in ${item.location}` : sessionId
    const ok = window.confirm(`Delete this search history item (${label})? This cannot be undone.`)
    if (!ok) return

    setDeleting(true)
    setError('')
    try {
      await agentApi.deleteSearchHistoryItem(sessionId)
      setHistory((current) => current.filter((item) => item.session_id !== sessionId))
      setSelectedIds((current) => current.filter((id) => id !== sessionId))
    } catch {
      setError('Unable to delete the selected search history item.')
    } finally {
      setDeleting(false)
    }
  }

  const deleteSelected = async () => {
    if (selectedIds.length === 0) return
    const ok = window.confirm(`Delete ${selectedIds.length} selected search history item${selectedIds.length === 1 ? '' : 's'}? This cannot be undone.`)
    if (!ok) return

    setDeleting(true)
    setError('')
    try {
      await agentApi.deleteSearchHistoryItems(selectedIds)
      setHistory((current) => current.filter((item) => !selectedIds.includes(item.session_id)))
      setSelectedIds([])
    } catch {
      setError('Unable to delete the selected search history items.')
    } finally {
      setDeleting(false)
    }
  }

  const selectAll = () => {
    setSelectedIds(history.map((item) => item.session_id))
  }

  const clearSelection = () => {
    setSelectedIds([])
  }

  return (
    <main className="mx-auto max-w-6xl px-6 py-10">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-sm uppercase tracking-[0.24em] text-indigo-300 dark:text-indigo-300">Search activity</p>
          <h1 className="mt-2 text-3xl font-semibold text-slate-900 dark:text-white">Search History</h1>
          <p className="mt-2 max-w-2xl text-sm text-slate-600 dark:text-gray-400">Reopen any prior search to restore the original resume, role, and location used for that job run.</p>
        </div>
        <Button onClick={() => navigate('/')} variant="secondary">Upload New Resume</Button>
      </div>

      {error && <div className="mt-6 rounded-2xl border border-red-700 bg-red-950 p-4 text-sm text-red-200">{error}</div>}

      <section className="mt-6 rounded-[2rem] border border-gray-800 bg-gray-900 p-6">
        {history.length > 0 && (
          <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
            <div className="text-sm text-slate-600 dark:text-gray-400">
              {selectedIds.length > 0 ? `${selectedIds.length} selected` : 'No items selected'}
            </div>
            <div className="flex flex-wrap gap-2">
              <Button onClick={selectAll} variant="secondary">Select All</Button>
              <Button onClick={clearSelection} variant="secondary" disabled={selectedIds.length === 0}>Clear Selection</Button>
              <Button onClick={deleteSelected} variant="danger" disabled={selectedIds.length === 0 || deleting}>
                Delete Selected
              </Button>
            </div>
          </div>
        )}
        {loading ? (
          <div className="py-12 text-center text-sm text-slate-600 dark:text-gray-400">Loading search history...</div>
        ) : history.length === 0 ? (
          <div className="rounded-3xl border border-dashed border-gray-700 bg-gray-950 p-10 text-center">
            <p className="text-lg font-medium text-slate-900 dark:text-white">No search history yet</p>
            <p className="mt-2 text-sm text-slate-600 dark:text-gray-400">Your past job searches will appear here after you upload a resume and start a search.</p>
          </div>
        ) : (
          <div className="space-y-4">
            {history.map((item) => (
              <div
                key={item.session_id}
                className="w-full rounded-3xl border border-gray-800 bg-gray-950 p-5 text-left transition hover:border-indigo-500 hover:bg-gray-900"
              >
                <div className="mb-4 flex items-center justify-between gap-3">
                  <label className="flex items-center gap-3 text-sm text-slate-700 dark:text-gray-300">
                    <input
                      type="checkbox"
                      checked={selectedIds.includes(item.session_id)}
                      onChange={() => toggleSelected(item.session_id)}
                      className="h-4 w-4 rounded border-gray-600 bg-gray-900 text-indigo-500 focus:ring-indigo-500"
                    />
                    Select item
                  </label>
                  <div className="flex items-center gap-2">
                    <Button onClick={() => deleteOne(item.session_id)} variant="danger" disabled={deleting}>
                      <Trash2 size={16} />
                      Delete
                    </Button>
                    <Button onClick={() => openHistory(item.session_id)} variant="secondary">
                      Open
                    </Button>
                  </div>
                </div>
                <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                  <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                    <div className="flex items-start gap-3">
                      <FileText size={18} className="mt-1 text-indigo-300" />
                      <div>
                        <p className="text-xs uppercase tracking-[0.2em] text-gray-500">Resume</p>
                        <p className="mt-1 text-sm text-slate-900 dark:text-white">{item.resume_name || item.resume_path || 'Unknown resume'}</p>
                      </div>
                    </div>
                    <div className="flex items-start gap-3">
                      <User size={18} className="mt-1 text-indigo-300" />
                      <div>
                        <p className="text-xs uppercase tracking-[0.2em] text-gray-500">Role</p>
                        <p className="mt-1 text-sm text-slate-900 dark:text-white">{item.role}</p>
                      </div>
                    </div>
                    <div className="flex items-start gap-3">
                      <MapPin size={18} className="mt-1 text-indigo-300" />
                      <div>
                        <p className="text-xs uppercase tracking-[0.2em] text-gray-500">Location</p>
                        <p className="mt-1 text-sm text-slate-900 dark:text-white">{item.location}</p>
                      </div>
                    </div>
                    <div className="flex items-start gap-3">
                      <Clock3 size={18} className="mt-1 text-indigo-300" />
                      <div>
                        <p className="text-xs uppercase tracking-[0.2em] text-gray-500">Search time</p>
                        <p className="mt-1 text-sm text-slate-900 dark:text-white">{new Date(item.created_at).toLocaleString()}</p>
                      </div>
                    </div>
                  </div>
                  <div className="inline-flex items-center gap-2 text-sm font-medium text-indigo-300">
                    View results
                    <ArrowRight size={16} />
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </main>
  )
}

export default SearchHistory
