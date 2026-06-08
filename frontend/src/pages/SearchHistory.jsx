import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowRight, Clock3, FileText, MapPin, User } from 'lucide-react'
import { agentApi } from '../api/agentApi.js'
import { Button } from '../components/ui/Button.jsx'

export function SearchHistory() {
  const navigate = useNavigate()
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    const load = async () => {
      setLoading(true)
      setError('')
      try {
        const data = await agentApi.getSearchHistory()
        setHistory(data.history || [])
      } catch {
        setError('Unable to load search history.')
      } finally {
        setLoading(false)
      }
    }

    load()
  }, [])

  const openHistory = (sessionId) => {
    navigate(`/dashboard?jobReferenceId=${sessionId}`)
  }

  return (
    <main className="mx-auto max-w-6xl px-6 py-10">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-sm uppercase tracking-[0.24em] text-indigo-300">Search activity</p>
          <h1 className="mt-2 text-3xl font-semibold text-white">Search History</h1>
          <p className="mt-2 max-w-2xl text-sm text-gray-400">Reopen any prior search to restore the original resume, role, and location used for that job run.</p>
        </div>
        <Button onClick={() => navigate('/')} variant="secondary">Upload New Resume</Button>
      </div>

      {error && <div className="mt-6 rounded-2xl border border-red-700 bg-red-950 p-4 text-sm text-red-200">{error}</div>}

      <section className="mt-6 rounded-[2rem] border border-gray-800 bg-gray-900 p-6">
        {loading ? (
          <div className="py-12 text-center text-sm text-gray-400">Loading search history...</div>
        ) : history.length === 0 ? (
          <div className="rounded-3xl border border-dashed border-gray-700 bg-gray-950 p-10 text-center">
            <p className="text-lg font-medium text-white">No search history yet</p>
            <p className="mt-2 text-sm text-gray-400">Your past job searches will appear here after you upload a resume and start a search.</p>
          </div>
        ) : (
          <div className="space-y-4">
            {history.map((item) => (
              <button
                key={item.session_id}
                onClick={() => openHistory(item.session_id)}
                className="w-full rounded-3xl border border-gray-800 bg-gray-950 p-5 text-left transition hover:border-indigo-500 hover:bg-gray-900"
              >
                <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                  <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                    <div className="flex items-start gap-3">
                      <FileText size={18} className="mt-1 text-indigo-300" />
                      <div>
                        <p className="text-xs uppercase tracking-[0.2em] text-gray-500">Resume</p>
                        <p className="mt-1 text-sm text-white">{item.resume_name || item.resume_path || 'Unknown resume'}</p>
                      </div>
                    </div>
                    <div className="flex items-start gap-3">
                      <User size={18} className="mt-1 text-indigo-300" />
                      <div>
                        <p className="text-xs uppercase tracking-[0.2em] text-gray-500">Role</p>
                        <p className="mt-1 text-sm text-white">{item.role}</p>
                      </div>
                    </div>
                    <div className="flex items-start gap-3">
                      <MapPin size={18} className="mt-1 text-indigo-300" />
                      <div>
                        <p className="text-xs uppercase tracking-[0.2em] text-gray-500">Location</p>
                        <p className="mt-1 text-sm text-white">{item.location}</p>
                      </div>
                    </div>
                    <div className="flex items-start gap-3">
                      <Clock3 size={18} className="mt-1 text-indigo-300" />
                      <div>
                        <p className="text-xs uppercase tracking-[0.2em] text-gray-500">Search time</p>
                        <p className="mt-1 text-sm text-white">{new Date(item.created_at).toLocaleString()}</p>
                      </div>
                    </div>
                  </div>
                  <div className="inline-flex items-center gap-2 text-sm font-medium text-indigo-300">
                    View results
                    <ArrowRight size={16} />
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}
      </section>
    </main>
  )
}

export default SearchHistory
