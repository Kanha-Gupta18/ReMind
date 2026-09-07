import { useState } from 'react'
import { Navigate } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import type { SafetyEvent } from '../api/types'
import { SAFETY_ROLES } from '../api/types'
import { useApiData } from '../api/useApiData'
import { useAuth } from '../auth/AuthContext'
import { Badge } from '../components/Badge'

export function severityTone(severity: string): string {
  return (
    {
      LOW: 'neutral',
      MEDIUM: 'amber',
      HIGH: 'red',
      CRITICAL: 'red',
    }[severity] ?? 'neutral'
  )
}

export function Safety() {
  const { user } = useAuth()
  const isAdmin = user?.role === 'administrator'

  const [patientId, setPatientId] = useState('')
  const [unackOnly, setUnackOnly] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  const pid = isAdmin ? patientId || undefined : undefined
  const level = useApiData(() => api.safetyLevel(pid), [patientId])
  const events = useApiData(
    () => api.safetyEvents(unackOnly, pid),
    [patientId, unackOnly],
  )

  if (user && !SAFETY_ROLES.includes(user.role)) {
    return <Navigate to="/" replace />
  }

  async function acknowledge(e: SafetyEvent) {
    setActionError(null)
    setNotice(null)
    try {
      await api.acknowledgeSafetyEvent(e.id)
      setNotice('Event acknowledged')
      events.reload()
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : 'Request failed')
    }
  }

  return (
    <section>
      <div className="page-head">
        <h1>Safety</h1>
      </div>
      <p className="muted">
        Safety events, caregiver stops, and the patient's current release level.
      </p>

      {isAdmin && (
        <label className="inline-label">
          Patient id (required for administrators)
          <input value={patientId} onChange={(e) => setPatientId(e.target.value)} placeholder="patient id" />
        </label>
      )}

      {notice && <p className="success">{notice}</p>}
      {actionError && <p className="error">{actionError}</p>}

      <div className="panel">
        <h2>Safety level</h2>
        {level.loading && <p className="muted">Loading…</p>}
        {level.error && <p className="error">{level.error}</p>}
        {level.data && (
          <div className={`level-banner level-${String(level.data.safety_level).toLowerCase()}`}>
            <strong>{level.data.safety_level}</strong>
            <span>for patient {level.data.patient_id}</span>
          </div>
        )}
      </div>

      <div className="group">
        <div className="page-head">
          <h2>Events</h2>
          <label className="check-row">
            <input
              type="checkbox"
              checked={unackOnly}
              onChange={(e) => setUnackOnly(e.target.checked)}
            />
            Unacknowledged only
          </label>
        </div>
        {events.loading && <p>Loading…</p>}
        {events.error && <p className="error">{events.error}</p>}
        {events.data && events.data.items.length === 0 && (
          <p className="muted">No safety events.</p>
        )}
        {events.data && (
          <div className="list">
            {events.data.items.map((e) => (
              <div key={e.id} className="row">
                <div className="row-main">
                  <div className="row-title">
                    {e.event_type}
                    <Badge tone={severityTone(e.severity)}>{e.severity}</Badge>
                    {e.acknowledged_at ? (
                      <Badge tone="green">acknowledged</Badge>
                    ) : (
                      <Badge tone="amber">unacknowledged</Badge>
                    )}
                  </div>
                  <div className="row-sub">
                    {e.created_at}
                    {e.session_id ? ` · session ${e.session_id}` : ''}
                    {e.action_taken ? ` · ${e.action_taken}` : ''}
                    {e.acknowledged_at ? ` · by ${e.acknowledged_by}` : ''}
                  </div>
                  {e.context && Object.keys(e.context).length > 0 && (
                    <div className="rev-content" style={{ marginTop: '0.5rem' }}>
                      {JSON.stringify(e.context, null, 2)}
                    </div>
                  )}
                </div>
                {!e.acknowledged_at && (
                  <div className="row-actions">
                    <button type="button" className="btn primary" onClick={() => acknowledge(e)}>
                      Acknowledge
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  )
}
