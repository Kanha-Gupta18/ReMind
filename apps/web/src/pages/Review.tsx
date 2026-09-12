import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import type { MemoryCreate as MemoryCreatePayload, StructuredReference } from '../api/types'
import { CREATE_MEMORY_ROLES, REVIEW_ROLES } from '../api/types'
import { useApiData } from '../api/useApiData'
import { useAuth } from '../auth/AuthContext'
import { Badge, statusTone } from '../components/Badge'
import { Icon } from '../components/Icon'

const TABS = [
  { key: 'AWAITING_REVIEW', label: 'Awaiting review' },
  { key: 'DRAFT', label: 'Drafts' },
  { key: 'AI_RECONSTRUCTED', label: 'AI drafts' },
  { key: 'APPROVED', label: 'Approved' },
  { key: 'DISPUTED', label: 'Disputed' },
  { key: 'REJECTED', label: 'Rejected' },
  { key: 'ALL', label: 'All' },
]

export function Review() {
  const { user } = useAuth()
  const [tab, setTab] = useState('AWAITING_REVIEW')
  const [busyId, setBusyId] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [showNew, setShowNew] = useState(false)

  const { data, loading, error, reload } = useApiData(
    () => api.memories(tab === 'ALL' ? undefined : tab),
    [tab],
  )

  const canReview = user !== null && REVIEW_ROLES.includes(user.role)
  const canCreate = user !== null && CREATE_MEMORY_ROLES.includes(user.role)

  if (user !== null && !REVIEW_ROLES.includes(user.role)) {
    return <Navigate to="/" replace />
  }

  async function act(id: string, fn: () => Promise<unknown>, message: string) {
    setBusyId(id)
    setActionError(null)
    setNotice(null)
    try {
      await fn()
      setNotice(message)
      reload()
    } catch (e) {
      setActionError(e instanceof ApiError ? e.message : 'Request failed')
    } finally {
      setBusyId(null)
    }
  }

  async function rejectOrDispute(id: string, kind: 'reject' | 'dispute') {
    const reason = window.prompt(`Reason for ${kind} (optional)`)
    if (reason === null) return
    await act(
      id,
      () => (kind === 'reject' ? api.rejectMemory(id, reason || undefined) : api.disputeMemory(id, reason || undefined)),
      kind === 'reject' ? 'Memory rejected' : 'Memory disputed',
    )
  }

  return (
    <section>
      <div className="page-head">
        <h1>Review</h1>
        {canCreate && (
          <button type="button" className="btn primary" onClick={() => setShowNew((v) => !v)}>
            <Icon name="plus" size={16} />
            {showNew ? 'Cancel' : 'New memory'}
          </button>
        )}
      </div>

      <div className="tabs">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            className={`tab${tab === t.key ? ' active' : ''}`}
            onClick={() => setTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {showNew && canCreate && <MemoryForm onDone={(ok) => { if (ok) { setShowNew(false); setTab('DRAFT'); reload() } }} />}

      {notice && <p className="success">{notice}</p>}
      {actionError && <p className="error">{actionError}</p>}
      {loading && <p>Loading memories…</p>}
      {error && <p className="error">{error}</p>}

      <div className="list">
        {data?.items.map((m) => (
          <div key={m.id} className="row">
            <div className="row-main">
              <div className="row-title">
                <Link to={`/memories/${m.id}`}>{m.title}</Link>
                <Badge tone={statusTone(m.status)}>{m.status}</Badge>
              </div>
              <div className="row-sub">
                {m.memory_date ?? 'date unknown'}, confidence {m.confidence_score}
                {m.confidence_band ? ` (${m.confidence_band})` : ''}
                {m.tags.length > 0 ? `, ${m.tags.slice(0, 3).join(', ')}` : ''}
              </div>
              {m.has_pending_revision && m.approved_revision_id && (
                <p className="row-note">A published revision remains active while this candidate is reviewed.</p>
              )}
              {m.sensitivity_flags.length > 0 && (
                <div className="chips">
                  {m.sensitivity_flags.map((f) => (
                    <span key={f} className="chip danger">
                      {f}
                    </span>
                  ))}
                </div>
              )}
            </div>
            <div className="row-actions">
              {(m.status === 'DRAFT' || m.status === 'AI_RECONSTRUCTED') && canReview && (
                <button
                  type="button"
                  className="btn"
                  disabled={busyId === m.id}
                  onClick={() => act(m.id, () => api.submitMemory(m.id), 'Submitted for review')}
                >
                  {busyId === m.id ? '…' : 'Submit'}
                </button>
              )}
              {m.status === 'AWAITING_REVIEW' && canReview && (
                <>
                  <button
                    type="button"
                    className="btn success"
                    disabled={busyId === m.id}
                    onClick={() => act(m.id, () => api.approveMemory(m.id), 'Memory approved')}
                  >
                    <Icon name="check" size={15} />
                    {busyId === m.id ? '…' : 'Approve'}
                  </button>
                  <button
                    type="button"
                    className="btn"
                    disabled={busyId === m.id}
                    onClick={() => rejectOrDispute(m.id, 'reject')}
                  >
                    Reject
                  </button>
                  <button
                    type="button"
                    className="btn"
                    disabled={busyId === m.id}
                    onClick={() => rejectOrDispute(m.id, 'dispute')}
                  >
                    Dispute
                  </button>
                </>
              )}
              {m.status === 'APPROVED' && canReview && (
                <button
                  type="button"
                  className="btn"
                  disabled={busyId === m.id}
                  onClick={() => {
                    if (window.confirm('Archive this memory?')) act(m.id, () => api.archiveMemory(m.id), 'Memory archived')
                  }}
                >
                  Archive
                </button>
              )}
              <Link className="btn" to={`/memories/${m.id}`}>
                Details
              </Link>
            </div>
          </div>
        ))}
        {data && data.items.length === 0 && <p className="muted">Nothing here.</p>}
      </div>
    </section>
  )
}

const ACCURACIES = ['exact', 'day', 'month', 'year', 'approximate']
const VISIBILITIES = ['both', 'patient', 'family_only']

function MemoryForm({ onDone }: { onDone: (ok: boolean) => void }) {
  const [title, setTitle] = useState('')
  const [narrative, setNarrative] = useState('')
  const [memory_date, setMemoryDate] = useState('')
  const [date_accuracy, setDateAccuracy] = useState('approximate')
  const [tagsText, setTagsText] = useState('')
  const [visibility, setVisibility] = useState('both')
  const [peopleIds, setPeopleIds] = useState<string[]>([])
  const [placeIds, setPlaceIds] = useState<string[]>([])
  const [eventIds, setEventIds] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const peopleState = useApiData(() => api.people(), [])
  const placesState = useApiData(() => api.knowledgePlaces(), [])
  const eventsState = useApiData(() => api.knowledgeEvents(), [])

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setBusy(true)
    const payload: MemoryCreatePayload = {
      title,
      narrative: narrative || null,
      memory_date: memory_date || null,
      date_accuracy,
      tags: tagsText.split(',').map((t) => t.trim()).filter(Boolean),
      visibility,
      people_ids: peopleIds,
      place_ids: placeIds,
      event_ids: eventIds,
    }
    try {
      await api.createMemory(payload)
      onDone(true)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Request failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="panel form revision-form" onSubmit={onSubmit}>
      <div className="section-heading">
        <div>
          <h2>Create a memory</h2>
          <p>Start a draft with its date and known people, places, and events.</p>
        </div>
      </div>
      <div className="form-grid">
      <label className="form-span-2">
        Title
        <input value={title} onChange={(e) => setTitle(e.target.value)} required />
      </label>
      <label className="form-span-2">
        Narrative
        <textarea value={narrative} onChange={(e) => setNarrative(e.target.value)} rows={4} />
      </label>
      <label>
        Date
        <input type="date" value={memory_date} onChange={(e) => setMemoryDate(e.target.value)} />
      </label>
      <label>
        Date accuracy
        <select value={date_accuracy} onChange={(e) => setDateAccuracy(e.target.value)}>
          {ACCURACIES.map((a) => (
            <option key={a} value={a}>
              {a}
            </option>
          ))}
        </select>
      </label>
      <label>
        Tags (comma-separated)
        <input value={tagsText} onChange={(e) => setTagsText(e.target.value)} />
      </label>
      <label>
        Visibility
        <select value={visibility} onChange={(e) => setVisibility(e.target.value)}>
          {VISIBILITIES.map((v) => (
            <option key={v} value={v}>
              {v}
            </option>
          ))}
        </select>
      </label>
      </div>
      <div className="reference-grid">
        <MemoryReferencePicker label="People" items={peopleState.data?.items ?? []} selected={peopleIds} onChange={setPeopleIds} loading={peopleState.loading} error={peopleState.error} />
        <MemoryReferencePicker label="Places" items={placesState.data?.items ?? []} selected={placeIds} onChange={setPlaceIds} loading={placesState.loading} error={placesState.error} />
        <MemoryReferencePicker label="Events" items={eventsState.data?.items ?? []} selected={eventIds} onChange={setEventIds} loading={eventsState.loading} error={eventsState.error} />
      </div>
      {error && <p className="error">{error}</p>}
      <div className="form-actions">
        <button type="submit" className="btn primary" disabled={busy}>
          {busy ? 'Creating…' : 'Create'}
        </button>
      </div>
    </form>
  )
}

function MemoryReferencePicker({ label, items, selected, onChange, loading, error }: {
  label: string
  items: StructuredReference[]
  selected: string[]
  onChange: (ids: string[]) => void
  loading: boolean
  error: string | null
}) {
  return (
    <fieldset className="reference-picker">
      <legend>{label}</legend>
      {loading && <p className="muted">Loading...</p>}
      {error && <p className="error">Unavailable: {error}</p>}
      {!loading && !error && items.length === 0 && <p className="muted">None recorded yet.</p>}
      {items.map((item) => (
        <label key={item.id} className="choice-row">
          <input
            type="checkbox"
            checked={selected.includes(item.id)}
            onChange={(event) => onChange(event.target.checked ? [...selected, item.id] : selected.filter((id) => id !== item.id))}
          />
          <span>{item.name}</span>
        </label>
      ))}
    </fieldset>
  )
}
