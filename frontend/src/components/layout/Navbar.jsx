import { Briefcase, Github } from 'lucide-react'
import { Link } from 'react-router-dom'

export function Navbar() {
  return (
    <header className="sticky top-0 z-50 border-b border-gray-800 bg-gray-900/95 backdrop-blur-xl">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-6 py-4">
        <Link to="/" className="inline-flex items-center gap-3 text-white">
          <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-indigo-600 text-white shadow-lg shadow-indigo-500/20">
            <Briefcase size={20} />
          </div>
          <span className="text-lg font-semibold tracking-tight text-indigo-300">JobAgent</span>
        </Link>
        <a href="#" className="inline-flex items-center gap-2 rounded-lg bg-gray-800 px-4 py-2 text-sm font-medium text-gray-200 transition hover:bg-gray-700">
          <Github size={18} />
          GitHub
        </a>
      </div>
    </header>
  )
}
