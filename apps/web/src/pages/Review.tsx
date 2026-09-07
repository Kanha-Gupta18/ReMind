import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import type { MemoryCreate as MemoryCreatePayload } from '../api/types'
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
                {m.memory_date ?? 'date unknown'} · confidence {m.confidence_score}
                {m.confidence_band ? ` (${m.confidence_band})` : ''}
                {m.tags.length > 0 ? ` · ${m.tags.slice(0, 3).join(', ')}` : ''}
              </div>
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
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

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
    <form className="panel form" onSubmit={onSubmit}>
      <h2>Create a memory</h2>
      <label>
        Title
        <input value={title} onChange={(e) => setTitle(e.target.value)} required />
      </label>
      <label>
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
      {error && <p className="error">{error}</p>}
      <div className="form-actions">
        <button type="submit" className="btn primary" disabled={busy}>
          {busy ? 'Creating…' : 'Create'}
        </button>
      </div>
    </form>
  )
}
