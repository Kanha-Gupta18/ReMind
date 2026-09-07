import { Navigate } from 'react-router-dom'
import { api } from '../api/client'
import { ANALYTICS_ROLES } from '../api/types'
import { useApiData } from '../api/useApiData'
import { useAuth } from '../auth/AuthContext'
import { Icon } from '../components/Icon'

const ACTION_ICONS: Record<string, string> = {
  view: 'file',
  chat: 'chat',
  save: 'check',
  share: 'link',
  like: 'heart',
  search: 'search',
}

export function Dashboard() {
  const { user } = useAuth()
  const { data, loading, error } = useApiData(() => api.engagement())

  if (user && !ANALYTICS_ROLES.includes(user.role)) {
    return <Navigate to="/" replace />
  }

  return (
    <section>
      <div className="page-head">
        <div>
          <h1>Engagement</h1>
          {data && (
            <p className="lead muted">{data.total_engagements} total engagements</p>
          )}
        </div>
      </div>
      {loading && <p className="muted">Loading…</p>}
      {error && <p className="error">{error}</p>}
      {data && (
        <>
          <div className="stat-grid">
            {Object.entries(data.by_action).map(([action, count]) => (
              <div key={action} className="stat">
                <Icon name={ACTION_ICONS[action] ?? 'file'} size={16} className="stat-icon" />
                <strong>{count}</strong>
                <span>{action}</span>
              </div>
            ))}
          </div>
          {data.top_memories.length > 0 && (
            <div className="group">
              <h2>Most viewed memories</h2>
              <ul className="plain-list">
                {data.top_memories.map((m) => (
                  <li key={m.memory_card_id}>
                    Memory {m.memory_card_id} · {m.views} views
                  </li>
                ))}
              </ul>
            </div>
          )}
          {data.by_action && Object.keys(data.by_action).length === 0 && (
            <p className="muted">No engagement recorded yet.</p>
          )}
        </>
      )}
    </section>
  )
}
