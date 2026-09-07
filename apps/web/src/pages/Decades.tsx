import { api } from '../api/client'
import { useApiData } from '../api/useApiData'
import { MemoryCardView } from '../components/MemoryCardView'

export function Decades() {
  const { data, loading, error } = useApiData(() => api.decades())

  return (
    <section>
      <div className="page-head">
        <div>
          <h1>By decade</h1>
          {data && <p className="lead muted">{data.items.length} decades of memories</p>}
        </div>
      </div>
      {loading && <p className="muted">Loading…</p>}
      {error && <p className="error">{error}</p>}
      {data?.items.map((group) => (
        <div key={group.decade} className="group">
          <h2>
            {group.decade}s <span className="muted small">· {group.count} memories</span>
          </h2>
          <div className="memory-list">
            {group.memories.map((m) => (
              <MemoryCardView key={m.id} memory={m} />
            ))}
          </div>
        </div>
      ))}
      {data && data.items.length === 0 && <p className="muted">No memories with dates yet.</p>}
    </section>
  )
}
