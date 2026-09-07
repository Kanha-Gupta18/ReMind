import { api } from '../api/client'
import { useApiData } from '../api/useApiData'
import { MemoryCardView } from '../components/MemoryCardView'

export function Timeline() {
  const { data, loading, error } = useApiData(() => api.timeline())

  return (
    <section>
      <div className="page-head">
        <div>
          <h1>Timeline</h1>
          {data && <p className="lead muted">{data.count} memories, in order</p>}
        </div>
      </div>
      {loading && <p className="muted">Loading memories…</p>}
      {error && <p className="error">{error}</p>}
      <div className="memory-list">
        {data?.items.map((m) => (
          <MemoryCardView key={m.id} memory={m} />
        ))}
      </div>
      {data && data.count === 0 && <p className="muted">No memories to show yet.</p>}
    </section>
  )
}
