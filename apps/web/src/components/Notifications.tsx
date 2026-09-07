import { useEffect, useRef, useState } from 'react'
import { api, ApiError } from '../api/client'
import type { Notification } from '../api/types'
import { Icon } from './Icon'

export function Notifications() {
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState<Notification[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const boxRef = useRef<HTMLDivElement>(null)

  const unread = items?.filter((n) => !n.read).length ?? 0

  function refresh() {
    setError(null)
    api
      .notifications(true)
      .then((r) => setItems(r.items))
      .catch((e) => setError(e instanceof ApiError ? e.message : 'Failed to load'))
  }

  useEffect(() => {
    if (open) refresh()
  }, [open])

  useEffect(() => {
    function onDown(e: MouseEvent) {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [])

  async function markRead(n: Notification) {
    if (n.read) return
    try {
      await api.markNotificationRead(n.id)
      refresh()
    } catch {
      /* keep the item; the panel can be reopened */
    }
  }

  async function markAll() {
    try {
      await api.markAllNotificationsRead()
      refresh()
    } catch {
      /* ignore */
    }
  }

  return (
    <div className="notif" ref={boxRef}>
      <button
        type="button"
        aria-label="Notifications"
        className={`notif-btn${open ? ' active' : ''}`}
        onClick={() => setOpen((v) => !v)}
      >
        <Icon name="bell" size={18} />
        {unread > 0 && <span className="notif-count">{unread}</span>}
      </button>
      {open && (
        <div className="notif-panel">
          <div className="notif-head">
            <strong>Notifications</strong>
            {unread > 0 && (
              <button type="button" className="btn" onClick={markAll}>
                Mark all read
              </button>
            )}
          </div>
          {error && <p className="error">{error}</p>}
          {items === null && <p className="muted">Loading…</p>}
          {items && items.length === 0 && <p className="muted">No unread notifications.</p>}
          {items &&
            items.map((n) => (
              <button
                key={n.id}
                type="button"
                className={`notif-item${n.read ? ' read' : ''}`}
                onClick={() => markRead(n)}
              >
                <span className="notif-msg">{n.message}</span>
                <span className="muted">{n.created_at}</span>
              </button>
            ))}
        </div>
      )}
    </div>
  )
}
