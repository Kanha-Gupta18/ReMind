import { useState } from 'react'
import type { FormEvent } from 'react'
import { api, ApiError } from '../api/client'
import type { ConsentDirective, ThirdPartyConsent } from '../api/types'
import { MANAGE_CONSENT_ROLES, SIGN_ROLES } from '../api/types'
import { useApiData } from '../api/useApiData'
import { useAuth } from '../auth/AuthContext'
import { Badge } from '../components/Badge'
import { Icon } from '../components/Icon'

export function Consent() {
  const { user } = useAuth()
  const isAdmin = user?.role === 'administrator'
  const canSign = user !== null && SIGN_ROLES.includes(user.role)
  const canManage = user !== null && MANAGE_CONSENT_ROLES.includes(user.role)

  const [patientId, setPatientId] = useState('')
  const [notice, setNotice] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  const directives = useApiData(
    () => api.consentDirectives(isAdmin ? patientId || undefined : undefined),
    [patientId],
  )
  const thirdParties = useApiData(
    () => api.thirdParties(isAdmin ? patientId || undefined : undefined),
    [patientId],
  )

  function reload() {
    directives.reload()
    thirdParties.reload()
  }

  async function act(fn: () => Promise<unknown>, message: string) {
    setActionError(null)
    setNotice(null)
    try {
      await fn()
      setNotice(message)
      reload()
    } catch (e) {
      setActionError(e instanceof ApiError ? e.message : 'Request failed')
    }
  }

  return (
    <section>
      <div className="page-head">
        <h1>Consent</h1>
      </div>
      <p className="muted">
        Versioned directives and third-party consent for the patient's archive.
      </p>

      {isAdmin && (
        <label className="inline-label">
          Patient id (required for administrators)
          <input value={patientId} onChange={(e) => setPatientId(e.target.value)} placeholder="patient id" />
        </label>
      )}

      {notice && <p className="success">{notice}</p>}
      {actionError && <p className="error">{actionError}</p>}

      <div className="group">
        <div className="page-head">
          <h2>Directives</h2>
        </div>
        {canSign && (
          <SignDirective
            isAdmin={isAdmin}
            patientId={patientId}
            onDone={(ok, msg) => {
              if (ok) {
                reload()
                setNotice(msg ?? 'Directive signed')
              }
            }}
          />
        )}
        {directives.loading && <p>Loading directives…</p>}
        {directives.error && <p className="error">{directives.error}</p>}
        {directives.data && directives.data.items.length === 0 && (
          <p className="muted">No directives signed yet.</p>
        )}
        {directives.data && (
          <div className="list">
            {[...directives.data.items]
              .sort((a, b) => b.version - a.version)
              .map((d) => (
                <DirectiveCard key={d.id} d={d} />
              ))}
          </div>
        )}
      </div>

      <div className="group">
        <div className="page-head">
          <h2>Third-party consent</h2>
        </div>
        {canManage && (
          <AddThirdParty
            isAdmin={isAdmin}
            patientId={patientId}
            onDone={(ok, msg) => {
              if (ok) {
                reload()
                setNotice(msg ?? 'Consent record added')
              }
            }}
          />
        )}
        {thirdParties.loading && <p>Loading records…</p>}
        {thirdParties.error && <p className="error">{thirdParties.error}</p>}
        {thirdParties.data && thirdParties.data.items.length === 0 && (
          <p className="muted">No third-party records yet.</p>
        )}
        {thirdParties.data && (
          <div className="list">
            {thirdParties.data.items.map((c) => (
              <ThirdPartyRow
                key={c.id}
                c={c}
                canManage={canManage}
                onAct={(fn, msg) => act(fn, msg)}
              />
            ))}
          </div>
        )}
      </div>
    </section>
  )
}

function DirectiveCard({ d }: { d: ConsentDirective }) {
  return (
    <div className="row">
      <div className="row-main">
        <div className="row-title">
          Version {d.version}
          <Badge tone="blue">v{d.version}</Badge>
        </div>
        <div className="row-sub">
          Signed {d.valid_from}
          {d.signer ? ` by ${d.signer}` : ''}
          {d.witness ? ` · witness: ${d.witness}` : ''}
          {d.training_opt_in ? ' · training opt-in' : ''}
          {d.supersedes_id ? ' · supersedes an earlier version' : ' · current version'}
        </div>
        <JsonBlock label="permissions" value={d.permissions} />
        <JsonBlock label="restrictions" value={d.restrictions} />
        <JsonBlock label="guardian_rules" value={d.guardian_rules} />
        {d.post_death_policy && <JsonBlock label="post_death_policy" value={d.post_death_policy} />}
      </div>
    </div>
  )
}

function JsonBlock({ label, value }: { label: string; value: Record<string, unknown> }) {
  return (
    <div className="json-block">
      <span className="muted">{label}</span>
      <pre>{JSON.stringify(value, null, 2)}</pre>
    </div>
  )
}

function SignDirective({
  isAdmin,
  patientId,
  onDone,
}: {
  isAdmin: boolean
  patientId: string
  onDone: (ok: boolean, msg?: string) => void
}) {
  const [show, setShow] = useState(false)
  const [permissionsText, setPermissionsText] = useState('{}')
  const [restrictionsText, setRestrictionsText] = useState('{}')
  const [guardianRulesText, setGuardianRulesText] = useState('{}')
  const [postDeathText, setPostDeathText] = useState('')
  const [witness, setWitness] = useState('')
  const [trainingOptIn, setTrainingOptIn] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    const parse = (text: string, label: string): Record<string, unknown> | null => {
      try {
        return JSON.parse(text || '{}')
      } catch {
        setError(`${label} must be valid JSON`)
        return null
      }
    }
    const permissions = parse(permissionsText, 'permissions')
    if (!permissions) return
    const restrictions = parse(restrictionsText, 'restrictions')
    if (!restrictions) return
    const guardian_rules = parse(guardianRulesText, 'guardian_rules')
    if (!guardian_rules) return
    const post_death_policy = postDeathText.trim() === '' ? null : parse(postDeathText, 'post_death_policy')
    if (postDeathText.trim() !== '' && post_death_policy === null) return

    setBusy(true)
    try {
      await api.createDirective(
        {
          permissions,
          restrictions,
          guardian_rules,
          witness: witness || null,
          training_opt_in: trainingOptIn,
          post_death_policy,
        },
        isAdmin ? patientId || undefined : undefined,
      )
      onDone(true)
      setShow(false)
      setWitness('')
      setTrainingOptIn(false)
      setPostDeathText('')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Request failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="panel">
      <div className="page-head">
        <h3>Sign a new version</h3>
        <button type="button" className="btn primary" onClick={() => setShow((v) => !v)}>
          <Icon name="plus" size={16} />
          {show ? 'Cancel' : 'Sign new version'}
        </button>
      </div>
      {show && (
        <form className="form" onSubmit={onSubmit}>
          <label>
            permissions (JSON)
            <textarea
              rows={3}
              value={permissionsText}
              onChange={(e) => setPermissionsText(e.target.value)}
              spellCheck={false}
            />
          </label>
          <label>
            restrictions (JSON)
            <textarea
              rows={3}
              value={restrictionsText}
              onChange={(e) => setRestrictionsText(e.target.value)}
              spellCheck={false}
            />
          </label>
          <label>
            guardian_rules (JSON)
            <textarea
              rows={3}
              value={guardianRulesText}
              onChange={(e) => setGuardianRulesText(e.target.value)}
              spellCheck={false}
            />
          </label>
          <label>
            post_death_policy (JSON, optional)
            <textarea
              rows={2}
              value={postDeathText}
              onChange={(e) => setPostDeathText(e.target.value)}
              placeholder='{"mode": "destroy"}'
              spellCheck={false}
            />
          </label>
          <label>
            Witness
            <input value={witness} onChange={(e) => setWitness(e.target.value)} />
          </label>
          <label className="check-row">
            <input
              type="checkbox"
              checked={trainingOptIn}
              onChange={(e) => setTrainingOptIn(e.target.checked)}
            />
            Allow use of anonymized data for training
          </label>
          {error && <p className="error">{error}</p>}
          <div className="form-actions">
            <button type="submit" className="btn primary" disabled={busy}>
              {busy ? 'Signing…' : 'Sign version'}
            </button>
          </div>
        </form>
      )}
    </div>
  )
}

function ThirdPartyRow({
  c,
  canManage,
  onAct,
}: {
  c: ThirdPartyConsent
  canManage: boolean
  onAct: (fn: () => Promise<unknown>, msg: string) => void
}) {
  const [editing, setEditing] = useState(false)

  return (
    <div className="stack">
      <div className="row">
        <div className="row-main">
          <div className="row-title">
            {c.person_name}
            <Badge tone={c.consent_given ? 'green' : 'red'}>
              {c.consent_given ? 'consented' : 'not consented'}
            </Badge>
          </div>
          <div className="row-sub">
            {c.contact ? `${c.contact} · ` : ''}
            {c.person_id ? `person ${c.person_id} · ` : ''}
            {c.created_at}
          </div>
          {c.notes && <p className="muted">{c.notes}</p>}
        </div>
        {canManage && (
          <div className="row-actions">
            <button type="button" className="btn" onClick={() => setEditing((v) => !v)}>
              {editing ? 'Cancel' : 'Edit'}
            </button>
            <button
              type="button"
              className="btn danger"
              onClick={() => {
                if (window.confirm(`Delete consent record for ${c.person_name}?`)) {
                  onAct(() => api.deleteThirdParty(c.id), 'Consent record deleted')
                }
              }}
            >
              Delete
            </button>
          </div>
        )}
      </div>
      {editing && (
        <ThirdPartyForm
          c={c}
          onSave={(patch) => {
            setEditing(false)
            onAct(() => api.updateThirdParty(c.id, patch), 'Record updated')
          }}
        />
      )}
    </div>
  )
}

function ThirdPartyForm({
  c,
  onSave,
}: {
  c: ThirdPartyConsent
  onSave: (patch: {
    person_name?: string
    person_id?: string | null
    contact?: string | null
    consent_given?: boolean
    notes?: string | null
  }) => void
}) {
  const [person_name, setPersonName] = useState(c.person_name)
  const [contact, setContact] = useState(c.contact ?? '')
  const [consent_given, setConsentGiven] = useState(c.consent_given)
  const [notes, setNotes] = useState(c.notes ?? '')

  return (
    <form
      className="panel form"
      onSubmit={(e) => {
        e.preventDefault()
        onSave({
          person_name: person_name || undefined,
          contact: contact || null,
          consent_given,
          notes: notes || null,
        })
      }}
    >
      <label>
        Name
        <input value={person_name} onChange={(e) => setPersonName(e.target.value)} required />
      </label>
      <label>
        Contact
        <input value={contact} onChange={(e) => setContact(e.target.value)} />
      </label>
      <label className="check-row">
        <input type="checkbox" checked={consent_given} onChange={(e) => setConsentGiven(e.target.checked)} />
        Consent given
      </label>
      <label>
        Notes
        <input value={notes} onChange={(e) => setNotes(e.target.value)} />
      </label>
      <div className="form-actions">
        <button type="submit" className="btn primary">
          Save
        </button>
      </div>
    </form>
  )
}

function AddThirdParty({
  isAdmin,
  patientId,
  onDone,
}: {
  isAdmin: boolean
  patientId: string
  onDone: (ok: boolean, msg?: string) => void
}) {
  const [show, setShow] = useState(false)
  const [person_name, setPersonName] = useState('')
  const [contact, setContact] = useState('')
  const [consent_given, setConsentGiven] = useState(false)
  const [notes, setNotes] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      await api.createThirdParty(
        {
          person_name,
          contact: contact || null,
          consent_given,
          notes: notes || null,
        },
        isAdmin ? patientId || undefined : undefined,
      )
      onDone(true, `Added ${person_name}`)
      setShow(false)
      setPersonName('')
      setContact('')
      setConsentGiven(false)
      setNotes('')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Request failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="panel">
      <div className="page-head">
        <h3>Add a record</h3>
        <button type="button" className="btn primary" onClick={() => setShow((v) => !v)}>
          <Icon name="plus" size={16} />
          {show ? 'Cancel' : 'Add third party'}
        </button>
      </div>
      {show && (
        <form className="form" onSubmit={onSubmit}>
          <label>
            Person name
            <input value={person_name} onChange={(e) => setPersonName(e.target.value)} required />
          </label>
          <label>
            Contact
            <input value={contact} onChange={(e) => setContact(e.target.value)} />
          </label>
          <label className="check-row">
            <input type="checkbox" checked={consent_given} onChange={(e) => setConsentGiven(e.target.checked)} />
            Consent given
          </label>
          <label>
            Notes
            <input value={notes} onChange={(e) => setNotes(e.target.value)} />
          </label>
          {error && <p className="error">{error}</p>}
          <div className="form-actions">
            <button type="submit" className="btn primary" disabled={busy}>
              {busy ? 'Adding…' : 'Add record'}
            </button>
          </div>
        </form>
      )}
    </div>
  )
}
