import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Navigate } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import type { ConversationMessage } from '../api/types'
import { CHAT_READ_ROLES } from '../api/types'
import { useApiData } from '../api/useApiData'
import { useAuth } from '../auth/AuthContext'
import { Badge } from '../components/Badge'
import { Icon } from '../components/Icon'

const SESSION_TYPES = ['chat', 'reminiscence', 'support']

export function Chat() {
  const { user } = useAuth()
  const isPatient = user?.role === 'patient'
  const isCaregiver = user?.role === 'caregiver'

  const sessions = useApiData(() => api.conversationSessions())
  const [activeId, setActiveId] = useState<string | null>(null)
  const [messages, setMessages] = useState<ConversationMessage[] | null>(null)
  const [msgLoading, setMsgLoading] = useState(false)
  const [msgError, setMsgError] = useState<string | null>(null)
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  if (user && !CHAT_READ_ROLES.includes(user.role)) {
    return <Navigate to="/" replace />
  }

  useEffect(() => {
    if (!activeId && sessions.data && sessions.data.items.length > 0) {
      setActiveId(sessions.data.items[0].id)
    }
  }, [sessions.data, activeId])

  useEffect(() => {
    if (!activeId) {
      setMessages(null)
      return
    }
    let active = true
    setMsgLoading(true)
    setMsgError(null)
    api
      .conversationMessages(activeId)
      .then((r) => {
        if (active) setMessages(r.items)
      })
      .catch((e) => {
        if (active) setMsgError(e instanceof ApiError ? e.message : 'Failed to load')
      })
      .finally(() => {
        if (active) setMsgLoading(false)
      })
    return () => {
      active = false
    }
  }, [activeId])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function reloadMessages() {
    if (!activeId) return
    try {
      setMessages(await api.conversationMessages(activeId).then((r) => r.items))
    } catch {
      /* keep current view */
    }
  }

  async function send(e: FormEvent) {
    e.preventDefault()
    if (!activeId || !input.trim() || sending) return
    setSending(true)
    setMsgError(null)
    setActionError(null)
    try {
      await api.sendConversationMessage(activeId, input.trim())
      setInput('')
      await reloadMessages()
    } catch (err) {
      setMsgError(err instanceof ApiError ? err.message : 'Failed to send')
    } finally {
      setSending(false)
    }
  }

  async function stop() {
    if (!activeId) return
    if (!window.confirm(isPatient ? 'End this conversation?' : 'Stop this session for safety?')) return
    setActionError(null)
    setNotice(null)
    try {
      await api.stopConversation(activeId)
      setNotice(isPatient ? 'Conversation ended.' : 'Session stopped — safety event recorded.')
      sessions.reload()
      await reloadMessages()
    } catch (e) {
      setActionError(e instanceof ApiError ? e.message : 'Request failed')
    }
  }

  const active = sessions.data?.items.find((s) => s.id === activeId)

  return (
    <section>
      <div className="page-head">
        <h1>Conversation</h1>
        {active && (isPatient || isCaregiver) && active.status === 'active' && (
          <button type="button" className="btn danger" onClick={stop}>
            <Icon name="stop" size={15} />
            {isPatient ? 'End session' : 'Stop for safety'}
          </button>
        )}
      </div>
      <p className="muted">
        {isPatient
          ? 'Talk to me about your memories — I only share what is backed by your records.'
          : 'Reviewing conversation sessions in scope. Only the patient can send messages.'}
      </p>

      {notice && <p className="success">{notice}</p>}
      {actionError && <p className="error">{actionError}</p>}

      {isPatient && (
        <NewSession
          onCreated={(id) => {
            sessions.reload()
            setActiveId(id)
          }}
        />
      )}

      <div className="chat-layout">
        <aside className="chat-sessions panel">
          <h2>Sessions</h2>
          {sessions.loading && <p className="muted">Loading…</p>}
          {sessions.error && <p className="error">{sessions.error}</p>}
          {sessions.data && sessions.data.items.length === 0 && (
            <p className="muted">No sessions yet.</p>
          )}
          {sessions.data &&
            sessions.data.items.map((s) => (
              <button
                key={s.id}
                type="button"
                className={`chat-session${s.id === activeId ? ' active' : ''}`}
                onClick={() => setActiveId(s.id)}
              >
                <span className="chat-session-title">
                  {s.session_type} <Badge tone={s.status === 'active' ? 'green' : 'neutral'}>{s.status}</Badge>
                </span>
                <span className="muted">{s.started_at}</span>
              </button>
            ))}
        </aside>

        <div className="chat-thread panel">
          {!activeId && <p className="muted">Select a session or start one.</p>}
          {msgLoading && <p className="muted">Loading messages…</p>}
          {msgError && <p className="error">{msgError}</p>}
          {!msgLoading && !msgError && messages && (
            <>
              {messages.length === 0 && <p className="muted">No messages in this session.</p>}
              {messages.map((m) => (
                <MessageBubble key={m.id} m={m} />
              ))}
            </>
          )}
          {!msgLoading && !msgError && messages && messages.length > 0 && (
            <div ref={bottomRef} />
          )}
          {isPatient && active && active.status === 'active' && (
            <form className="chat-input" onSubmit={send}>
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask about a person, place, or memory…"
                disabled={sending}
              />
              <button type="submit" className="btn primary" disabled={sending || !input.trim()}>
                <Icon name="send" size={15} />
                {sending ? 'Sending…' : 'Send'}
              </button>
            </form>
          )}
          {isPatient && active && active.status !== 'active' && (
            <p className="muted">This session has ended.</p>
          )}
          {!isPatient && <p className="muted">Read-only view.</p>}
        </div>
      </div>
    </section>
  )
}

function MessageBubble({ m }: { m: ConversationMessage }) {
  if (m.role === 'tool') {
    const tool = (m.tool_calls?.[0] as { tool?: string } | undefined)?.tool ?? m.content
    return (
      <div className="chat-tool">
        <span className="chip">used tool: {tool}</span>
      </div>
    )
  }
  return (
    <div className={`chat-msg chat-${m.role === 'system' ? 'ai' : 'patient'}`}>
      {m.safety_flag && <Badge tone="red">safety</Badge>}
      <div className="chat-bubble">{m.content}</div>
      <span className="muted chat-time">{formatTime(m.created_at)}</span>
    </div>
  )
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

function NewSession({ onCreated }: { onCreated: (id: string) => void }) {
  const [type, setType] = useState('chat')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function start(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      const s = await api.startConversation(type)
      onCreated(s.id)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Request failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="panel form" onSubmit={start}>
      <h2>Start a new session</h2>
      <label>
        Session type
        <select value={type} onChange={(e) => setType(e.target.value)}>
          {SESSION_TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </label>
      {error && <p className="error">{error}</p>}
      <div className="form-actions">
        <button type="submit" className="btn primary" disabled={busy}>
          {busy ? 'Starting…' : 'Start session'}
        </button>
      </div>
    </form>
  )
}
