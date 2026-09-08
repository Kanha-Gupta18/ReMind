import { useEffect } from 'react'
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
import { api, PATIENT_PROFILE_UPDATED_EVENT } from '../api/client'
import { useApiData } from '../api/useApiData'
import { Icon } from './Icon'
import { Notifications } from './Notifications'

export function Layout() {
  const { user, selectedPatientId, selectPatient, logout } = useAuth()
  const patients = useApiData(() => api.availablePatients(), [user?.id])

  useEffect(() => {
    const refreshPatientNames = () => patients.reload()
    window.addEventListener(PATIENT_PROFILE_UPDATED_EVENT, refreshPatientNames)
    return () => window.removeEventListener(PATIENT_PROFILE_UPDATED_EVENT, refreshPatientNames)
  }, [patients.reload])

  const navLink = ({ isActive }: { isActive: boolean }) =>
    `nav-link${isActive ? ' active' : ''}`

  const canIngest = user !== null && INGESTION_ROLES.includes(user.role)
  const canReview = user !== null && REVIEW_ROLES.includes(user.role)
  const canAdmin = user !== null && ADMIN_ROLES.includes(user.role)
  const canChat = user !== null && CHAT_READ_ROLES.includes(user.role)
  const canSafety = user !== null && SAFETY_ROLES.includes(user.role)
  const canGraph = user !== null && GRAPH_READ_ROLES.includes(user.role)
  const selectedPatient = patients.data?.items.find((patient) => patient.id === selectedPatientId)
  const accountName = user?.role === 'patient'
    ? selectedPatient?.preferred_name ?? user.full_name
    : user?.full_name

  const items: Array<[string, string, ReactNode]> = []
  if (!canAdmin) {
    items.push(
      ['/', 'Timeline', <Icon key="i" name="timeline" size={17} />],
      ['/decades', 'Decades', <Icon key="i" name="decades" size={17} />],
      ['/places', 'Places', <Icon key="i" name="places" size={17} />],
      ['/profile', 'Profile', <Icon key="i" name="people" size={17} />],
    )
    if (user?.role === 'patient') items.push(['/onboarding', 'Setup', <Icon key="i" name="consent" size={17} />])
  }
  if (canChat) items.push(['/chat', 'Chat', <Icon key="i" name="chat" size={17} />])
  if (!canAdmin) items.push(['/people', 'People', <Icon key="i" name="people" size={17} />])
  if (canGraph) items.push(['/graph', 'Graph', <Icon key="i" name="graph" size={17} />])
  if (user && ANALYTICS_ROLES.includes(user.role))
    items.push(['/dashboard', 'Dashboard', <Icon key="i" name="dashboard" size={17} />])
  if (canIngest) items.push(['/sources', 'Sources', <Icon key="i" name="sources" size={17} />])
  if (canReview) items.push(['/review', 'Review', <Icon key="i" name="review" size={17} />])
  if (!canAdmin) items.push(['/consent', 'Consent', <Icon key="i" name="consent" size={17} />])
  if (canSafety) items.push(['/safety', 'Safety', <Icon key="i" name="safety" size={17} />])
  if (canAdmin) items.push(['/admin', 'Admin', <Icon key="i" name="admin" size={17} />])

  return (
    <div className="app-shell">
      <header className="topbar">
        <NavLink to={canAdmin ? '/admin' : '/'} className="brand" end>
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
          {patients.data && patients.data.count > 1 && (
            <label className="patient-switcher">
              <span>Patient</span>
              <select
                value={selectedPatientId ?? ''}
                onChange={(event) => selectPatient(event.target.value)}
                aria-label="Choose patient"
              >
                <option value="" disabled>Choose a patient</option>
                {patients.data.items.map((patient) => (
                  <option key={patient.id} value={patient.id}>{patient.preferred_name}</option>
                ))}
              </select>
            </label>
          )}
          <Notifications />
          <div className="account-id">
            <span className="account-name">{accountName}</span>
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
