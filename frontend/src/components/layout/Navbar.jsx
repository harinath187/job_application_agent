import { Briefcase, ChevronLeft, ChevronRight, Moon, Sun } from 'lucide-react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useJobAgent } from '../../hooks/useJobAgent.jsx'
import { Button } from '../ui/Button.jsx'

export function Navbar() {
  const { sessionId, theme, toggleTheme } = useJobAgent()
  const navigate = useNavigate()
  const location = useLocation()
  const showBackButton = location.pathname === '/search-history' || location.pathname === '/manage-alerts'

  return (
    <header className="sticky top-0 z-50 border-b border-gray-200 bg-white/90 text-slate-900 backdrop-blur-xl transition-colors duration-200 dark:border-gray-800 dark:bg-gray-900/95 dark:text-white">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-6 py-4">
        <Link to="/" className="inline-flex items-center gap-3 text-slate-900 dark:text-white">
          <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-indigo-600 text-white shadow-lg shadow-indigo-500/20">
            <Briefcase size={20} />
          </div>
          <span className="text-lg font-semibold tracking-tight text-indigo-600 dark:text-indigo-300">JobAgent</span>
        </Link>
        <nav className="flex items-center gap-3">
          {showBackButton && (
            <Button type="button" variant="ghost" onClick={() => navigate('/')} icon={<ChevronLeft size={16} />}>
              Back
            </Button>
          )}
          {/* <Button
            type="button"
            variant="ghost"
            onClick={toggleTheme}
            icon={theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
          >
            {theme === 'dark' ? 'Light' : 'Dark'}
          </Button> */}
          {/* {sessionId && (
            <Link to="/dashboard" className="rounded-lg px-4 py-2 text-sm font-medium text-slate-700 hover:text-slate-900 dark:text-gray-200 dark:hover:text-white">
              Return to dashboard
            </Link>
          )} */}
          <Link to="/search-history" className="rounded-lg px-4 py-2 text-sm font-medium text-slate-700 hover:text-slate-900 dark:text-gray-200 dark:hover:text-white">
            Search History
          </Link>
          <Link to="/manage-alerts" className="rounded-lg px-4 py-2 text-sm font-medium text-slate-700 hover:text-slate-900 dark:text-gray-200 dark:hover:text-white">Manage Alerts</Link>
        </nav>
      </div>
    </header>
  )
}
