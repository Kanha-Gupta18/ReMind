import { Link } from 'react-router-dom'
import type { MemoryCard } from '../api/types'

export function MemoryCardView({ memory }: { memory: MemoryCard }) {
  return (
    <article className="memory-card">
      <div className="memory-card-head">
        <Link className="memory-card-title" to={`/memories/${memory.id}`}>
          {memory.title}
        </Link>
        {memory.memory_date ? <time>{memory.memory_date}</time> : <span>Date unknown</span>}
      </div>
      <p className="memory-narrative">{memory.narrative}</p>
      {memory.tags.length > 0 && (
        <div className="memory-tags">
          {memory.tags.map((tag) => (
            <span key={tag} className="tag">
              {tag}
            </span>
          ))}
        </div>
      )}
      {memory.sensitivity_flags.length > 0 && (
        <div className="memory-flags">
          {memory.sensitivity_flags.map((flag) => (
            <span key={flag} className="flag">
              {flag}
            </span>
          ))}
        </div>
      )}
    </article>
  )
}
