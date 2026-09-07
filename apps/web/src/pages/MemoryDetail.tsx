import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import { RESTRICT_ROLES, REVIEW_ROLES } from '../api/types'
import { useApiData } from '../api/useApiData'
import { useAuth } from '../auth/AuthContext'
import { Badge, statusTone } from '../components/Badge'
import { Icon } from '../components/Icon'

export function MemoryDetail() {
  const { id = '' } = useParams()
  const { user } = useAuth()
  const [notice, setNotice] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [editing, setEditing] = useState(false)

  const memoryState = useApiData(() => api.getMemory(id), [id])
  const evidenceState = useApiData(() => api.getEvidence(id), [id])
  const revisionsState = useApiData(() => api.getRevisions(id), [id])

  const m = memoryState.data
  const canReview = user !== null && REVIEW_ROLES.includes(user.role)
  const canRestrict = user !== null && RESTRICT_ROLES.includes(user.role)

  async function act(fn: () => Promise<unknown>, message: string) {
    setActionError(null)
    setNotice(null)
    try {
      await fn()
      setNotice(message)
      memoryState.reload()
      evidenceState.reload()
      revisionsState.reload()
    } catch (e) {
      setActionError(e instanceof ApiError ? e.message : 'Request failed')
    }
  }

  async function rejectOrDispute(kind: 'reject' | 'dispute') {
    const reason = window.prompt(`Reason for ${kind} (optional)`)
    if (reason === null) return
    await act(
      () => (kind === 'reject' ? api.rejectMemory(id, reason || undefined) : api.disputeMemory(id, reason || undefined)),
      kind === 'reject' ? 'Memory rejected' : 'Memory disputed',
    )
  }

  return (
    <section>
      <p>
        <Link to="/review" className="back-link">
          <Icon name="arrowLeft" size={15} /> Review
        </Link>
      </p>

      {memoryState.loading && <p>Loading…</p>}
      {memoryState.error && <p className="error">{memoryState.error}</p>}
      {notice && <p className="success">{notice}</p>}
      {actionError && <p className="error">{actionError}</p>}

      {m && (
        <>
          <div className="page-head">
            <h1>{m.title}</h1>
            <Badge tone={statusTone(m.status)}>{m.status}</Badge>
          </div>

          <div className="panel">
            <p className="narrative">{m.narrative || 'No narrative.'}</p>
            <dl className="kv">
              <div><dt>Date</dt><dd>{m.memory_date ?? 'unknown'} ({m.date_accuracy ?? 'n/a'})</dd></div>
              <div><dt>Confidence</dt><dd>{m.confidence_score} {m.confidence_band ? `(${m.confidence_band})` : ''}</dd></div>
              <div><dt>Visibility</dt><dd>{m.visibility}</dd></div>
              <div><dt>Created</dt><dd>{m.created_at}</dd></div>
              {m.approved_at && <div><dt>Approved</dt><dd>{m.approved_at}</dd></div>}
              {m.model_version && <div><dt>Model</dt><dd>{m.model_version}</dd></div>}
            </dl>
            {m.sensitivity_flags.length > 0 && (
              <div className="chips">
                {m.sensitivity_flags.map((f) => (
                  <span key={f} className="chip danger">{f}</span>
                ))}
              </div>
            )}
            {m.tags.length > 0 && (
              <div className="chips">
                {m.tags.map((t) => (
                  <span key={t} className="chip">{t}</span>
                ))}
              </div>
            )}
            {m.contradictions.length > 0 && (
              <p className="error">
                Contradictions: {m.contradictions.join('; ')}
              </p>
            )}
            {m.media_urls.length > 0 && (
              <div className="chips">
                {m.media_urls.map((u) => (
                  <span key={u} className="chip">{u}</span>
                ))}
              </div>
            )}
            {m.confidence_breakdown && (
              <details className="muted">
                <summary>Confidence breakdown</summary>
                <pre>{JSON.stringify(m.confidence_breakdown, null, 2)}</pre>
              </details>
            )}
          </div>

          {canReview && (
            <div className="row-actions actions-bar">
              {(m.status === 'DRAFT' || m.status === 'AI_RECONSTRUCTED') && (
                <button type="button" className="btn" onClick={() => act(() => api.submitMemory(id), 'Submitted for review')}>
                  Submit for review
                </button>
              )}
              {m.status === 'AWAITING_REVIEW' && (
                <>
                  <button type="button" className="btn success" onClick={() => act(() => api.approveMemory(id), 'Memory approved')}>
                    Approve
                  </button>
                  <button type="button" className="btn" onClick={() => rejectOrDispute('reject')}>Reject</button>
                  <button type="button" className="btn" onClick={() => rejectOrDispute('dispute')}>Dispute</button>
                </>
              )}
              {m.status === 'APPROVED' && (
                <button type="button" className="btn" onClick={() => { if (window.confirm('Archive this memory?')) act(() => api.archiveMemory(id), 'Memory archived') }}>
                  Archive
                </button>
              )}
              {canRestrict && (
                <button
                  type="button"
                  className="btn"
                  onClick={async () => {
                    const reason = window.prompt('Reason for restricting (optional)')
                    if (reason === null) return
                    await act(() => api.restrictMemory(id, reason || undefined), 'Memory restricted')
                  }}
                >
                  Restrict
                </button>
              )}
              <button type="button" className="btn" onClick={() => setEditing((v) => !v)}>
                {editing ? 'Cancel edit' : 'Edit'}
              </button>
            </div>
          )}

          {editing && canReview && <EditForm id={id} memory={m} onDone={(ok) => { if (ok) { setEditing(false); memoryState.reload() } }} />}

          <div className="two-col">
            <div>
              <h2>Evidence</h2>
              {evidenceState.loading && <p>Loading…</p>}
              <div className="list">
                {evidenceState.data?.items.map((e) => (
                  <div key={e.id} className="row">
                    <div className="row-main">
                      <div className="row-title">
                        {e.evidence_type}
                        <Badge tone={statusTone(e.review_status)}>{e.review_status}</Badge>
                      </div>
                      <div className="row-sub">{e.claim}</div>
                      <div className="row-sub">
                        {e.source_file ?? 'no source'}
                        {e.confidence !== null ? ` · confidence ${e.confidence}` : ''}
                      </div>
                    </div>
                  </div>
                ))}
                {evidenceState.data && evidenceState.data.items.length === 0 && (
                  <p className="muted">No evidence recorded.</p>
                )}
              </div>
            </div>

            <div>
              <h2>Revisions</h2>
              {revisionsState.loading && <p>Loading…</p>}
              <div className="list">
                {revisionsState.data?.items.map((r) => (
                  <div key={r.revision_number} className="row">
                    <div className="row-main">
                      <div className="row-title">
                        Revision {r.revision_number}
                        <Badge tone={statusTone(r.status)}>{r.status}</Badge>
                      </div>
                      <div className="row-sub">{r.created_at}</div>
                      {r.content && <pre className="rev-content">{JSON.stringify(r.content, null, 2)}</pre>}
                    </div>
                  </div>
                ))}
                {revisionsState.data && revisionsState.data.items.length === 0 && (
                  <p className="muted">No revisions yet.</p>
                )}
              </div>
            </div>
          </div>
        </>
      )}
    </section>
  )
}

function EditForm({ id, memory, onDone }: { id: string; memory: { title: string; narrative: string; tags: string[] }; onDone: (ok: boolean) => void }) {
  const [title, setTitle] = useState(memory.title)
  const [narrative, setNarrative] = useState(memory.narrative ?? '')
  const [tagsText, setTagsText] = useState(memory.tags.join(', '))
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      await api.editMemory(id, {
        title,
        narrative: narrative || undefined,
        tags: tagsText.split(',').map((t) => t.trim()).filter(Boolean),
      })
      onDone(true)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Request failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="panel form" onSubmit={onSubmit}>
      <h2>Edit memory</h2>
      <label>
        Title
        <input value={title} onChange={(e) => setTitle(e.target.value)} required />
      </label>
      <label>
        Narrative
        <textarea value={narrative} onChange={(e) => setNarrative(e.target.value)} rows={4} />
      </label>
      <label>
        Tags (comma-separated)
        <input value={tagsText} onChange={(e) => setTagsText(e.target.value)} />
      </label>
      {error && <p className="error">{error}</p>}
      <div className="form-actions">
        <button type="submit" className="btn primary" disabled={busy}>
          {busy ? 'Saving…' : 'Save'}
        </button>
      </div>
    </form>
  )
}
