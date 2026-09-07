import { useState } from 'react'
import type { FormEvent } from 'react'
import { api, ApiError } from '../api/client'
import type { FaceMatch, Person, RelationItem } from '../api/types'
import { PEOPLE_CREATE_ROLES, PEOPLE_EDIT_ROLES } from '../api/types'
import { useApiData } from '../api/useApiData'
import { useAuth } from '../auth/AuthContext'
import { Badge } from '../components/Badge'
import { Icon } from '../components/Icon'

const IDENTITY_STATUSES = ['UNIDENTIFIED', 'POSSIBLE_MATCH', 'LIKELY_MATCH', 'FAMILY_CONFIRMED', 'DISPUTED']

export function identityTone(status: string): string {
  return (
    {
      UNIDENTIFIED: 'neutral',
      POSSIBLE_MATCH: 'amber',
      LIKELY_MATCH: 'blue',
      FAMILY_CONFIRMED: 'green',
      DISPUTED: 'red',
    }[status] ?? 'neutral'
  )
}

export function People() {
  const { user } = useAuth()
  const isAdmin = user?.role === 'administrator'
  const canCreate = user !== null && PEOPLE_CREATE_ROLES.includes(user.role)
  const canEdit = user !== null && PEOPLE_EDIT_ROLES.includes(user.role)

  const [notice, setNotice] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [patientId, setPatientId] = useState('')
  const people = useApiData(
    () => api.people(isAdmin ? patientId || undefined : undefined),
    [patientId],
  )
  const matches = useApiData(
    () => api.faceMatches(isAdmin ? patientId || undefined : undefined),
    [patientId],
  )

  async function act(fn: () => Promise<unknown>, message: string) {
    setActionError(null)
    setNotice(null)
    try {
      await fn()
      setNotice(message)
      people.reload()
      matches.reload()
    } catch (e) {
      setActionError(e instanceof ApiError ? e.message : 'Request failed')
    }
  }

  return (
    <section>
      <div className="page-head">
        <h1>People</h1>
      </div>
      <p className="muted">
        The people in the patient's story, their identity status, and face-match reviews.
      </p>

      {notice && <p className="success">{notice}</p>}
      {actionError && <p className="error">{actionError}</p>}

      {isAdmin && (
        <label className="inline-label">
          Patient id (required for administrators)
          <input
            value={patientId}
            onChange={(e) => setPatientId(e.target.value)}
            placeholder="patient id"
          />
        </label>
      )}
      {isAdmin && !patientId && (
        <p className="muted">Enter a patient id above to view their people.</p>
      )}

      {canCreate && (
        <AddPerson
          patientId={patientId}
          onDone={(ok, msg) => {
            if (ok) {
              people.reload()
              setNotice(msg ?? 'Person added')
            }
          }}
        />
      )}

      <div className="group">
        <div className="page-head">
          <h2>People</h2>
        </div>
        {people.loading && <p>Loading…</p>}
        {people.error && <p className="error">{people.error}</p>}
        {people.data && people.data.items.length === 0 && <p className="muted">No people yet.</p>}
        {people.data && (
          <div className="list">
            {people.data.items.map((p) => (
              <PersonRow
                key={p.id}
                p={p}
                canEdit={canEdit}
                onAct={(fn, msg) => act(fn, msg)}
              />
            ))}
          </div>
        )}
      </div>

      {canEdit && (
        <div className="group">
          <div className="page-head">
            <h2>Face matches</h2>
          </div>
          <p className="muted">
            Confirm which detected face belongs to which person. Only reviewer/guardian/admin can
            confirm.
          </p>
          {matches.loading && <p>Loading…</p>}
          {matches.error && <p className="error">{matches.error}</p>}
          {matches.data && matches.data.items.length === 0 && (
            <p className="muted">No face matches yet.</p>
          )}
          {matches.data && (
            <div className="list">
              {matches.data.items.map((m) => (
                <FaceMatchRow
                  key={m.id}
                  m={m}
                  people={people.data?.items ?? []}
                  onAct={(fn, msg) => act(fn, msg)}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </section>
  )
}

function PersonRow({
  p,
  canEdit,
  onAct,
}: {
  p: Person
  canEdit: boolean
  onAct: (fn: () => Promise<unknown>, msg: string) => void
}) {
  const [editing, setEditing] = useState(false)
  const [relations, setRelations] = useState<RelationItem[] | null>(null)
  const [relationsOpen, setRelationsOpen] = useState(false)

  async function toggleRelations() {
    if (relationsOpen) {
      setRelationsOpen(false)
      return
    }
    setRelationsOpen(true)
    setRelations(null)
    try {
      const r = await api.personRelations(p.id)
      setRelations(r.items)
    } catch {
      setRelations([])
    }
  }

  return (
    <div className="stack">
      <div className="row">
        <div className="row-main">
          <div className="row-title">
            {p.name}
            <Badge tone={identityTone(p.identity_status)}>{p.identity_status}</Badge>
          </div>
          <div className="row-sub">
            {p.relationship_to_patient ? `${p.relationship_to_patient} · ` : ''}
            {p.created_at}
          </div>
          {p.aliases.length > 0 && (
            <div className="chips">
              {p.aliases.map((a) => (
                <span key={a} className="chip">
                  {a}
                </span>
              ))}
            </div>
          )}
          {p.notes && <p className="muted">{p.notes}</p>}
        </div>
        <div className="row-actions">
          <button type="button" className="btn" onClick={toggleRelations}>
            {relationsOpen ? 'Hide relations' : 'Relations'}
          </button>
          {canEdit && (
            <button type="button" className="btn" onClick={() => setEditing((v) => !v)}>
              {editing ? 'Cancel' : 'Edit'}
            </button>
          )}
        </div>
      </div>
      {relationsOpen && (
        <div className="panel">
          <h3>Relations</h3>
          {relations === null && <p className="muted">Loading…</p>}
          {relations !== null && relations.length === 0 && (
            <p className="muted">No graph relations found for {p.name}.</p>
          )}
          {relations !== null &&
            relations.map((r, i) => (
              <div key={i} className="row-sub">
                {r.other_name} ({r.other_node_type}) — {r.relation_type}{' '}
                <Badge tone={r.status === 'CONFIRMED' ? 'green' : 'amber'}>{r.status}</Badge>
              </div>
            ))}
        </div>
      )}
      {editing && (
        <PersonForm
          p={p}
          onSave={(patch) => {
            setEditing(false)
            onAct(() => api.updatePerson(p.id, patch), 'Person updated')
          }}
        />
      )}
    </div>
  )
}

function PersonForm({
  p,
  onSave,
}: {
  p: Person
  onSave: (patch: {
    name?: string
    aliases?: string[]
    relationship_to_patient?: string | null
    identity_status?: string
    notes?: string | null
  }) => void
}) {
  const [name, setName] = useState(p.name)
  const [aliasesText, setAliasesText] = useState((p.aliases ?? []).join(', '))
  const [relationship, setRelationship] = useState(p.relationship_to_patient ?? '')
  const [status, setStatus] = useState(p.identity_status)
  const [notes, setNotes] = useState(p.notes ?? '')

  return (
    <form
      className="panel form"
      onSubmit={(e) => {
        e.preventDefault()
        onSave({
          name: name || undefined,
          aliases: aliasesText.split(',').map((a) => a.trim()).filter(Boolean),
          relationship_to_patient: relationship || null,
          identity_status: status,
          notes: notes || null,
        })
      }}
    >
      <label>
        Name
        <input value={name} onChange={(e) => setName(e.target.value)} required />
      </label>
      <label>
        Aliases (comma-separated)
        <input value={aliasesText} onChange={(e) => setAliasesText(e.target.value)} />
      </label>
      <label>
        Relationship to patient
        <input value={relationship} onChange={(e) => setRelationship(e.target.value)} />
      </label>
      <label>
        Identity status
        <select value={status} onChange={(e) => setStatus(e.target.value)}>
          {IDENTITY_STATUSES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
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

function FaceMatchRow({
  m,
  people,
  onAct,
}: {
  m: FaceMatch
  people: Person[]
  onAct: (fn: () => Promise<unknown>, msg: string) => void
}) {
  const [personId, setPersonId] = useState('')
  const confirmed = m.face_match_state === 'FAMILY_CONFIRMED'

  return (
    <div className="row">
      <div className="row-main">
        <div className="row-title">
          Source {m.source_id}
          <Badge tone={confirmed ? 'green' : 'amber'}>{m.face_match_state}</Badge>
        </div>
        <div className="row-sub">
          confidence {Math.round(m.confidence * 100)}%
          {m.model_version ? ` · ${m.model_version}` : ''}
          {m.person_id ? ` · person ${m.person_id}` : ''}
        </div>
      </div>
      {!confirmed && (
        <div className="row-actions">
          <select value={personId} onChange={(e) => setPersonId(e.target.value)}>
            <option value="">Choose a person…</option>
            {people.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
          <button
            type="button"
            className="btn primary"
            disabled={!personId}
            onClick={() =>
              onAct(() => api.confirmFaceMatch(m.id, personId), 'Face match confirmed')
            }
          >
            <Icon name="check" size={14} /> Confirm
          </button>
        </div>
      )}
    </div>
  )
}

function AddPerson({ patientId, onDone }: { patientId: string; onDone: (ok: boolean, msg?: string) => void }) {
  const [show, setShow] = useState(false)
  const [name, setName] = useState('')
  const [aliasesText, setAliasesText] = useState('')
  const [relationship, setRelationship] = useState('')
  const [notes, setNotes] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      await api.createPerson(
        {
          name,
          aliases: aliasesText.split(',').map((a) => a.trim()).filter(Boolean),
          relationship_to_patient: relationship || null,
          notes: notes || null,
        },
        patientId || undefined,
      )
      onDone(true, `Added ${name}`)
      setShow(false)
      setName('')
      setAliasesText('')
      setRelationship('')
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
        <h2>Add a person</h2>
        <button type="button" className="btn primary" onClick={() => setShow((v) => !v)}>
          <Icon name="plus" size={16} />
          {show ? 'Cancel' : 'Add person'}
        </button>
      </div>
      {show && (
        <form className="form" onSubmit={onSubmit}>
          <label>
            Name
            <input value={name} onChange={(e) => setName(e.target.value)} required />
          </label>
          <label>
            Aliases (comma-separated)
            <input value={aliasesText} onChange={(e) => setAliasesText(e.target.value)} />
          </label>
          <label>
            Relationship to patient
            <input value={relationship} onChange={(e) => setRelationship(e.target.value)} />
          </label>
          <label>
            Notes
            <input value={notes} onChange={(e) => setNotes(e.target.value)} />
          </label>
          {error && <p className="error">{error}</p>}
          <div className="form-actions">
            <button type="submit" className="btn primary" disabled={busy}>
              {busy ? 'Adding…' : 'Add person'}
            </button>
          </div>
        </form>
      )}
    </div>
  )
}
