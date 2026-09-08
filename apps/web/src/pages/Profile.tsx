import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { ApiError, api, PATIENT_PROFILE_UPDATED_EVENT } from '../api/client'
import type { PatientProfile, PatientProfileUpdate, Relationship } from '../api/types'
import { useApiData } from '../api/useApiData'
import { useAuth } from '../auth/AuthContext'
import { Badge } from '../components/Badge'

function readableRole(role: string) {
  return role.replaceAll('_', ' ')
}

export function Profile() {
  const { user, selectedPatientId } = useAuth()
  const profile = useApiData(() => api.patientProfile(), [selectedPatientId])
  const capabilities = useApiData(() => api.patientCapabilities(), [selectedPatientId])
  const canEdit = capabilities.data?.actions.includes('profile:edit') ?? false
  const canViewRelationships = capabilities.data?.actions.includes('relationships:view') ?? false
  const canManageRelationships = capabilities.data?.actions.includes('relationships:manage') ?? false
  const [notice, setNotice] = useState<string | null>(null)

  if (user?.role !== 'patient' && user?.patient_ids.length && !selectedPatientId) {
    return (
      <section className="empty-state" aria-live="polite">
        <h1>Choose a patient</h1>
        <p>Select a patient from the account menu before opening their profile.</p>
      </section>
    )
  }

  return (
    <section>
      <div className="page-head profile-heading">
        <div>
          <h1>Patient profile</h1>
          <p className="lead">Preferences, accessibility needs, and the people authorized to help.</p>
        </div>
        {profile.data && <Badge tone={profile.data.status === 'active' ? 'green' : 'neutral'}>{profile.data.status}</Badge>}
      </div>

      {notice && <p className="success" role="status">{notice}</p>}
      {capabilities.error && <p className="error" role="alert">Permissions could not be checked. This profile will remain read-only.</p>}
      {profile.loading && <ProfileSkeleton />}
      {profile.error && <p className="error" role="alert">{profile.error}</p>}
      {profile.data && (
        <ProfileForm
          profile={profile.data}
          canEdit={canEdit}
          onSaved={() => {
            setNotice('Profile changes saved.')
            profile.reload()
            window.dispatchEvent(new Event(PATIENT_PROFILE_UPDATED_EVENT))
          }}
        />
      )}

      <div className="profile-section">
        <div>
          <h2>Authorized relationships</h2>
          <p className="muted">Access depends on both an active relationship and the current consent directive.</p>
        </div>
        {capabilities.loading && <p className="muted">Checking relationship permissions...</p>}
        {!capabilities.loading && !canViewRelationships && (
          <p className="muted">Your current permission does not include viewing patient relationships.</p>
        )}
        {canViewRelationships && <RelationshipsSection canManage={canManageRelationships} />}
      </div>
    </section>
  )
}

function ProfileSkeleton() {
  return (
    <div className="profile-skeleton" aria-label="Loading patient profile">
      <span />
      <span />
      <span />
    </div>
  )
}

function ProfileForm({
  profile,
  canEdit,
  onSaved,
}: {
  profile: PatientProfile
  canEdit: boolean
  onSaved: () => void
}) {
  const [form, setForm] = useState<PatientProfileUpdate>({})
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setForm({
      preferred_name: profile.preferred_name,
      preferred_language: profile.preferred_language,
      date_of_birth: profile.date_of_birth,
      diagnosis: profile.diagnosis,
      diagnosis_date: profile.diagnosis_date,
      cognition_level: profile.cognition_level,
      safety_level: profile.safety_level,
      status: profile.status,
      accessibility_profile: profile.accessibility_profile,
    })
  }, [profile])

  function setField<K extends keyof PatientProfileUpdate>(key: K, value: PatientProfileUpdate[K]) {
    setForm((current) => ({ ...current, [key]: value }))
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setBusy(true)
    try {
      await api.updatePatientProfile(form)
      onSaved()
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'The profile could not be saved.')
    } finally {
      setBusy(false)
    }
  }

  const accessibility = form.accessibility_profile ?? profile.accessibility_profile

  return (
    <form className="profile-form" onSubmit={submit}>
      <fieldset disabled={!canEdit || busy}>
        <legend>Personal details</legend>
        <div className="form-grid">
          <label>
            Preferred name
            <input
              value={form.preferred_name ?? ''}
              onChange={(event) => setField('preferred_name', event.target.value)}
              required
            />
          </label>
          <label>
            Preferred language
            <input
              value={form.preferred_language ?? ''}
              onChange={(event) => setField('preferred_language', event.target.value)}
              placeholder="en-IN"
              required
            />
          </label>
          <label>
            Date of birth
            <input
              type="date"
              value={form.date_of_birth ?? ''}
              onChange={(event) => setField('date_of_birth', event.target.value || null)}
            />
          </label>
          <label>
            Profile status
            <select value={form.status ?? 'active'} onChange={(event) => setField('status', event.target.value as PatientProfile['status'])}>
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
              <option value="deceased">Deceased</option>
            </select>
          </label>
        </div>
      </fieldset>

      <fieldset disabled={!canEdit || busy}>
        <legend>Care context</legend>
        <div className="form-grid">
          <label>
            Diagnosis
            <input value={form.diagnosis ?? ''} onChange={(event) => setField('diagnosis', event.target.value || null)} />
          </label>
          <label>
            Diagnosis date
            <input type="date" value={form.diagnosis_date ?? ''} onChange={(event) => setField('diagnosis_date', event.target.value || null)} />
          </label>
          <label>
            Cognition level
            <select value={form.cognition_level ?? ''} onChange={(event) => setField('cognition_level', (event.target.value || null) as PatientProfile['cognition_level'])}>
              <option value="">Not recorded</option>
              <option value="early">Early</option>
              <option value="moderate">Moderate</option>
              <option value="advanced">Advanced</option>
            </select>
          </label>
          <label>
            Safety level
            <select value={form.safety_level ?? 'NORMAL'} onChange={(event) => setField('safety_level', event.target.value as PatientProfile['safety_level'])}>
              <option value="NORMAL">Normal</option>
              <option value="CAUTION">Caution</option>
              <option value="CAREGIVER_RECOMMENDED">Caregiver recommended</option>
              <option value="CAREGIVER_REQUIRED">Caregiver required</option>
              <option value="HIDDEN">Hidden</option>
            </select>
          </label>
        </div>
      </fieldset>

      <fieldset disabled={!canEdit || busy}>
        <legend>Accessibility</legend>
        <div className="accessibility-options">
          <label>
            Text size
            <select
              value={accessibility.text_size}
              onChange={(event) => setField('accessibility_profile', { ...accessibility, text_size: event.target.value as typeof accessibility.text_size })}
            >
              <option value="standard">Standard</option>
              <option value="large">Large</option>
              <option value="extra_large">Extra large</option>
            </select>
          </label>
          {([
            ['high_contrast', 'Use higher contrast'],
            ['reduced_motion', 'Reduce motion'],
            ['narration_auto_start', 'Start narration automatically'],
            ['simplified_navigation', 'Use simplified navigation'],
          ] as const).map(([key, label]) => (
            <label className="choice-row" key={key}>
              <input
                type="checkbox"
                checked={accessibility[key]}
                onChange={(event) => setField('accessibility_profile', { ...accessibility, [key]: event.target.checked })}
              />
              <span>{label}</span>
            </label>
          ))}
        </div>
      </fieldset>

      {!canEdit && <p className="muted" role="status">This profile is read-only under the current consent permissions.</p>}
      {error && <p className="error" role="alert">{error}</p>}
      {canEdit && (
        <button className="btn primary" type="submit" disabled={busy}>
          {busy ? 'Saving...' : 'Save profile'}
        </button>
      )}
    </form>
  )
}

function RelationshipsSection({ canManage }: { canManage: boolean }) {
  const { selectedPatientId } = useAuth()
  const relationships = useApiData(() => api.relationships(), [selectedPatientId])

  return (
    <>
      {canManage && <RelationshipForm onAdded={() => relationships.reload()} />}
      {relationships.loading && <p className="muted">Loading relationships...</p>}
      {relationships.error && <p className="error" role="alert">{relationships.error}</p>}
      {relationships.data && relationships.data.items.length === 0 && (
        <div className="empty-state compact">
          <h3>No support relationships yet</h3>
          <p>Add an existing ReMind account when the patient is ready to share access.</p>
        </div>
      )}
      {relationships.data && (
        <div className="relationship-list">
          {relationships.data.items.map((relationship) => (
            <RelationshipRow
              key={relationship.id}
              relationship={relationship}
              canEdit={canManage}
              onRevoked={() => relationships.reload()}
            />
          ))}
        </div>
      )}
    </>
  )
}

function RelationshipForm({ onAdded }: { onAdded: () => void }) {
  const [email, setEmail] = useState('')
  const [relationship, setRelationship] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await api.grantRelationship(email, relationship)
      setEmail('')
      setRelationship('')
      onAdded()
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'The relationship could not be added.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="relationship-form" onSubmit={submit}>
      <label>
        Account email
        <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
      </label>
      <label>
        Relationship to patient
        <input value={relationship} onChange={(event) => setRelationship(event.target.value)} placeholder="Daughter, friend, care coordinator" required />
      </label>
      <button className="btn primary" type="submit" disabled={busy}>
        {busy ? 'Adding...' : 'Authorize account'}
      </button>
      {error && <p className="error" role="alert">{error}</p>}
    </form>
  )
}

function RelationshipRow({
  relationship,
  canEdit,
  onRevoked,
}: {
  relationship: Relationship
  canEdit: boolean
  onRevoked: () => void
}) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function revoke() {
    if (!window.confirm(`Remove ${relationship.full_name}'s access to this patient?`)) return
    setBusy(true)
    setError(null)
    try {
      await api.revokeRelationship(relationship.id)
      onRevoked()
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Access could not be removed.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <article className="relationship-row">
      <div>
        <div className="relationship-name">
          <strong>{relationship.full_name}</strong>
          <Badge tone={relationship.status === 'active' ? 'green' : 'neutral'}>{relationship.status}</Badge>
        </div>
        <p>{relationship.relationship}</p>
        <span>{relationship.email} · {readableRole(relationship.role)}</span>
        {error && <p className="error" role="alert">{error}</p>}
      </div>
      {canEdit && relationship.status === 'active' && (
        <button className="btn danger" type="button" onClick={revoke} disabled={busy}>
          {busy ? 'Removing...' : 'Remove access'}
        </button>
      )}
    </article>
  )
}
