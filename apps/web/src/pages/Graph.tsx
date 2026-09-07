import { useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import { Navigate } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import type { GraphEdge, GraphEvidence, GraphNode } from '../api/types'
import { GRAPH_CREATE_ROLES, GRAPH_READ_ROLES, GRAPH_REVIEW_ROLES } from '../api/types'
import { useApiData } from '../api/useApiData'
import { useAuth } from '../auth/AuthContext'
import { Badge } from '../components/Badge'
import { Icon } from '../components/Icon'

export function edgeTone(status: string): string {
  return (
    {
      SUGGESTED: 'amber',
      CONFIRMED: 'green',
      DISPUTED: 'red',
      REJECTED: 'neutral',
    }[status] ?? 'neutral'
  )
}

export function Graph() {
  const { user } = useAuth()
  const isAdmin = user?.role === 'administrator'
  const canCreate = user !== null && GRAPH_CREATE_ROLES.includes(user.role)
  const canReview = user !== null && GRAPH_REVIEW_ROLES.includes(user.role)

  if (user === null || !GRAPH_READ_ROLES.includes(user.role)) {
    return <Navigate to="/" replace />
  }

  const [patientId, setPatientId] = useState('')
  const [notice, setNotice] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [typeFilter, setTypeFilter] = useState('all')
  const [nameSearch, setNameSearch] = useState('')

  const graph = useApiData(
    () => api.graph(isAdmin ? patientId || undefined : undefined),
    [patientId],
  )

  const nodes = graph.data?.nodes ?? []
  const edges = graph.data?.edges ?? []

  const nodeTypes = useMemo(() => {
    const types = new Set(nodes.map((n) => n.node_type))
    return ['all', ...Array.from(types).sort()]
  }, [nodes])

  const filteredNodes = useMemo(
    () =>
      nodes.filter(
        (n) =>
          (typeFilter === 'all' || n.node_type === typeFilter) &&
          (nameSearch === '' || n.name.toLowerCase().includes(nameSearch.toLowerCase())),
      ),
    [nodes, typeFilter, nameSearch],
  )

  const nodeById = useMemo(() => {
    const m = new Map<string, GraphNode>()
    for (const n of nodes) m.set(n.id, n)
    return m
  }, [nodes])

  async function act(fn: () => Promise<unknown>, message: string) {
    setActionError(null)
    setNotice(null)
    try {
      await fn()
      setNotice(message)
      graph.reload()
    } catch (e) {
      setActionError(e instanceof ApiError ? e.message : 'Request failed')
    }
  }

  return (
    <section>
      <div className="page-head">
        <h1>Knowledge graph</h1>
      </div>
      <p className="muted">
        People, places, events, and memories connected from the patient's records.
      </p>

      {isAdmin && (
        <label className="inline-label">
          Patient id (required for administrators)
          <input value={patientId} onChange={(e) => setPatientId(e.target.value)} placeholder="patient id" />
        </label>
      )}

      {notice && <p className="success">{notice}</p>}
      {actionError && <p className="error">{actionError}</p>}

      {graph.loading && <p>Loading graph…</p>}
      {graph.error && <p className="error">{graph.error}</p>}

      {isAdmin && !patientId && !graph.loading && !graph.error && (
        <p className="muted">Enter a patient id above to view their graph.</p>
      )}

      {graph.data && (
        <>
          {canCreate && (
            <AddNode
              nodes={nodes}
              patientId={patientId}
              onDone={(ok, msg) => {
                if (ok) {
                  graph.reload()
                  setNotice(msg ?? 'Node added')
                }
              }}
            />
          )}

          <div className="group">
            <div className="page-head">
              <h2>Nodes ({filteredNodes.length})</h2>
              <div className="row-actions">
                <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
                  {nodeTypes.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
                <input
                  className="filter-input"
                  value={nameSearch}
                  onChange={(e) => setNameSearch(e.target.value)}
                  placeholder="Search name…"
                />
              </div>
            </div>
            {filteredNodes.length === 0 && <p className="muted">No nodes.</p>}
            <div className="list">
              {filteredNodes.map((n) => (
                <div key={n.id} className="row">
                  <div className="row-main">
                    <div className="row-title">
                      {n.name}
                      <Badge tone="neutral">{n.node_type}</Badge>
                    </div>
                    <div className="row-sub">
                      {n.id}
                      {n.metadata && Object.keys(n.metadata).length > 0
                        ? ` · ${JSON.stringify(n.metadata)}`
                        : ''}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="group">
            <div className="page-head">
              <h2>Edges ({edges.length})</h2>
            </div>
            {edges.length === 0 && <p className="muted">No edges yet.</p>}
            <div className="list">
              {edges.map((e) => (
                <EdgeRow
                  key={e.id}
                  e={e}
                  nodeById={nodeById}
                  canReview={canReview}
                  onAct={(fn, msg) => act(fn, msg)}
                />
              ))}
            </div>
          </div>
        </>
      )}
    </section>
  )
}

function EdgeRow({
  e,
  nodeById,
  canReview,
  onAct,
}: {
  e: GraphEdge
  nodeById: Map<string, GraphNode>
  canReview: boolean
  onAct: (fn: () => Promise<unknown>, msg: string) => void
}) {
  const [trace, setTrace] = useState<GraphEvidence[] | null>(null)
  const [traceOpen, setTraceOpen] = useState(false)
  const src = nodeById.get(e.source_node_id)?.name ?? e.source_node_id
  const tgt = nodeById.get(e.target_node_id)?.name ?? e.target_node_id

  async function toggleTrace() {
    if (traceOpen) {
      setTraceOpen(false)
      return
    }
    setTraceOpen(true)
    setTrace(null)
    try {
      const r = await api.traceGraphEdge(e.id)
      setTrace(r.items)
    } catch {
      setTrace([])
    }
  }

  return (
    <div className="stack">
      <div className="row">
        <div className="row-main">
          <div className="row-title">
            {src} → {tgt}
            <Badge tone={edgeTone(e.status)}>{e.status}</Badge>
            {e.disputed && <Badge tone="red">disputed</Badge>}
          </div>
          <div className="row-sub">
            {e.relation_type} · weight {e.weight}
            {e.confidence !== null && e.confidence !== undefined
              ? ` · confidence ${Math.round(e.confidence * 100)}%`
              : ''}
          </div>
        </div>
        <div className="row-actions">
          <button type="button" className="btn" onClick={toggleTrace}>
            <Icon name="link" size={14} />
            {traceOpen ? 'Hide trace' : 'Trace'}
          </button>
          {canReview && (
            <>
              <button
                type="button"
                className="btn success"
                onClick={() => onAct(() => api.reviewGraphEdge(e.id, 'CONFIRMED'), 'Edge confirmed')}
              >
                <Icon name="check" size={14} /> Confirm
              </button>
              <button
                type="button"
                className="btn"
                onClick={() =>
                  onAct(() => api.reviewGraphEdge(e.id, 'DISPUTED', true), 'Edge disputed')
                }
              >
                Dispute
              </button>
              <button
                type="button"
                className="btn danger"
                onClick={() => onAct(() => api.reviewGraphEdge(e.id, 'REJECTED'), 'Edge rejected')}
              >
                Reject
              </button>
            </>
          )}
        </div>
      </div>
      {traceOpen && (
        <div className="panel">
          <h3>Evidence trace</h3>
          {trace === null && <p className="muted">Loading…</p>}
          {trace !== null && trace.length === 0 && (
            <p className="muted">No source evidence recorded for this edge.</p>
          )}
          {trace !== null &&
            trace.map((ev) => (
              <div key={ev.id} className="rev-content" style={{ marginBottom: '0.5rem' }}>
                <strong>{ev.contribution}</strong> — {ev.source_data_ref}
                {ev.detail ? ` · ${ev.detail}` : ''}
              </div>
            ))}
        </div>
      )}
    </div>
  )
}

function AddNode({
  nodes,
  patientId,
  onDone,
}: {
  nodes: GraphNode[]
  patientId: string
  onDone: (ok: boolean, msg?: string) => void
}) {
  const [show, setShow] = useState(false)
  const [mode, setMode] = useState<'node' | 'edge'>('node')
  const [nodeType, setNodeType] = useState('person')
  const [name, setName] = useState('')
  const [metadataText, setMetadataText] = useState('')
  const [srcId, setSrcId] = useState('')
  const [tgtId, setTgtId] = useState('')
  const [relationType, setRelationType] = useState('related_to')
  const [weight, setWeight] = useState('0.5')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    const pid = patientId || undefined
    setBusy(true)
    try {
      if (mode === 'node') {
        let metadata: Record<string, unknown> = {}
        if (metadataText.trim() !== '') {
          try {
            metadata = JSON.parse(metadataText)
          } catch {
            setError('metadata must be valid JSON')
            setBusy(false)
            return
          }
        }
        await api.createGraphNode({ node_type: nodeType, name, metadata }, pid)
        onDone(true, `Added node ${name}`)
        setName('')
        setMetadataText('')
      } else {
        await api.createGraphEdge(
          {
            source_node_id: srcId,
            target_node_id: tgtId,
            relation_type: relationType,
            weight: Number(weight),
          },
          pid,
        )
        onDone(true, `Added edge ${relationType}`)
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Request failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="panel">
      <div className="page-head">
        <h2>Add to the graph</h2>
        <button type="button" className="btn primary" onClick={() => setShow((v) => !v)}>
          <Icon name="plus" size={16} />
          {show ? 'Cancel' : 'Add node / edge'}
        </button>
      </div>
      {show && (
        <form className="form" onSubmit={onSubmit}>
          <label>
            Mode
            <select value={mode} onChange={(e) => setMode(e.target.value as 'node' | 'edge')}>
              <option value="node">Node</option>
              <option value="edge">Edge</option>
            </select>
          </label>
          {mode === 'node' ? (
            <>
              <label>
                Node type
                <input value={nodeType} onChange={(e) => setNodeType(e.target.value)} placeholder="person, place, event, memory…" required />
              </label>
              <label>
                Name
                <input value={name} onChange={(e) => setName(e.target.value)} required />
              </label>
              <label>
                Metadata (JSON, optional)
                <textarea rows={2} value={metadataText} onChange={(e) => setMetadataText(e.target.value)} spellCheck={false} />
              </label>
            </>
          ) : (
            <>
              <label>
                Source node
                <select value={srcId} onChange={(e) => setSrcId(e.target.value)} required>
                  <option value="">Choose…</option>
                  {nodes.map((n) => (
                    <option key={n.id} value={n.id}>
                      {n.name} ({n.node_type})
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Target node
                <select value={tgtId} onChange={(e) => setTgtId(e.target.value)} required>
                  <option value="">Choose…</option>
                  {nodes.map((n) => (
                    <option key={n.id} value={n.id}>
                      {n.name} ({n.node_type})
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Relation type
                <input value={relationType} onChange={(e) => setRelationType(e.target.value)} required />
              </label>
              <label>
                Weight
                <input type="number" step="0.1" min="0" max="1" value={weight} onChange={(e) => setWeight(e.target.value)} />
              </label>
            </>
          )}
          {error && <p className="error">{error}</p>}
          <div className="form-actions">
            <button type="submit" className="btn primary" disabled={busy}>
              {busy ? 'Adding…' : 'Add'}
            </button>
          </div>
        </form>
      )}
    </div>
  )
}
