import { api } from '../api/client'
import { useApiData } from '../api/useApiData'
import { MemoryCardView } from '../components/MemoryCardView'

export function Places() {
  const { data, loading, error } = useApiData(() => api.places())

  return (
    <section>
      <div className="page-head">
        <div>
          <h1>By place</h1>
          {data && <p className="lead muted">{data.items.length} places remembered</p>}
        </div>
      </div>
      {loading && <p className="muted">Loading…</p>}
      {error && <p className="error">{error}</p>}
      {data?.items.map((group) => (
        <div key={group.place} className="group">
          <h2>
            {group.place} <span className="muted small">· {group.count} memories</span>
          </h2>
          <div className="memory-list">
            {group.memories.map((m) => (
              <MemoryCardView key={m.id} memory={m} />
            ))}
          </div>
        </div>
      ))}
      {data && data.items.length === 0 && <p className="muted">No places to show yet.</p>}
    </section>
  )
}
