import { useState } from 'react'
import type { FormEvent } from 'react'
import { Navigate } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import type { AdminUser } from '../api/types'
import { useApiData } from '../api/useApiData'
import { useAuth } from '../auth/AuthContext'
import { Badge } from '../components/Badge'
import { Icon } from '../components/Icon'

const ROLES = [
  'patient',
  'family_contributor',
  'family_reviewer',
  'caregiver',
  'guardian',
  'clinician',
  'administrator',
]
const PATIENTLESS_ROLES = ['patient', 'administrator']

export function Admin() {
  const { user } = useAuth()
  const stats = useApiData(() => api.adminStats())
  const users = useApiData(() => api.adminUsers())
  const [notice, setNotice] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<string | null>(null)

  if (user && user.role !== 'administrator') {
    return <Navigate to="/" replace />
  }

  async function act(id: string | null, fn: () => Promise<unknown>, message: string) {
    setBusyId(id)
    setActionError(null)
    setNotice(null)
    try {
      await fn()
      setNotice(message)
      users.reload()
      stats.reload()
    } catch (e) {
      setActionError(e instanceof ApiError ? e.message : 'Request failed')
    } finally {
      setBusyId(null)
    }
  }

  return (
    <section>
      <div className="page-head">
        <h1>Admin</h1>
      </div>
      <p className="muted">User directory and account lifecycle (administrator only).</p>

      {notice && <p className="success">{notice}</p>}
      {actionError && <p className="error">{actionError}</p>}

      {stats.loading && <p>Loading stats…</p>}
      {stats.error && <p className="error">{stats.error}</p>}
      {stats.data && (
        <div className="stat-grid">
          <div className="stat">
            <strong>{stats.data.total_users}</strong>
            <span>users</span>
          </div>
          <div className="stat">
            <strong>{stats.data.total_sources}</strong>
            <span>sources</span>
          </div>
          <div className="stat">
            <strong>{stats.data.total_memories}</strong>
            <span>memories</span>
          </div>
          {Object.entries(stats.data.users_by_role).map(([role, count]) => (
            <div key={role} className="stat">
              <strong>{count}</strong>
              <span>{role}</span>
            </div>
          ))}
        </div>
      )}

      <CreateUserForm
        onDone={(ok, msg) => {
          if (ok) {
            users.reload()
            stats.reload()
            setNotice(msg ?? 'User created')
          }
        }}
      />

      <div className="group">
        <h2>Users</h2>
        {users.loading && <p>Loading users…</p>}
        {users.error && <p className="error">{users.error}</p>}
        {users.data && users.data.items.length === 0 && <p className="muted">No users yet.</p>}
        {users.data && (
          <div className="list">
            {users.data.items.map((u) => (
              <div key={u.id} className="row">
                <UserMain u={u} />
                <div className="row-actions">
                  <select
                    value={u.role}
                    disabled={busyId === u.id}
                    onChange={(e) =>
                      act(u.id, () => api.adminUpdateUser(u.id, { role: e.target.value }), `Role updated to ${e.target.value}`)
                    }
                  >
                    {ROLES.map((r) => (
                      <option key={r} value={r}>
                        {r}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    className="btn"
                    disabled={busyId === u.id}
                    onClick={() => {
                      const password = window.prompt(`New password for ${u.email} (min 8 characters)`)
                      if (password === null) return
                      if (password.length < 8) {
                        window.alert('Password must be at least 8 characters.')
                        return
                      }
                      act(u.id, () => api.adminUpdateUser(u.id, { password }), 'Password reset')
                    }}
                  >
                    Reset password
                  </button>
                  {u.is_active ? (
                    <button
                      type="button"
                      className="btn danger"
                      disabled={busyId === u.id}
                      onClick={() => {
                        if (window.confirm(`Deactivate ${u.email}? Their sessions will be invalidated.`)) {
                          act(u.id, () => api.adminUpdateUser(u.id, { is_active: false }), 'User deactivated')
                        }
                      }}
                    >
                      Deactivate
                    </button>
                  ) : (
                    <button
                      type="button"
                      className="btn success"
                      disabled={busyId === u.id}
                      onClick={() => act(u.id, () => api.adminUpdateUser(u.id, { is_active: true }), 'User reactivated')}
                    >
                      Reactivate
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  )
}

function UserMain({ u }: { u: AdminUser }) {
  return (
    <div className="row-main">
      <div className="row-title">
        {u.full_name}
        <Badge tone={u.is_active ? 'green' : 'red'}>{u.is_active ? 'active' : 'inactive'}</Badge>
      </div>
      <div className="row-sub">
        {u.email} · {u.role}
        {u.patient_id ? ` · patient ${u.patient_id}` : ''}
      </div>
    </div>
  )
}

function CreateUserForm({ onDone }: { onDone: (ok: boolean, msg?: string) => void }) {
  const [show, setShow] = useState(false)
  const [email, setEmail] = useState('')
  const [full_name, setFullName] = useState('')
  const [role, setRole] = useState('family_contributor')
  const [password, setPassword] = useState('')
  const [patientId, setPatientId] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const needsPatient = !PATIENTLESS_ROLES.includes(role)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      await api.adminCreateUser({
        email,
        full_name,
        role,
        password,
        patient_id: patientId || null,
      })
      onDone(true, `Created ${email}`)
      setEmail('')
      setFullName('')
      setPassword('')
      setPatientId('')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Request failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="panel">
      <div className="page-head">
        <h2>Create a user</h2>
        <button type="button" className="btn primary" onClick={() => setShow((v) => !v)}>
          <Icon name="plus" size={16} />
          {show ? 'Cancel' : 'New user'}
        </button>
      </div>
      {show && (
        <form className="form" onSubmit={onSubmit}>
          <label>
            Email
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </label>
          <label>
            Full name
            <input value={full_name} onChange={(e) => setFullName(e.target.value)} required />
          </label>
          <label>
            Role
            <select value={role} onChange={(e) => setRole(e.target.value)}>
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
          </label>
          <label>
            Password (min 8 characters)
            <input
              type="password"
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </label>
          <label>
            Patient id{needsPatient ? ' (required for this role)' : ' (not allowed for this role)'}
            <input
              value={patientId}
              onChange={(e) => setPatientId(e.target.value)}
              disabled={!needsPatient}
            />
          </label>
          {error && <p className="error">{error}</p>}
          <div className="form-actions">
            <button type="submit" className="btn primary" disabled={busy}>
              {busy ? 'Creating…' : 'Create'}
            </button>
          </div>
        </form>
      )}
    </div>
  )
}
