import type { ReactNode } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import {
  ADMIN_ROLES,
  ANALYTICS_ROLES,
  CHAT_READ_ROLES,
  GRAPH_READ_ROLES,
  INGESTION_ROLES,
  REVIEW_ROLES,
  SAFETY_ROLES,
} from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { Icon } from './Icon'
import { Notifications } from './Notifications'

export function Layout() {
  const { user, logout } = useAuth()

  const navLink = ({ isActive }: { isActive: boolean }) =>
    `nav-link${isActive ? ' active' : ''}`

  const canIngest = user !== null && INGESTION_ROLES.includes(user.role)
  const canReview = user !== null && REVIEW_ROLES.includes(user.role)
  const canAdmin = user !== null && ADMIN_ROLES.includes(user.role)
  const canChat = user !== null && CHAT_READ_ROLES.includes(user.role)
  const canSafety = user !== null && SAFETY_ROLES.includes(user.role)
  const canGraph = user !== null && GRAPH_READ_ROLES.includes(user.role)

  const items: Array<[string, string, ReactNode]> = [
    ['/', 'Timeline', <Icon key="i" name="timeline" size={17} />],
    ['/decades', 'Decades', <Icon key="i" name="decades" size={17} />],
    ['/places', 'Places', <Icon key="i" name="places" size={17} />],
  ]
  if (canChat) items.push(['/chat', 'Chat', <Icon key="i" name="chat" size={17} />])
  items.push(['/people', 'People', <Icon key="i" name="people" size={17} />])
  if (canGraph) items.push(['/graph', 'Graph', <Icon key="i" name="graph" size={17} />])
  if (user && ANALYTICS_ROLES.includes(user.role))
    items.push(['/dashboard', 'Dashboard', <Icon key="i" name="dashboard" size={17} />])
  if (canIngest) items.push(['/sources', 'Sources', <Icon key="i" name="sources" size={17} />])
  if (canReview) items.push(['/review', 'Review', <Icon key="i" name="review" size={17} />])
  items.push(['/consent', 'Consent', <Icon key="i" name="consent" size={17} />])
  if (canSafety) items.push(['/safety', 'Safety', <Icon key="i" name="safety" size={17} />])
  if (canAdmin) items.push(['/admin', 'Admin', <Icon key="i" name="admin" size={17} />])

  return (
    <div className="app-shell">
      <header className="topbar">
        <NavLink to="/" className="brand" end>
          <span className="brand-mark">R</span>
          ReMind
        </NavLink>
        <nav className="nav">
          {items.map(([to, label, icon]) => (
            <NavLink key={to} to={to} className={navLink} end={to === '/'}>
              {icon}
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="account">
          <Notifications />
          <div className="account-id">
            <span className="account-name">{user?.full_name}</span>
            <span className="account-role">{user?.role}</span>
          </div>
          <button type="button" className="btn btn-ghost" onClick={logout}>
            Sign out
          </button>
        </div>
      </header>
      <main className="content">
        <Outlet />
      </main>
    </div>
  )
}
