import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import type { MemoryDetail as MemoryDetailData, Revision, StructuredReference } from '../api/types'
import { RESTRICT_ROLES, REVIEW_ROLES } from '../api/types'
import { useApiData } from '../api/useApiData'
import { useAuth } from '../auth/AuthContext'
import { Badge, statusTone } from '../components/Badge'
import { Icon } from '../components/Icon'

const ACCURACIES = ['exact', 'day', 'month', 'year', 'approximate']
const VISIBILITIES = ['both', 'patient', 'family_only']

function formatDate(value: string | null | undefined) {
  if (!value) return 'Not recorded'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString()
}

function contentString(revision: Revision, key: string) {
  const value = revision.content?.[key]
  return typeof value === 'string' ? value : null
}

function humanize(value: string) {
  return value.toLowerCase().replaceAll('_', ' ')
}

export function MemoryDetail() {
  const { id = '' } = useParams()
  const { user } = useAuth()
  const [notice, setNotice] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [editing, setEditing] = useState(false)
  const [busy, setBusy] = useState(false)
  const [decision, setDecision] = useState<'reject' | 'dispute' | null>(null)
  const [decisionReason, setDecisionReason] = useState('')

  const memoryState = useApiData(() => api.getMemory(id), [id])
  const evidenceState = useApiData(() => api.getEvidence(id), [id])
  const revisionsState = useApiData(() => api.getRevisions(id), [id])

  const m = memoryState.data
  const canReview = user !== null && REVIEW_ROLES.includes(user.role)
  const canRestrict = user !== null && RESTRICT_ROLES.includes(user.role)
  const publishedRevision = revisionsState.data?.items.find((revision) => revision.is_approved)

  async function act(fn: () => Promise<unknown>, message: string) {
    setActionError(null)
    setNotice(null)
    setBusy(true)
    try {
      await fn()
      setNotice(message)
      await Promise.all([memoryState.reload(), evidenceState.reload(), revisionsState.reload()])
    } catch (e) {
      setActionError(e instanceof ApiError ? e.message : 'The request could not be completed. Try again.')
    } finally {
      setBusy(false)
    }
  }

  async function completeDecision(event: FormEvent) {
    event.preventDefault()
    if (!decision) return
    const kind = decision
    await act(
      () => kind === 'reject'
        ? api.rejectMemory(id, decisionReason || undefined)
        : api.disputeMemory(id, decisionReason || undefined),
      kind === 'reject' ? 'Candidate revision rejected.' : 'Memory marked as disputed.',
    )
    setDecision(null)
    setDecisionReason('')
  }

  return (
    <section className="memory-review-page">
      <p>
        <Link to="/review" className="back-link">
          <Icon name="arrowLeft" size={15} /> Review queue
        </Link>
      </p>

      {memoryState.loading && <p role="status">Loading memory...</p>}
      {memoryState.error && <p className="error">{memoryState.error}</p>}
      {notice && <p className="success" role="status">{notice}</p>}
      {actionError && <p className="error" role="alert">{actionError}</p>}

      {m && (
        <>
          <div className="page-head memory-review-head">
            <div>
              <h1>{m.title}</h1>
              <p className="lead">Review the candidate, its evidence, and every recorded decision.</p>
            </div>
            <Badge tone={statusTone(m.status)}>{humanize(m.status)}</Badge>
          </div>

          {m.has_pending_revision && m.approved_revision_id && (
            <div className="review-callout" role="status">
              <strong>Published content is protected.</strong>
              <span>Patients continue to see the approved revision until this candidate is approved.</span>
            </div>
          )}

          <div className="memory-version-grid">
            <MemoryVersion
              title={m.has_pending_revision ? 'Candidate revision' : 'Current revision'}
              description={m.has_pending_revision ? 'Visible to reviewers only' : 'The current working content'}
              narrative={m.narrative}
              memoryDate={m.memory_date}
              dateAccuracy={m.date_accuracy}
              visibility={m.visibility}
              confidence={m.confidence_score}
              confidenceBand={m.confidence_band}
              context={m.structured_context}
              tags={m.tags}
              sensitivityFlags={m.sensitivity_flags}
              emphasized
            />

            {m.has_pending_revision && publishedRevision && (
              <MemoryVersion
                title="Published revision"
                description="This remains available to the patient"
                narrative={contentString(publishedRevision, 'narrative')}
                memoryDate={contentString(publishedRevision, 'memory_date')}
                dateAccuracy={contentString(publishedRevision, 'date_accuracy')}
                visibility={contentString(publishedRevision, 'visibility') ?? 'both'}
                confidence={Number(publishedRevision.content?.confidence_score ?? 0)}
                confidenceBand={null}
                tags={Array.isArray(publishedRevision.content?.tags) ? publishedRevision.content.tags as string[] : []}
                sensitivityFlags={Array.isArray(publishedRevision.content?.sensitivity_flags) ? publishedRevision.content.sensitivity_flags as string[] : []}
              />
            )}
          </div>

          {m.contradictions.length > 0 && (
            <div className="review-callout danger" role="alert">
              <strong>Contradictory information needs attention.</strong>
              <span>{m.contradictions.join('; ')}</span>
            </div>
          )}

          {canReview && (
            <div className="row-actions actions-bar review-actions" aria-label="Memory actions">
              {(m.status === 'DRAFT' || m.status === 'AI_RECONSTRUCTED') && (
                <button type="button" className="btn primary" disabled={busy} onClick={() => act(() => api.submitMemory(id), 'Candidate submitted for review.')}>Submit for review</button>
              )}
              {m.status === 'AWAITING_REVIEW' && (
                <>
                  <button type="button" className="btn success" disabled={busy} onClick={() => act(() => api.approveMemory(id), 'Candidate approved and published.')}>
                    <Icon name="check" size={15} /> Approve and publish
                  </button>
                  <button type="button" className="btn" disabled={busy} onClick={() => setDecision('reject')}>Reject candidate</button>
                  <button type="button" className="btn" disabled={busy} onClick={() => setDecision('dispute')}>Mark disputed</button>
                </>
              )}
              {m.status === 'APPROVED' && !m.has_pending_revision && (
                <button type="button" className="btn" disabled={busy} onClick={() => { if (window.confirm('Archive this memory?')) void act(() => api.archiveMemory(id), 'Memory archived.') }}>Archive</button>
              )}
              {canRestrict && (
                <button type="button" className="btn" disabled={busy} onClick={async () => {
                  const reason = window.prompt('Reason for restricting this memory (optional)')
                  if (reason !== null) await act(() => api.restrictMemory(id, reason || undefined), 'Memory restricted.')
                }}>Restrict</button>
              )}
              <button type="button" className="btn" disabled={busy || m.status === 'AWAITING_REVIEW'} onClick={() => setEditing((value) => !value)}>
                {editing ? 'Cancel edit' : 'Edit candidate'}
              </button>
            </div>
          )}

          {decision && (
            <form className="decision-form" onSubmit={completeDecision}>
              <label htmlFor="decision-reason">Reason for {decision === 'reject' ? 'rejecting this candidate' : 'marking this memory disputed'}</label>
              <textarea id="decision-reason" value={decisionReason} onChange={(event) => setDecisionReason(event.target.value)} rows={3} autoFocus />
              <div className="form-actions">
                <button type="submit" className="btn primary" disabled={busy}>Confirm {decision}</button>
                <button type="button" className="btn" disabled={busy} onClick={() => { setDecision(null); setDecisionReason('') }}>Cancel</button>
              </div>
            </form>
          )}

          {editing && canReview && (
            <EditForm
              id={id}
              memory={m}
              onDone={async () => {
                setEditing(false)
                setNotice('A new candidate revision was saved. Submit it when it is ready for review.')
                await Promise.all([memoryState.reload(), evidenceState.reload(), revisionsState.reload()])
              }}
            />
          )}

          <div className="two-col review-columns">
            <section aria-labelledby="evidence-heading">
              <div className="section-heading">
                <div>
                  <h2 id="evidence-heading">Evidence</h2>
                  <p>Source-backed claims associated with this memory.</p>
                </div>
              </div>
              {evidenceState.loading && <p role="status">Loading evidence...</p>}
              {evidenceState.error && <p className="error">{evidenceState.error}</p>}
              <div className="evidence-list">
                {evidenceState.data?.items.map((evidence) => (
                  <article key={evidence.id} className="evidence-item">
                    <div className="row-title">
                      <span>{humanize(evidence.evidence_type)}</span>
                      <Badge tone={statusTone(evidence.review_status)}>{humanize(evidence.review_status)}</Badge>
                    </div>
                    <p>{evidence.claim}</p>
                    <p className="row-sub">
                      {evidence.source_file ?? 'No source file'}
                      {evidence.confidence !== null ? `, confidence ${evidence.confidence}` : ''}
                    </p>
                    {evidence.reviewed_at && <p className="review-attribution">Reviewed {formatDate(evidence.reviewed_at)} by {evidence.reviewed_by}</p>}
                    {canReview && evidence.review_status === 'PENDING' && (
                      <div className="row-actions evidence-actions">
                        <button type="button" className="btn success" disabled={busy} onClick={() => act(() => api.reviewEvidence(id, evidence.id, 'ACCEPTED'), 'Evidence accepted.')}>Accept</button>
                        <button type="button" className="btn" disabled={busy} onClick={() => act(() => api.reviewEvidence(id, evidence.id, 'DISPUTED'), 'Evidence marked as disputed.')}>Dispute</button>
                        <button type="button" className="btn" disabled={busy} onClick={() => act(() => api.reviewEvidence(id, evidence.id, 'REJECTED'), 'Evidence rejected.')}>Reject</button>
                      </div>
                    )}
                  </article>
                ))}
                {evidenceState.data && evidenceState.data.items.length === 0 && <p className="muted empty-state">No evidence has been recorded.</p>}
              </div>
            </section>

            <section aria-labelledby="history-heading">
              <div className="section-heading">
                <div>
                  <h2 id="history-heading">Revision history</h2>
                  <p>Every candidate and review decision is retained.</p>
                </div>
              </div>
              {revisionsState.loading && <p role="status">Loading revision history...</p>}
              {revisionsState.error && <p className="error">{revisionsState.error}</p>}
              <div className="revision-timeline">
                {revisionsState.data?.items.map((revision) => <RevisionEntry key={revision.id} revision={revision} />)}
                {revisionsState.data && revisionsState.data.items.length === 0 && <p className="muted empty-state">No revisions have been recorded.</p>}
              </div>
            </section>
          </div>
        </>
      )}
    </section>
  )
}

function MemoryVersion({ title, description, narrative, memoryDate, dateAccuracy, visibility, confidence, confidenceBand, context, tags, sensitivityFlags, emphasized = false }: {
  title: string
  description: string
  narrative: string | null
  memoryDate: string | null
  dateAccuracy: string | null
  visibility: string
  confidence: number
  confidenceBand: string | null
  context?: MemoryDetailData['structured_context']
  tags: string[]
  sensitivityFlags: string[]
  emphasized?: boolean
}) {
  return (
    <article className={`memory-version${emphasized ? ' candidate' : ''}`}>
      <header><div><h2>{title}</h2><p>{description}</p></div></header>
      <p className="narrative">{narrative || 'No narrative has been recorded.'}</p>
      <dl className="version-facts">
        <div><dt>Date</dt><dd>{memoryDate || 'Unknown'}{dateAccuracy ? ` (${humanize(dateAccuracy)})` : ''}</dd></div>
        <div><dt>Visibility</dt><dd>{humanize(visibility)}</dd></div>
        <div><dt>Confidence</dt><dd>{confidence}{confidenceBand ? ` (${humanize(confidenceBand)})` : ''}</dd></div>
      </dl>
      {context && <div className="context-groups"><ContextGroup label="People" items={context.people} /><ContextGroup label="Places" items={context.places} /><ContextGroup label="Events" items={context.events} /></div>}
      {(tags.length > 0 || sensitivityFlags.length > 0) && <div className="chips">{tags.map((tag) => <span key={tag} className="chip">{tag}</span>)}{sensitivityFlags.map((flag) => <span key={flag} className="chip danger">{humanize(flag)}</span>)}</div>}
    </article>
  )
}

function ContextGroup({ label, items }: { label: string; items: StructuredReference[] }) {
  if (items.length === 0) return null
  return <div><h3>{label}</h3><p>{items.map((item) => item.name).join(', ')}</p></div>
}

function RevisionEntry({ revision }: { revision: Revision }) {
  const title = contentString(revision, 'title') ?? 'Untitled memory'
  const narrative = contentString(revision, 'narrative')
  return (
    <article className="revision-entry">
      <div className="revision-marker" aria-hidden="true" />
      <div className="revision-body">
        <div className="row-title"><span>Revision {revision.revision_number}</span><Badge tone={statusTone(revision.status)}>{humanize(revision.status)}</Badge>{revision.is_approved && <Badge tone="green">Published</Badge>}{revision.is_candidate && <Badge tone="blue">Candidate</Badge>}</div>
        <p className="revision-title">{title}</p>
        {narrative && <p className="revision-excerpt">{narrative}</p>}
        <p className="review-attribution">Created {formatDate(revision.created_at)} by {revision.authored_by ?? 'system'}</p>
        {revision.change_note && <p className="change-note"><strong>Change note:</strong> {revision.change_note}</p>}
        {revision.reviews.map((review) => <div key={review.id} className="review-record"><strong>{humanize(review.decision)}</strong><span>{formatDate(review.created_at)} by {review.actor_id}</span>{review.reason && <p>{review.reason}</p>}</div>)}
      </div>
    </article>
  )
}

function EditForm({ id, memory, onDone }: { id: string; memory: MemoryDetailData; onDone: () => Promise<void> }) {
  const [title, setTitle] = useState(memory.title)
  const [narrative, setNarrative] = useState(memory.narrative ?? '')
  const [memoryDate, setMemoryDate] = useState(memory.memory_date ?? '')
  const [dateAccuracy, setDateAccuracy] = useState(memory.date_accuracy ?? 'approximate')
  const [visibility, setVisibility] = useState(memory.visibility)
  const [tagsText, setTagsText] = useState(memory.tags.join(', '))
  const [sensitivityText, setSensitivityText] = useState(memory.sensitivity_flags.join(', '))
  const [note, setNote] = useState('')
  const [peopleIds, setPeopleIds] = useState(memory.structured_context.people.map((item) => item.id))
  const [placeIds, setPlaceIds] = useState(memory.structured_context.places.map((item) => item.id))
  const [eventIds, setEventIds] = useState(memory.structured_context.events.map((item) => item.id))
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const peopleState = useApiData(() => api.people(), [])
  const placesState = useApiData(() => api.knowledgePlaces(), [])
  const eventsState = useApiData(() => api.knowledgeEvents(), [])

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setBusy(true)
    try {
      await api.editMemory(id, {
        title,
        narrative,
        memory_date: memoryDate || null,
        date_accuracy: dateAccuracy,
        visibility,
        tags: tagsText.split(',').map((tag) => tag.trim()).filter(Boolean),
        sensitivity_flags: sensitivityText.split(',').map((flag) => flag.trim()).filter(Boolean),
        people_ids: peopleIds,
        place_ids: placeIds,
        event_ids: eventIds,
        note,
      })
      await onDone()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'The candidate could not be saved. Try again.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="panel form revision-form" onSubmit={onSubmit}>
      <div className="section-heading"><div><h2>Edit candidate revision</h2><p>Saving creates a new reviewable candidate. It does not replace the published version.</p></div></div>
      <div className="form-grid">
        <label className="form-span-2">Title<input value={title} onChange={(event) => setTitle(event.target.value)} required /></label>
        <label className="form-span-2">Narrative<textarea value={narrative} onChange={(event) => setNarrative(event.target.value)} rows={5} /></label>
        <label>Date<input type="date" value={memoryDate} onChange={(event) => setMemoryDate(event.target.value)} /></label>
        <label>Date accuracy<select value={dateAccuracy} onChange={(event) => setDateAccuracy(event.target.value)}>{ACCURACIES.map((accuracy) => <option key={accuracy} value={accuracy}>{humanize(accuracy)}</option>)}</select></label>
        <label>Visibility<select value={visibility} onChange={(event) => setVisibility(event.target.value)}>{VISIBILITIES.map((item) => <option key={item} value={item}>{humanize(item)}</option>)}</select></label>
        <label>Topic tags<input value={tagsText} onChange={(event) => setTagsText(event.target.value)} placeholder="holiday, school, family" /></label>
        <label className="form-span-2">Sensitivity labels<input value={sensitivityText} onChange={(event) => setSensitivityText(event.target.value)} placeholder="grief, medical" /></label>
      </div>
      <div className="reference-grid">
        <ReferencePicker label="People" items={peopleState.data?.items ?? []} selected={peopleIds} onChange={setPeopleIds} loading={peopleState.loading} error={peopleState.error} />
        <ReferencePicker label="Places" items={placesState.data?.items ?? []} selected={placeIds} onChange={setPlaceIds} loading={placesState.loading} error={placesState.error} />
        <ReferencePicker label="Events" items={eventsState.data?.items ?? []} selected={eventIds} onChange={setEventIds} loading={eventsState.loading} error={eventsState.error} />
      </div>
      <label>Change note<input value={note} onChange={(event) => setNote(event.target.value)} required placeholder="What changed and why?" /></label>
      {error && <p className="error" role="alert">{error}</p>}
      <div className="form-actions"><button type="submit" className="btn primary" disabled={busy}>{busy ? 'Saving candidate...' : 'Save candidate revision'}</button></div>
    </form>
  )
}

function ReferencePicker({ label, items, selected, onChange, loading, error }: { label: string; items: StructuredReference[]; selected: string[]; onChange: (ids: string[]) => void; loading: boolean; error: string | null }) {
  return (
    <fieldset className="reference-picker">
      <legend>{label}</legend>
      {loading && <p className="muted">Loading...</p>}
      {error && <p className="error">Unavailable: {error}</p>}
      {!loading && !error && items.length === 0 && <p className="muted">None recorded yet.</p>}
      {items.map((item) => <label key={item.id} className="choice-row"><input type="checkbox" checked={selected.includes(item.id)} onChange={(event) => onChange(event.target.checked ? [...selected, item.id] : selected.filter((id) => id !== item.id))} /><span>{item.name}</span></label>)}
    </fieldset>
  )
}
