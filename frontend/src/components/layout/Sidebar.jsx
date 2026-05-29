import { LayoutDashboard, Upload, Settings2 } from 'lucide-react'
import { NavLink } from 'react-router-dom'

const links = [
  { label: 'Dashboard', to: '/dashboard', icon: LayoutDashboard },
  { label: 'Upload New', to: '/', icon: Upload },
  { label: 'Settings', to: '#', icon: Settings2 }
]

export function Sidebar() {
  return (
    <aside className="hidden h-[calc(100vh-64px)] w-64 flex-col gap-4 border-r border-gray-800 bg-gray-950 p-6 md:flex">
      <nav className="flex flex-col gap-2">
        {links.map((item) => {
          const Icon = item.icon
          return (
            <NavLink
              key={item.label}
              to={item.to}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-2xl px-4 py-3 text-sm font-medium transition ${
                  isActive ? 'bg-indigo-600 text-white' : 'text-gray-300 hover:bg-gray-900'
                }`
              }
            >
              <Icon size={18} />
              {item.label}
            </NavLink>
          )
        })}
      </nav>
    </aside>
  )
}
